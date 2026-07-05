"""SQL execution engine.

The default engine is Python's built-in ``sqlite3`` module: a real, self
contained SQL engine that parses, plans and executes queries with zero setup.
Each request runs against a *fresh in-memory copy* of the sample database, so
whatever a student runs (even DROP TABLE) can never affect anyone else.

The engine sits behind the small ``SqlExecutor`` interface, so a real MySQL
server can be plugged in later just by setting ``DB_BACKEND=mysql`` — no code
elsewhere has to change.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .config import get_settings
from .curriculum import load_schema_sql

# Guardrails so a heavy or accidental query can't hang the server.
MAX_ROWS = 2000            # rows returned to the browser
STEP_BUDGET = 5_000_000    # SQLite virtual-machine steps before we abort


@dataclass
class RunResult:
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    elapsed_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "truncated": self.truncated,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "error": self.error,
        }


def _jsonable(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8", "replace")
        except Exception:
            return repr(value)
    return value


class SqlExecutor:
    """Interface implemented by every backend."""

    def run(self, sql: str) -> RunResult:  # pragma: no cover - interface
        raise NotImplementedError

    def explain(self, sql: str) -> RunResult:  # pragma: no cover - interface
        raise NotImplementedError


class SQLiteExecutor(SqlExecutor):
    """Runs SQL on a fresh, seeded, in-memory SQLite database per call."""

    def __init__(self, setup_sql: str) -> None:
        self._setup_sql = setup_sql

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.executescript(self._setup_sql)

        # Abort runaway queries after a fixed number of VM steps.
        steps = {"n": 0}

        def _guard() -> int:
            steps["n"] += 1
            return 1 if steps["n"] > (STEP_BUDGET // 1000) else 0

        conn.set_progress_handler(_guard, 1000)
        return conn

    def _execute(self, sql: str, explain: bool) -> RunResult:
        sql = (sql or "").strip().rstrip(";").strip()
        if not sql:
            return RunResult(error="Write a SQL statement first.")

        query = f"EXPLAIN QUERY PLAN {sql}" if explain else sql
        conn = self._connect()
        started = time.perf_counter()
        try:
            cur = conn.execute(query)
            columns = [d[0] for d in cur.description] if cur.description else []
            fetched = cur.fetchmany(MAX_ROWS + 1)
            truncated = len(fetched) > MAX_ROWS
            rows = [[_jsonable(v) for v in row] for row in fetched[:MAX_ROWS]]
            elapsed = (time.perf_counter() - started) * 1000
            return RunResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                truncated=truncated,
                elapsed_ms=elapsed,
            )
        except sqlite3.Warning as exc:
            # Raised when more than one statement is submitted at once.
            return RunResult(
                elapsed_ms=(time.perf_counter() - started) * 1000,
                error=f"Run one statement at a time. ({exc})",
            )
        except sqlite3.Error as exc:
            return RunResult(
                elapsed_ms=(time.perf_counter() - started) * 1000,
                error=str(exc),
            )
        finally:
            conn.close()

    def run(self, sql: str) -> RunResult:
        return self._execute(sql, explain=False)

    def explain(self, sql: str) -> RunResult:
        return self._execute(sql, explain=True)


class MySQLExecutor(SqlExecutor):
    """Runs SQL against a real MySQL server (opt-in).

    Requires ``PyMySQL`` + ``SQLAlchemy`` and a ``MYSQL_URL`` pointing at a
    database already seeded with data/schema.sql. Every statement runs inside a
    transaction that is rolled back, so student queries never mutate the data.
    """

    def __init__(self, url: str) -> None:
        from sqlalchemy import create_engine  # lazy import

        self._engine = create_engine(url, pool_pre_ping=True)

    def _execute(self, sql: str, explain: bool) -> RunResult:
        from sqlalchemy import text

        sql = (sql or "").strip().rstrip(";").strip()
        if not sql:
            return RunResult(error="Write a SQL statement first.")

        query = f"EXPLAIN {sql}" if explain else sql
        started = time.perf_counter()
        try:
            with self._engine.connect() as conn:
                trans = conn.begin()
                try:
                    result = conn.execute(text(query))
                    columns = list(result.keys()) if result.returns_rows else []
                    fetched = result.fetchmany(MAX_ROWS + 1) if result.returns_rows else []
                    truncated = len(fetched) > MAX_ROWS
                    rows = [[_jsonable(v) for v in row] for row in fetched[:MAX_ROWS]]
                    return RunResult(
                        columns=columns,
                        rows=rows,
                        row_count=len(rows),
                        truncated=truncated,
                        elapsed_ms=(time.perf_counter() - started) * 1000,
                    )
                finally:
                    trans.rollback()
        except Exception as exc:  # SQLAlchemy wraps driver errors
            return RunResult(
                elapsed_ms=(time.perf_counter() - started) * 1000,
                error=str(exc),
            )

    def run(self, sql: str) -> RunResult:
        return self._execute(sql, explain=False)

    def explain(self, sql: str) -> RunResult:
        return self._execute(sql, explain=True)


_executor: Optional[SqlExecutor] = None


def get_executor() -> SqlExecutor:
    """Build (once) and return the configured executor."""
    global _executor
    if _executor is not None:
        return _executor

    settings = get_settings()
    if settings.db_backend == "mysql" and settings.mysql_url:
        _executor = MySQLExecutor(settings.mysql_url)
    else:
        _executor = SQLiteExecutor(load_schema_sql())
    return _executor
