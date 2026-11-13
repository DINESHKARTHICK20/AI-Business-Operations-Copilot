import sys
from pathlib import Path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from ai_backend import app

client = TestClient(app, raise_server_exceptions=True)
print("Sending POST /api/auth/login...")
res = client.post("/api/auth/login", json={"email": "dinesh@test.com", "password": "password123"})
print(f"Status: {res.status_code}")
print(f"Response: {res.json()}")

