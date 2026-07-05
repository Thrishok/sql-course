# SQL Learning IDE

A browser-based IDE that **teaches MySQL-style SQL** and lets students practise
in a real coding environment. Powered by **Qwen (via the Groq API)**:

1. **Qwen generates the learning content** for each lesson — explanation, syntax,
   a worked example, key points, and a hint.
2. **A built-in coding environment** runs the student's SQL against a sample
   database, and **Qwen checks the answer** (correct / wrong) and gives suggestions.

## How the pieces fit

| Layer | What it does |
|-------|--------------|
| `backend/executor.py` | Runs SQL on a **real SQL engine** (Python's built-in SQLite) against a *fresh, seeded, in-memory database per request* — safe and instant. Pluggable: set `DB_BACKEND=mysql` to run on a real MySQL server instead. |
| `backend/llm.py` | Calls Qwen on Groq to generate lessons and review answers. Falls back to offline content if no API key is set. |
| `backend/grading.py` | Decides correctness **deterministically** by comparing result sets — the model never invents the verdict, it only explains it. |
| `backend/main.py` | FastAPI app + JSON API + serves the frontend. |
| `frontend/` | The IDE: course tree, lesson pane, SQL editor (CodeMirror), results grid, an **Explain** view (query plan), and AI feedback. |
| `data/` | `curriculum.json` (18 lessons across 6 modules) + `schema.sql` (the sample "shop" database). |

> **Why SQLite when the course teaches MySQL?** You had no MySQL server or Docker
> installed and wanted a free, zero-setup engine that truly *interprets* SQL like an
> IDE. SQLite is exactly that. The executor is pluggable, so installing MySQL later
> is a one-line config switch (see below). The **Explain** tab shows the real query
> plan so you can see how the engine interprets each query.

## Run it

```bash
cd c:\python\ide
pip install -r requirements.txt

# 1. add your free Groq key
copy .env.example .env        # then edit .env and set GROQ_API_KEY

# 2. start
python run.py                 # -> http://127.0.0.1:8000
```

Get a free key at <https://console.groq.com/keys>. Without a key the app still
runs fully — lessons and feedback use built-in offline content.

## Switching to a real MySQL server (optional)

```bash
pip install PyMySQL SQLAlchemy
```

Seed a database with `data/schema.sql`, then in `.env`:

```
DB_BACKEND=mysql
MYSQL_URL=mysql+pymysql://user:password@127.0.0.1:3306/sqlcourse
```

Student queries run inside a rolled-back transaction, so the data is never mutated.

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/api/curriculum` | Course tree + dataset schema |
| GET  | `/api/lessons/{id}` | Lesson + Qwen-generated content |
| POST | `/api/lessons/{id}/generate` | Regenerate lesson content |
| POST | `/api/run` | Execute SQL → result grid (`explain:true` for the plan) |
| POST | `/api/check` | Grade the answer + Qwen feedback |

## Model note

Defaults to `qwen/qwen3.6-27b` (set via `GROQ_MODEL`). Groq flagged
`qwen/qwen3-32b` for deprecation on 2026-06-17, so the current Qwen model is used.
