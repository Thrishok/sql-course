"""Vercel serverless entrypoint. Exposes the FastAPI app as `app`."""
from backend.main import app  # noqa: F401
