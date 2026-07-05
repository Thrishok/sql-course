"""Groq + Qwen integration.

Two jobs:
  1. generate_lesson()  -> teaching content for a lesson (requirement #1)
  2. check_answer()      -> explains correctness + gives suggestions (requirement #2)

If no GROQ_API_KEY is configured, both fall back to sensible offline content so
the whole app still works end-to-end without a key.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from .config import get_settings

# In-memory cache so re-opening a lesson is instant and free.
_lesson_cache: dict[str, dict[str, Any]] = {}
_client = None


def _get_client():
    """Lazily build the Groq client; None if no key is set."""
    global _client
    settings = get_settings()
    if not settings.llm_enabled:
        return None
    if _client is None:
        from groq import Groq

        _client = Groq(api_key=settings.groq_api_key)
    return _client


def _strip_think(text: str) -> str:
    """Qwen can emit <think>…</think> reasoning; drop it."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _extract_json(text: str) -> Optional[dict[str, Any]]:
    """Pull the first JSON object out of a model response, tolerating fences."""
    if not text:
        return None
    text = _strip_think(text)
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _chat(messages: list[dict[str, str]], temperature: float, max_tokens: int) -> Optional[str]:
    client = _get_client()
    if client is None:
        return None
    settings = get_settings()
    try:
        resp = client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content
    except Exception as exc:  # network/auth/model errors -> fall back gracefully
        print(f"[llm] Groq call failed: {exc}")
        return None


def _schema_text(dataset: dict[str, Any]) -> str:
    lines = []
    for table in dataset.get("tables", []):
        cols = ", ".join(table.get("columns", []))
        lines.append(f"- {table['name']}({cols})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
#  Requirement #1 — generate SQL lesson / learning content
# ---------------------------------------------------------------------------

def generate_lesson(lesson: dict[str, Any], dataset: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    cache_key = f"{settings.groq_model}:{lesson['id']}"
    if cache_key in _lesson_cache:
        return _lesson_cache[cache_key]

    exercise = lesson.get("exercise", {})
    system = (
        "You are an expert SQL instructor writing a short, practical MySQL "
        "micro-lesson for a hands-on learning IDE. The student practises on a "
        "fixed sample database immediately after reading. Teach ONLY the target "
        "concept, concisely and encouragingly. Respond with ONLY a JSON object "
        "and nothing else — no markdown fences, no commentary, no <think>."
    )
    user = f"""Dataset ({dataset.get('dialect', 'MySQL')}) tables:
{_schema_text(dataset)}

Lesson title: {lesson['title']}
Learning objective: {lesson.get('objective', '')}
Concepts to cover: {', '.join(lesson.get('concepts', []))}
Upcoming practice task (do NOT give away its answer): {exercise.get('prompt', '')}

Return JSON with exactly these fields:
{{
  "summary": "one or two sentences introducing the concept",
  "explanation_md": "2-4 short paragraphs in markdown teaching the concept; use `inline code` for SQL keywords",
  "syntax": "the general SQL syntax pattern for this concept (one short code snippet)",
  "example": {{"sql": "a runnable example query on THIS dataset that is NOT the practice answer", "explains": "one sentence describing the result"}},
  "key_points": ["3 to 4 concise takeaways"],
  "hint": "a gentle hint for the practice task that does not reveal the full query"
}}"""

    raw = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.4,
        max_tokens=1200,
    )
    parsed = _extract_json(raw) if raw else None
    if not parsed:
        parsed = _fallback_lesson(lesson)
    parsed["generated_by"] = "qwen" if raw else "offline"
    _lesson_cache[cache_key] = parsed
    return parsed


def _fallback_lesson(lesson: dict[str, Any]) -> dict[str, Any]:
    concepts = ", ".join(lesson.get("concepts", [])) or "this concept"
    return {
        "summary": lesson.get("objective", f"Learn about {lesson['title']}."),
        "explanation_md": (
            f"### {lesson['title']}\n\n"
            f"This lesson covers **{concepts}**. {lesson.get('objective', '')}\n\n"
            "Read the task on the right, write your query in the editor, press "
            "**Run** to see the result, then press **Check** for feedback.\n\n"
            "_(Set a `GROQ_API_KEY` in `.env` to get full AI-written explanations.)_"
        ),
        "syntax": "SELECT columns FROM table WHERE condition;",
        "example": {
            "sql": "SELECT * FROM products LIMIT 5;",
            "explains": "Shows the first five products so you can see the data.",
        },
        "key_points": [f"Focus: {concepts}.", "Run early and often.", "Read the error messages — they are precise."],
        "hint": "Start from the starter query and fill in the blanks.",
    }


# ---------------------------------------------------------------------------
#  Requirement #2 — check a student's answer and suggest improvements
# ---------------------------------------------------------------------------

def check_answer(
    *,
    prompt: str,
    student_sql: str,
    is_correct: bool,
    student_result: dict[str, Any],
    expected_result: dict[str, Any],
) -> dict[str, Any]:
    error = student_result.get("error")

    system = (
        "You are a supportive MySQL tutor reviewing a student's answer inside a "
        "learning IDE. Whether the answer is correct has ALREADY been decided by "
        "comparing result sets — trust the provided 'is_correct' flag; do not "
        "contradict it. Keep feedback brief, specific and encouraging. Respond "
        "with ONLY a JSON object — no markdown fences, no <think>."
    )

    def preview(res: dict[str, Any], limit: int = 5) -> str:
        cols = res.get("columns", [])
        rows = res.get("rows", [])[:limit]
        return json.dumps({"columns": cols, "rows": rows}, ensure_ascii=False)

    user = f"""Task: {prompt}

Student's SQL:
{student_sql}

Execution error (empty if none): {error or 'none'}
is_correct: {str(is_correct).lower()}

Student's result (preview): {preview(student_result)}
Reference result (preview): {preview(expected_result)}

Return JSON with exactly these fields:
{{
  "verdict": "correct" | "incorrect" | "error",
  "feedback_md": "2-4 sentences in markdown. If correct: praise plus one insight or best-practice tip. If incorrect: what is wrong and why. If there is an error: explain it simply.",
  "suggestions": ["1-3 short, actionable tips"],
  "corrected_sql": "a correct query when incorrect or errored; empty string when correct"
}}"""

    raw = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.3,
        max_tokens=800,
    )
    parsed = _extract_json(raw) if raw else None
    if not parsed:
        parsed = _fallback_check(is_correct, error)
    # Grading is authoritative — never let the model flip the verdict.
    parsed["verdict"] = "error" if (error and not is_correct) else ("correct" if is_correct else "incorrect")
    parsed["reviewed_by"] = "qwen" if raw else "offline"
    return parsed


def _fallback_check(is_correct: bool, error: Optional[str]) -> dict[str, Any]:
    if error:
        return {
            "feedback_md": f"Your query didn't run:\n\n```\n{error}\n```\n\nFix the syntax and try again.",
            "suggestions": ["Check table and column names.", "Watch for missing commas or quotes."],
            "corrected_sql": "",
        }
    if is_correct:
        return {
            "feedback_md": "✅ Correct — your result matches the expected output. Nicely done!",
            "suggestions": ["Try rewriting it a different way to compare approaches."],
            "corrected_sql": "",
        }
    return {
        "feedback_md": "Your query ran but the result doesn't match what the task asked for.",
        "suggestions": [
            "Re-read the task and check which columns and rows are expected.",
            "Compare your result grid against the requirement.",
        ],
        "corrected_sql": "",
    }
