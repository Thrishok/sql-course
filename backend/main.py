"""FastAPI application: serves the IDE frontend and the JSON API."""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import llm
from .config import FRONTEND_DIR, get_settings
from .curriculum import curriculum_outline, dataset_info, find_lesson
from .executor import get_executor
from .grading import compare_python_output, compare_results
from .python_executor import run_python

app = FastAPI(title="SQL Learning IDE", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- request models -------------------------------------------------------
class RunRequest(BaseModel):
    sql: str
    explain: bool = False
    language: str = "sql"


class CheckRequest(BaseModel):
    lesson_id: str
    sql: str
    language: str = "sql"


class RunPythonRequest(BaseModel):
    code: str


# ---- API ------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "llm_enabled": settings.llm_enabled,
        "model": settings.groq_model if settings.llm_enabled else None,
        "db_backend": settings.db_backend,
    }


@app.get("/api/curriculum")
def get_curriculum() -> dict:
    return curriculum_outline()


@app.get("/api/lessons/{lesson_id}")
def get_lesson(lesson_id: str) -> dict:
    lesson = find_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    content = llm.generate_lesson(lesson, dataset_info())
    return {
        "lesson": {
            "id": lesson["id"],
            "title": lesson["title"],
            "objective": lesson.get("objective", ""),
            "module_title": lesson.get("module_title", ""),
            "language": lesson.get("language", "sql"),
            "exercise": {
                "prompt": lesson["exercise"]["prompt"],
                "starter_sql": lesson["exercise"].get("starter_sql", ""),
            },
        },
        "content": content,
    }


@app.post("/api/lessons/{lesson_id}/generate")
def regenerate_lesson(lesson_id: str) -> dict:
    lesson = find_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    # Drop any cached copy so Qwen writes a fresh lesson.
    settings = get_settings()
    llm._lesson_cache.pop(f"{settings.groq_model}:{lesson_id}", None)
    content = llm.generate_lesson(lesson, dataset_info())
    return {"content": content}


@app.post("/api/run")
def run_sql(req: RunRequest) -> dict:
    if req.language == "python":
        return run_python(req.sql).to_dict()
    executor = get_executor()
    result = executor.explain(req.sql) if req.explain else executor.run(req.sql)
    return result.to_dict()


@app.post("/api/run-python")
def run_python_code(req: RunPythonRequest) -> dict:
    return run_python(req.code).to_dict()


@app.post("/api/check")
def check_sql(req: CheckRequest) -> dict:
    lesson = find_lesson(req.lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    exercise = lesson["exercise"]
    language = lesson.get("language", "sql")

    if language == "python":
        student_result = run_python(req.sql)
        expected_result = run_python(exercise["solution_sql"])
        is_correct = compare_python_output(student_result, expected_result)
    else:
        executor = get_executor()
        student_result = executor.run(req.sql)
        expected_result = executor.run(exercise["solution_sql"])
        order_matters = bool(exercise.get("order_matters", False))
        is_correct = compare_results(student_result, expected_result, order_matters)

    feedback = llm.check_answer(
        prompt=exercise["prompt"],
        student_sql=req.sql,
        is_correct=is_correct,
        student_result=student_result.to_dict(),
        expected_result=expected_result.to_dict(),
        language=language,
    )

    return {
        "correct": is_correct,
        "student_result": student_result.to_dict(),
        "feedback": feedback,
    }


# ---- static frontend --------------------------------------------------
# On Vercel the frontend/ folder is served directly as static output (see
# vercel.json), so the API function doesn't need to mount it. Locally
# (python run.py) we still mount it here so `python run.py` serves everything
# from one process.
if os.getenv("VERCEL") is None:
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
