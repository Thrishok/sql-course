"""Application configuration loaded from environment / .env file."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv is optional at runtime
    pass


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"


class Settings:
    """Simple settings holder (no external settings lib needed)."""

    def __init__(self) -> None:
        self.groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
        self.groq_model: str = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b").strip()

        self.db_backend: str = os.getenv("DB_BACKEND", "sqlite").strip().lower()
        self.mysql_url: str = os.getenv("MYSQL_URL", "").strip()

        # Render (and most PaaS hosts) require binding 0.0.0.0, not localhost.
        self.host: str = os.getenv("HOST", "0.0.0.0").strip()
        self.port: int = int(os.getenv("PORT", "8000"))

    @property
    def llm_enabled(self) -> bool:
        """Whether we can call Groq. When False the app uses offline fallbacks."""
        return bool(self.groq_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
