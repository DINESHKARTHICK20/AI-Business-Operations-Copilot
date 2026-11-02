# AI Business Operations Copilot

A comprehensive AI-powered business operations copilot featuring customer churn prediction, sales forecasting, inventory demand optimization, and business analytics.

## Architecture

- **Frontend**: React + TypeScript + Tailwind CSS (powered by Vite, running on `http://localhost:5173`)
- **Backend**: Python FastAPI with scikit-learn ML models (`backend/ai_backend.py`, running on `http://127.0.0.1:8000`)
- **Database**: Persistent local SQLite database (`backend/ai_bizops.db`) with WAL mode and bcrypt password hashing.

## Quick Start

### 1. Install Dependencies
```bash
npm install
```

### 2. Start the Backend API Server
In a terminal, run either:
```bash
npm run server
```
or directly via Python:
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
The FastAPI backend will start at `http://127.0.0.1:8000`. You can verify health at `http://127.0.0.1:8000/health`.

### 3. Start the Frontend Development Server
In a second terminal, run:
```bash
npm run dev
```
Open `http://localhost:5173` in your browser. All API requests are proxied directly to the backend.