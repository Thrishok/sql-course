"""Loads the course structure and the sample-database schema."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Optional

from .config import DATA_DIR


@lru_cache
def load_curriculum() -> dict[str, Any]:
    """Read data/curriculum.json (cached)."""
    with open(DATA_DIR / "curriculum.json", "r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache
def load_schema_sql() -> str:
    """Read the setup SQL that seeds the sample database (cached)."""
    data = load_curriculum()
    schema_file = data["dataset"].get("schema_file", "schema.sql")
    with open(DATA_DIR / schema_file, "r", encoding="utf-8") as fh:
        return fh.read()


def curriculum_outline() -> dict[str, Any]:
    """A trimmed view of the curriculum for the sidebar (no solutions)."""
    data = load_curriculum()
    modules = []
    for module in data["modules"]:
        modules.append(
            {
                "id": module["id"],
                "title": module["title"],
                "summary": module.get("summary", ""),
                "lessons": [
                    {"id": lesson["id"], "title": lesson["title"]}
                    for lesson in module["lessons"]
                ],
            }
        )
    return {"dataset": data["dataset"], "modules": modules}


def find_lesson(lesson_id: str) -> Optional[dict[str, Any]]:
    """Return the full lesson dict (including exercise + solution) or None."""
    data = load_curriculum()
    for module in data["modules"]:
        for lesson in module["lessons"]:
            if lesson["id"] == lesson_id:
                enriched = dict(lesson)
                enriched["module_id"] = module["id"]
                enriched["module_title"] = module["title"]
                return enriched
    return None


def dataset_info() -> dict[str, Any]:
    return load_curriculum()["dataset"]
