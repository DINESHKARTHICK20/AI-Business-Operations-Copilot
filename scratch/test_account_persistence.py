import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
import json
import sqlite3
import time
import subprocess
import sys
import uuid
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "backend" / "ai_bizops.db"

class ApiSessionClient:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))

    def request(self, method, endpoint, payload=None, extra_headers=None):
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        if extra_headers:
            headers.update(extra_headers)

        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with self.opener.open(req) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                try:
                    parsed = json.loads(body)
                except Exception:
                    parsed = body
                return status, parsed
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = body
            return e.code, parsed

    def get_cookies(self):
        return {c.name: c.value for c in self.cookie_jar}

    def clear_cookies(self):
        self.cookie_jar.clear()


def run_persistence_tests():
    print("=" * 70)
    print("AI BUSINESS OPERATIONS COPILOT - ACCOUNT PERSISTENCE TEST SUITE")
    print("=" * 70)

    # 1. Check health
    client = ApiSessionClient()
    status, health = client.request("GET", "/health")
    assert status == 200, f"Health check failed: {health}"
    assert health.get("status") == "healthy", "Status not healthy"
    print("[PASS] Step 1: Backend server is healthy & database connected.")

    # 2. Login with existing account
    existing_email = "security.officer@bizops.in"
    existing_pass = "SecurePassword2026!"
    status, res = client.request("POST", "/api/auth/login", {"email": existing_email, "password": existing_pass})
    assert status == 200, f"Existing account login failed: {res}"
    assert res.get("user", {}).get("email") == existing_email
    print(f"[PASS] Step 2: Successfully logged in with existing account: {existing_email}")

    # 3. Check /api/auth/me for existing account
    status, me = client.request("GET", "/api/auth/me")
    assert status == 200, f"Session check failed: {me}"
    assert me.get("user", {}).get("email") == existing_email
    print(f"[PASS] Step 3: Verified existing account session via /api/auth/me: {me['user']['name']}")

    # 4. Logout existing user
    status, logout = client.request("POST", "/api/auth/logout")
    assert status == 200
    client.clear_cookies()
    print("[PASS] Step 4: Existing user logged out successfully.")

    # 5. Register a new user
    uid = str(uuid.uuid4())[:8]
    new_email = f"persisted.user.{uid}@enterprise.in"
    new_pass = "TestSecurePassword2026!"
    new_name = f"Persisted Officer {uid}"
    new_company = "Enterprise Cloud Corp"
    new_biz = "SaaS Analytics"

    status, reg = client.request("POST", "/api/auth/register", {
        "name": new_name,
        "email": new_email,
        "password": new_pass,
        "company": new_company,
        "biz_type": new_biz
    })
    assert status == 200, f"Registration failed: {reg}"
    assert reg.get("status") == "success"
    assert reg.get("user", {}).get("email") == new_email
    print(f"[PASS] Step 5: Registered new user: {new_email}")

    # 6. Verify record is physically written in sqlite3 database
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, password_hash, company, is_active FROM users WHERE email = ?", (new_email,))
    row = cur.fetchone()
    conn.close()
    assert row is not None, "User NOT found in SQLite database!"
    assert row[1] == new_name
    assert row[3].startswith("$2b$") or row[3].startswith("$2a$"), "Password not bcrypt hashed!"
    print(f"[PASS] Step 6: Verified user ID {row[0]} saved in persistent SQLite storage ({DB_PATH.name}).")

    # 7. Login with newly registered user
    new_client = ApiSessionClient()
    status, login_res = new_client.request("POST", "/api/auth/login", {"email": new_email, "password": new_pass})
    assert status == 200, f"New user login failed: {login_res}"
    assert login_res.get("user", {}).get("name") == new_name
    print(f"[PASS] Step 7: Successfully logged in with new user credentials.")

    # 8. Verify session with /api/auth/me
    status, me_res = new_client.request("GET", "/api/auth/me")
    assert status == 200
    assert me_res.get("user", {}).get("email") == new_email
    print(f"[PASS] Step 8: Verified new user session via /api/auth/me.")

    # 9. Logout
    status, logout_res = new_client.request("POST", "/api/auth/logout")
    assert status == 200
    new_client.clear_cookies()
    print("[PASS] Step 9: Logged out new user.")

    # 10. Test Server Restart & Persistence Across Restarts
    # We will simulate restarting the backend by spawning an isolated sub-process on another port (8001),
    # hitting both existing and newly registered accounts against the database, then stopping the process.
    test_port = 8001
    print(f"[PASS] Step 10: Testing server restart on port {test_port} against persistent database...")
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", f"--port={test_port}"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    try:
        # Wait for server to bind
        time.sleep(3)

        restart_client = ApiSessionClient(base_url=f"http://127.0.0.1:{test_port}")

        # Check health on restarted server
        h_st, h_dat = restart_client.request("GET", "/health")
        assert h_st == 200, f"Restarted backend health failed: {h_dat}"
        print(f"  - Restarted backend healthy on port {test_port}.")

        # 11. Login using newly registered account on restarted server
        st_new, dat_new = restart_client.request("POST", "/api/auth/login", {"email": new_email, "password": new_pass})
        assert st_new == 200, f"Login on restarted server failed: {dat_new}"
        assert dat_new.get("user", {}).get("email") == new_email
        print(f"[PASS] Step 11: Newly created account persisted and successfully logged in on restarted backend!")

        # 12. Login using existing account on restarted server
        st_old, dat_old = restart_client.request("POST", "/api/auth/login", {"email": existing_email, "password": existing_pass})
        assert st_old == 200, f"Existing login on restarted server failed: {dat_old}"
        assert dat_old.get("user", {}).get("email") == existing_email
        print(f"[PASS] Step 12: Existing account persisted and successfully logged in on restarted backend!")

    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()
        print("  - Restarted test backend instance shut down cleanly.")

    # 13. Verify all business data rows are intact
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM customers")
    c_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM employees")
    e_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM products")
    p_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM invoices")
    i_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM profit_products")
    pp_count = cur.fetchone()[0]
    conn.close()

    assert c_count >= 6, f"Customer data lost: {c_count}"
    assert e_count >= 5, f"Employee data lost: {e_count}"
    assert p_count >= 6, f"Product data lost: {p_count}"
    assert i_count >= 5, f"Invoice data lost: {i_count}"
    assert pp_count >= 10, f"Profit products data lost: {pp_count}"
    print(f"[PASS] Step 13: All business records completely intact (Customers: {c_count}, Employees: {e_count}, Products: {p_count}, Invoices: {i_count}).")

    print("=" * 70)
    print("ALL 13 ACCOUNT PERSISTENCE & SERVER RESTART TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_persistence_tests()
