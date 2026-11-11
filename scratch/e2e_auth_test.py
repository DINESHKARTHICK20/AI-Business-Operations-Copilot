"""
Complete E2E diagnostic and verification test for AI Business Operations Copilot auth.
"""
import sys, os, time, subprocess, json, urllib.request, urllib.error, threading

os.chdir(r"d:\My Projects\AI Business Operations Copilot")

print("=" * 60)
print("1. DATABASE PERSISTENCE & USER ACCOUNTS CHECK")
print("=" * 60)
import sqlite3
conn = sqlite3.connect("backend/ai_bizops.db")
c = conn.cursor()
c.execute("PRAGMA integrity_check")
ic = c.fetchone()[0]
print(f"Database integrity check: {ic}")
assert ic == "ok"

c.execute("SELECT COUNT(*) FROM users")
total_users = c.fetchone()[0]
print(f"Total existing users: {total_users}")

c.execute("SELECT id, name, email, LENGTH(password_hash), LENGTH(password), is_active FROM users LIMIT 5")
for r in c.fetchall():
    print(f"  User {r[0]}: {r[2]} | Hash len: {r[3]} | Pass len: {r[4]} | Active: {r[5]}")

c.execute("SELECT COUNT(*) FROM customers")
print(f"Total customers: {c.fetchone()[0]}")
c.execute("SELECT COUNT(*) FROM employees")
print(f"Total employees: {c.fetchone()[0]}")
c.execute("SELECT COUNT(*) FROM products")
print(f"Total products: {c.fetchone()[0]}")
c.execute("SELECT COUNT(*) FROM invoices")
print(f"Total invoices: {c.fetchone()[0]}")
conn.close()

print("\n" + "=" * 60)
print("2. STARTING SERVER FOR E2E LIFECYCLE TESTING")
print("=" * 60)
proc = subprocess.Popen(
    [r".venv\Scripts\python.exe", "main.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)
print(f"Backend started with PID: {proc.pid}")

def wait_for_server(url, timeout=45):
    t0 = time.time()
    print("Waiting for server to complete model loading and bind port 8000...", end="", flush=True)
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    print(f" ready in {time.time() - t0:.1f}s!")
                    return True
        except Exception:
            print(".", end="", flush=True)
            time.sleep(1)
    print(" TIMEOUT!")
    return False

base = "http://127.0.0.1:8000"
assert wait_for_server(f"{base}/health"), "Server failed to start in time"

def request(url, data=None, headers=None, method="GET"):
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8")
            cookie_headers = resp.headers.get_all("Set-Cookie") if hasattr(resp.headers, "get_all") else [resp.headers.get("Set-Cookie", "")]
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = raw
            return resp.status, parsed, cookie_headers
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
        return e.code, parsed, []
    except Exception as e:
        return 0, str(e), []

base = "http://127.0.0.1:8000"

print("\n[TEST 1] Health check:")
status, body, _ = request(f"{base}/health")
print(f"Status: {status} | Body: {body}")
assert status == 200

print("\n[TEST 2] Frontend index.html served:")
status, body, _ = request(f"{base}/")
print(f"Status: {status} | Contains HTML: {'<html' in str(body).lower() or '<!doctype html>' in str(body).lower()}")
assert status == 200

print("\n[TEST 3] Login existing user dinesh@test.com:")
status, body, cookies = request(f"{base}/api/auth/login", {"email": "dinesh@test.com", "password": "password123"}, method="POST")
print(f"Status: {status} | User: {body.get('user') if isinstance(body, dict) else body}")
assert status == 200
assert body.get("status") == "success"
session_token = body.get("token")
csrf_token = body.get("csrf_token")
assert session_token

print("\n[TEST 4] Login existing user arun@company.com:")
status, body, _ = request(f"{base}/api/auth/login", {"email": "arun@company.com", "password": "password123"}, method="POST")
print(f"Status: {status} | User: {body.get('user') if isinstance(body, dict) else body}")
assert status == 200

print("\n[TEST 5] Login existing user priya@nexus.in:")
status, body, _ = request(f"{base}/api/auth/login", {"email": "priya@nexus.in", "password": "password123"}, method="POST")
print(f"Status: {status} | User: {body.get('user') if isinstance(body, dict) else body}")
assert status == 200

print("\n[TEST 6] Incorrect password login:")
status, body, _ = request(f"{base}/api/auth/login", {"email": "dinesh@test.com", "password": "wrongpassword999"}, method="POST")
print(f"Status: {status} | Detail: {body.get('detail') if isinstance(body, dict) else body}")
assert status == 401
assert "Invalid email or password" in str(body)

print("\n[TEST 7] Nonexistent user login:")
status, body, _ = request(f"{base}/api/auth/login", {"email": "ghost@doesnotexist.com", "password": "anypassword"}, method="POST")
print(f"Status: {status} | Detail: {body.get('detail') if isinstance(body, dict) else body}")
assert status == 401

print("\n[TEST 8] Empty credentials login:")
status, body, _ = request(f"{base}/api/auth/login", {"email": "", "password": ""}, method="POST")
print(f"Status: {status} | Detail: {body.get('detail') if isinstance(body, dict) else body}")
assert status == 400

print("\n[TEST 9] Session verification /api/auth/me with session cookie:")
status, body, _ = request(f"{base}/api/auth/me", headers={"Cookie": f"session_token={session_token}"})
print(f"Status: {status} | Email: {body.get('email') if isinstance(body, dict) else body}")
assert status == 200
assert body.get("email") == "dinesh@test.com"

print("\n[TEST 10] Logout:")
status, body, _ = request(f"{base}/api/auth/logout", headers={"Cookie": f"session_token={session_token}"}, method="POST")
print(f"Status: {status} | Response: {body}")
assert status == 200

print("\n[TEST 11] Session verification after logout (should be 401):")
status, body, _ = request(f"{base}/api/auth/me", headers={"Cookie": f"session_token={session_token}"})
print(f"Status: {status} | Detail: {body.get('detail') if isinstance(body, dict) else body}")
assert status == 401

print("\n[TEST 12] Parallel concurrent logins under high load (10 threads):")
results = []
def worker():
    s, b, _ = request(f"{base}/api/auth/login", {"email": "dinesh@test.com", "password": "password123"}, method="POST")
    results.append(s)

threads = [threading.Thread(target=worker) for _ in range(10)]
for t in threads: t.start()
for t in threads: t.join()
print(f"Concurrent login status codes: {results}")
assert all(s == 200 for s in results)
print("All 10 parallel logins succeeded with 0 lock errors!")

print("\n" + "=" * 60)
print("3. TESTING RESTART AND RE-LOGIN (PERSISTENCE)")
print("=" * 60)
proc.terminate()
try:
    proc.wait(timeout=5)
except Exception:
    proc.kill()
print("First server process terminated.")

time.sleep(2)
proc2 = subprocess.Popen(
    [r".venv\Scripts\python.exe", "main.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)
print(f"Second server process started with PID: {proc2.pid}")
assert wait_for_server(f"{base}/health"), "Second server failed to start in time"

status, body, _ = request(f"{base}/api/auth/login", {"email": "dinesh@test.com", "password": "password123"}, method="POST")
print(f"Login after restart -> Status: {status} | Email: {body.get('user', {}).get('email') if isinstance(body, dict) else body}")
assert status == 200
assert body.get("user", {}).get("email") == "dinesh@test.com"

proc2.terminate()
try:
    proc2.wait(timeout=5)
except Exception:
    proc2.kill()
print("Second server process terminated.")

print("\n" + "=" * 60)
print("ALL 12 TESTS PASSED PERFECTLY!")
print("=" * 60)
