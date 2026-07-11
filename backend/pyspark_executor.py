"""Real PySpark execution.

Runs student PySpark code in a fresh subprocess, same isolation model as
python_executor.py: no shared state between runs, wall-clock timeout, output
capped. Unlike the SQL/Python executors this needs a JVM on PATH (Java 11+),
which is why this branch targets a persistent host like Render rather than
Vercel serverless — see README for the buildpack/apt setup.

Each run pays SparkSession startup cost (a few seconds) since it's a fresh
subprocess; that's an acceptable trade for correctness and isolation in a
small demo course. A shared long-lived Spark context would need a proper job
server and is out of scope for "few pages, for demo".
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

TIMEOUT_SECONDS = 90  # Free-tier hosts (e.g. Render) are CPU/memory-throttled;
                       # a JVM + Spark cold start there can take much longer
                       # than on a normal machine.
MAX_OUTPUT_CHARS = 20_000

_BOOTSTRAP = """
import sys, os

# Trim JVM startup work as much as possible: no JIT warmup tiering, no
# compressed-oops class-data sharing probe, serial GC (cheaper to init than
# the default G1 for a JVM that lives a few seconds), no ivy/hadoop network
# lookups. These are the actual few-second costs of a cold JVM+Spark boot on
# a throttled CPU -- config alone can't remove them, only trim the margins.
os.environ["PYSPARK_SUBMIT_ARGS"] = (
    "--conf spark.driver.extraJavaOptions="
    "-XX:+UseSerialGC -XX:TieredStopAtLevel=1 -XX:CICompilerCount=1 -Xshare:off "
    "pyspark-shell"
)
os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
os.environ["HADOOP_CONF_DIR"] = ""
os.environ["SPARK_LOCAL_IP"] = "127.0.0.1"

try:
    from pyspark.sql import SparkSession
except ImportError:
    print("__PYSPARK_MISSING__", file=sys.stderr)
    sys.exit(97)

spark = (
    SparkSession.builder
    .appName("sql-course-demo")
    .master("local[1]")
    .config("spark.ui.enabled", "false")
    .config("spark.driver.memory", "256m")
    .config("spark.executor.memory", "256m")
    .config("spark.sql.shuffle.partitions", "1")
    .config("spark.sql.adaptive.enabled", "false")
    .config("spark.driver.host", "127.0.0.1")
    .config("spark.driver.bindAddress", "127.0.0.1")
    .config("spark.sql.warehouse.dir", "/tmp/spark-warehouse")
    .config("spark.hadoop.fs.defaultFS", "file:///")
    .config("spark.serializer", "org.apache.spark.serializer.JavaSerializer")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("ERROR")

try:
    exec(compile(__STUDENT_CODE__, "<student>", "exec"), {"spark": spark, "__name__": "__main__"})
finally:
    spark.stop()
"""


@dataclass
class SparkRunResult:
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False
    elapsed_ms: float = 0.0
    error: Optional[str] = None
    timed_out: bool = False
    pyspark_missing: bool = False

    def to_dict(self) -> dict:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "truncated": self.truncated,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "error": self.error,
            "timed_out": self.timed_out,
            "pyspark_missing": self.pyspark_missing,
        }


def _clip(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text, False
    return text[:MAX_OUTPUT_CHARS] + "\n… output truncated …", True


def pyspark_available() -> bool:
    if shutil.which("java") is None:
        return False
    try:
        import pyspark  # noqa: F401

        return True
    except ImportError:
        return False


def run_pyspark(code: str) -> SparkRunResult:
    code = (code or "").strip()
    if not code:
        return SparkRunResult(error="Write some PySpark code first.")

    script = _BOOTSTRAP.replace("__STUDENT_CODE__", repr(code))
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, "-B", "-c", script],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return SparkRunResult(
            elapsed_ms=(time.perf_counter() - started) * 1000,
            error=f"Timed out after {TIMEOUT_SECONDS}s. Spark cold start is slow — try again, or check for infinite loops.",
            timed_out=True,
        )
    except Exception as exc:  # pragma: no cover - environment failure
        return SparkRunResult(error=f"Failed to run PySpark: {exc}")

    elapsed = (time.perf_counter() - started) * 1000
    stdout, out_trunc = _clip(proc.stdout or "")
    stderr, err_trunc = _clip(proc.stderr or "")
    missing = proc.returncode == 97 or "__PYSPARK_MISSING__" in stderr

    return SparkRunResult(
        stdout=stdout,
        stderr=stderr,
        truncated=out_trunc or err_trunc,
        elapsed_ms=elapsed,
        error=(
            "PySpark is not installed on this server. Install pyspark + a JVM (Java 11+) to enable this lesson."
            if missing
            else (None if proc.returncode == 0 else f"Process exited with code {proc.returncode}")
        ),
        pyspark_missing=missing,
    )
