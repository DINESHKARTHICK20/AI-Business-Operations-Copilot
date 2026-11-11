import sys, os, time, subprocess, json, urllib.request, urllib.error

os.chdir(r"d:\My Projects\AI Business Operations Copilot")

server = subprocess.Popen(
    [r".venv\Scripts\python.exe", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "debug"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

time.sleep(4)

def req(url, data=None, headers=None, method="GET"):
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    body = json.dumps(data).encode("utf-8") if data is not None else None
    r = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(r, timeout=5) as res:
            return res.status, res.headers, res.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read().decode("utf-8")
    except Exception as e:
        return 0, {}, str(e)

print("--- 1. Health check ---")
print(req("http://127.0.0.1:8000/health"))

print("--- 2. dinesh@test.com / password123 ---")
print(req("http://127.0.0.1:8000/api/auth/login", {"email": "dinesh@test.com", "password": "password123"}, method="POST"))

print("--- 3. with Cookie header ---")
print(req("http://127.0.0.1:8000/api/auth/login", {"email": "dinesh@test.com", "password": "password123"}, headers={"Cookie": "session_token=fake_or_expired; csrf_token=test"}, method="POST"))

print("--- 4. ssmc@gmail.com ---")
print(req("http://127.0.0.1:8000/api/auth/login", {"email": "ssmc@gmail.com", "password": "password123"}, method="POST"))

print("--- 5. prasanna@gmail.com ---")
print(req("http://127.0.0.1:8000/api/auth/login", {"email": "prasanna@gmail.com", "password": "password123"}, method="POST"))

print("--- 6. prasanna1@gmail.com ---")
print(req("http://127.0.0.1:8000/api/auth/login", {"email": "prasanna1@gmail.com", "password": "password123"}, method="POST"))

print("--- 7. OPTIONS preflight for /api/auth/login ---")
print(req("http://127.0.0.1:8000/api/auth/login", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"}, method="OPTIONS"))

print("--- 8. Nonexistent email ---")
print(req("http://127.0.0.1:8000/api/auth/login", {"email": "nonexistent@test.com", "password": "password123"}, method="POST"))

print("--- 9. GET /api/auth/me with invalid session ---")
print(req("http://127.0.0.1:8000/api/auth/me", headers={"Cookie": "session_token=invalid_session_token_12345"}))

print("--- 10. GET /api/auth/me without cookie ---")
print(req("http://127.0.0.1:8000/api/auth/me"))

server.terminate()
stdout, stderr = server.communicate(timeout=3)
print("\n--- SERVER STDERR ---")
print(stderr)

