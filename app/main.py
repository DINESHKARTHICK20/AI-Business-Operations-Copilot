"""
Application entry point alias for uvicorn app.main:app
Re-exports the FastAPI app from backend.ai_backend to support
standard FastAPI module execution patterns.
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.ai_backend import app

__all__ = ["app"]
