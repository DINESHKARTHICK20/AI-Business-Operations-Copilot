"""
Backend entry point alias for uvicorn backend.main:app
Re-exports the FastAPI app from backend.ai_backend
"""
from backend.ai_backend import app

__all__ = ["app"]
