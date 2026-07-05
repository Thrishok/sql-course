"""Convenience launcher:  python run.py

Starts the SQL Learning IDE on http://HOST:PORT (default 127.0.0.1:8000).
"""
from __future__ import annotations

import uvicorn

from backend.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    print("=" * 60)
    print("  SQL Learning IDE")
    print(f"  Open:      http://{settings.host}:{settings.port}")
    print(f"  Qwen/Groq: {'ON — ' + settings.groq_model if settings.llm_enabled else 'OFF (offline fallback; set GROQ_API_KEY)'}")
    print(f"  SQL engine: {settings.db_backend}")
    print("=" * 60)
    uvicorn.run("backend.main:app", host=settings.host, port=settings.port, reload=False)
