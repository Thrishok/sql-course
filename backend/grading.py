"""Deterministic result-set comparison used to grade answers.

Correctness is decided here by comparing the student's result set against the
reference solution's result set — never by the language model. The LLM only
explains *why* and suggests improvements.
"""
from __future__ import annotations

from collections import Counter

from .executor import RunResult


def compare_results(student: RunResult, expected: RunResult, order_matters: bool) -> bool:
    """True when the student's rows match the reference solution's rows."""
    if student.error or expected.error:
        return False
    if len(student.columns) != len(expected.columns):
        return False
    if student.row_count != expected.row_count:
        return False

    student_rows = [tuple(r) for r in student.rows]
    expected_rows = [tuple(r) for r in expected.rows]

    if order_matters:
        return student_rows == expected_rows
    # Order-insensitive: same rows, same multiplicities, any order.
    return Counter(student_rows) == Counter(expected_rows)
