import asyncio
import json
import sys
from pathlib import Path

# Add project root and backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.ai_backend import app

async def test_asgi_login():
    print("Sending ASGI POST /api/auth/login request...")
    
    body = json.dumps({"email": "dinesh@test.com", "password": "password123"}).encode("utf-8")
    
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.1"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/auth/login",
        "raw_path": b"/api/auth/login",
        "query_string": b"",
        "headers": [
            (b"host", b"localhost:8000"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"origin", b"http://localhost:5173"),
        ],
        "client": ("127.0.0.1", 54321),
        "server": ("127.0.0.1", 8000),
    }

    messages = [
        {"type": "http.request", "body": body, "more_body": False}
    ]

    response_started = {}
    response_body = []

    async def receive():
        if messages:
            return messages.pop(0)
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.start":
            response_started.update(message)
        elif message["type"] == "http.response.body":
            response_body.append(message.get("body", b""))

    try:
        await app(scope, receive, send)
        status_code = response_started.get("status")
        full_body = b"".join(response_body).decode("utf-8", errors="replace")
        print(f"ASGI Response Status: {status_code}")
        print(f"ASGI Response Body: {full_body}")
    except Exception as e:
        import traceback
        print("ASGI Exception caught:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_asgi_login())
