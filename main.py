"""
Root entry point alias for uvicorn main:app
Re-exports the FastAPI app from backend.ai_backend
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.ai_backend import app

__all__ = ["app"]
