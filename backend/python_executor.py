"""Sandboxed Python execution.

Runs student code in a fresh subprocess (never in this server's own process),
with a wall-clock timeout, an output-size cap, and no shared state between
runs. This is the "coding environment" for Python, matching the same
zero-install, free approach used for SQL (backend/executor.py).

Safe for Vercel-style serverless too: `python -I -S` with `-B` avoids writing
bytecode files or reading a user site-config, and everything happens inside
one short-lived function invocation.
"""
from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

TIMEOUT_SECONDS = 8
MAX_OUTPUT_CHARS = 20_000


@dataclass
class PyRunResult:
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False
    elapsed_ms: float = 0.0
    error: Optional[str] = None
    timed_out: bool = False

    def to_dict(self) -> dict:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "truncated": self.truncated,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "error": self.error,
            "timed_out": self.timed_out,
        }


def _clip(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text, False
    return text[:MAX_OUTPUT_CHARS] + "\n… output truncated …", True


def run_python(code: str) -> PyRunResult:
    code = (code or "").strip()
    if not code:
        return PyRunResult(error="Write some Python code first.")

    started = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-B", "-c", code],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return PyRunResult(
            elapsed_ms=(time.perf_counter() - started) * 1000,
            error=f"Timed out after {TIMEOUT_SECONDS}s. Check for infinite loops.",
            timed_out=True,
        )
    except Exception as exc:  # pragma: no cover - environment failure
        return PyRunResult(error=f"Failed to run Python: {exc}")

    elapsed = (time.perf_counter() - started) * 1000
    stdout, out_trunc = _clip(proc.stdout or "")
    stderr, err_trunc = _clip(proc.stderr or "")

    return PyRunResult(
        stdout=stdout,
        stderr=stderr,
        truncated=out_trunc or err_trunc,
        elapsed_ms=elapsed,
        error=None if proc.returncode == 0 else f"Process exited with code {proc.returncode}",
    )
