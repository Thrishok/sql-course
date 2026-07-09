# SQL Learning IDE (SQL + Python + PySpark)

A browser-based IDE that teaches **MySQL-style SQL, Python, and PySpark**, and
lets students practise in a real coding environment. Powered by **Qwen (via
the Groq API)**:

1. **Qwen generates the learning content** for each lesson — explanation, syntax,
   a worked example, key points, and a hint.
2. **A built-in coding environment** runs the student's code for real (SQL,
   Python, or PySpark), and **Qwen checks the answer** (correct / wrong) and
   gives suggestions.

This branch (`PYSPARK_JUPYTERHUB`) targets deployment on **Render** (or any
persistent host) rather than Vercel, because real PySpark needs a JVM and a
process that can spawn subprocesses — Vercel's serverless functions can't
reliably do either. SQL and Python still run fine on Vercel too; only the
PySpark lessons need this branch's target.

## How the pieces fit

| Layer | What it does |
|-------|--------------|
| `backend/executor.py` | Runs SQL on a **real SQL engine** (Python's built-in SQLite) against a *fresh, seeded, in-memory database per request* — safe and instant. Pluggable: set `DB_BACKEND=mysql` to run on a real MySQL server instead. |
| `backend/python_executor.py` | Runs student Python in a fresh subprocess per request — free, zero-install, isolated. |
| `backend/pyspark_executor.py` | Runs student PySpark in a fresh subprocess with a real `SparkSession` (`local[1]` master). Needs a JVM (Java 11+) on PATH; degrades gracefully with a clear message if PySpark/Java isn't installed. |
| `backend/llm.py` | Calls Qwen on Groq to generate lessons and review answers, language-aware (SQL/Python/PySpark). Falls back to offline content if no API key is set. |
| `backend/grading.py` | Decides correctness **deterministically** — SQL by comparing result sets, Python/PySpark by comparing stdout — the model never invents the verdict, it only explains it. |
| `backend/main.py` | FastAPI app + JSON API + serves the frontend. |
| `frontend/` | The IDE: course tree, lesson pane, a CodeMirror editor that switches mode per lesson (SQL/Python/PySpark), results grid or stdout view, an **Explain** view (query plan, SQL only), and AI feedback. |
| `data/` | `curriculum.json` (18 SQL + 6 Python + 3 PySpark lessons) + `schema.sql` (the sample "shop" database). |

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

## Deploying to Render (for the PySpark lessons)

PySpark needs a JVM. Render's **native** Python environment builds run as a
non-root user against a read-only filesystem outside the app directory, so
`apt-get install` (needed for Java) fails there — there is no way to install
a system package in Render's native build step. This branch deploys via
**Docker** instead, which gives full control over the base image:

1. Push this branch to GitHub.
2. Create a new **Web Service** on Render, connect the repo, branch `PYSPARK_JUPYTERHUB`.
3. **Runtime:** choose **Docker** (Render auto-detects the `Dockerfile` at the repo root).
4. Leave Build/Start commands blank — the `Dockerfile`'s `CMD` handles startup.
5. **Environment:** add `GROQ_API_KEY` (and optionally `GROQ_MODEL`). Don't set
   `PORT`/`HOST` — Render injects `$PORT` automatically and `run.py` binds `0.0.0.0`.

The `Dockerfile` installs `default-jre-headless` (Java 17) as root during the
image build, then installs `requirements.txt` (including `pyspark`) on top.

`render-build.sh` runs `apt-get install default-jre-headless` to get Java 11+
on the image, then `pip install -r requirements.txt` (which includes `pyspark`).
Without Java, the PySpark lessons still load and run — they just return a
clear "PySpark is not installed on this server" message instead of crashing.

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
