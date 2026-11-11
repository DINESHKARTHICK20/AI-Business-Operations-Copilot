import sys
import time
import json
import subprocess
import urllib.request
import urllib.error
import http.cookiejar
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"

def run_lifecycle():
    print("=" * 70)
    print("BACKEND RESTART & FULL AUTHENTICATION LIFECYCLE TEST")
    print("=" * 70)

    # 1. Start backend process
    print("\n[Step 1] Starting backend server on http://127.0.0.1:8000...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    try:
        # Wait for server to be responsive
        server_up = False
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"{BASE_URL}/health", timeout=1) as r:
                    if r.status == 200:
                        server_up = True
                        break
            except Exception:
                time.sleep(0.3)

        assert server_up, "Backend server failed to start within timeout"
        print("  -> Backend is online and healthy!")

        # 2. Test sign-in with existing registered account
        print("\n[Step 2] Testing sign-in with existing registered account (dinesh@test.com)...")
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

        login_body = json.dumps({"email": "dinesh@test.com", "password": "password123"}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=login_body, headers={"Content-Type": "application/json"})
        with opener.open(req) as resp:
            data = json.loads(resp.read().decode())
            print(f"  -> HTTP {resp.status} - Logged in: {data['user']['name']} ({data['user']['email']})")

        # 3. Test sign-up with new user
        test_uid = f"user_{int(time.time())}"
        test_email = f"{test_uid}@copilotops.biz"
        test_pass = "SecurePass2026!"
        print(f"\n[Step 3] Registering new user ({test_email})...")

        reg_body = json.dumps({
            "name": f"Tester {test_uid}",
            "email": test_email,
            "password": test_pass,
            "company": "Copilot Ops Inc",
            "biz_type": "Analytics"
        }).encode()
        req_reg = urllib.request.Request(f"{BASE_URL}/api/auth/register", data=reg_body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req_reg) as resp:
            data = json.loads(resp.read().decode())
            print(f"  -> HTTP {resp.status} - Registered: {data['message']}")

        # 4. Sign in with the newly registered account
        print(f"\n[Step 4] Signing in with new user ({test_email})...")
        user_cj = http.cookiejar.CookieJar()
        user_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(user_cj))

        new_login_body = json.dumps({"email": test_email, "password": test_pass}).encode()
        req_new_login = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=new_login_body, headers={"Content-Type": "application/json"})
        with user_opener.open(req_new_login) as resp:
            data = json.loads(resp.read().decode())
            print(f"  -> HTTP {resp.status} - Signed in: {data['user']['name']}")

        # 5. Verify session via /api/auth/me
        print("\n[Step 5] Verifying session with /api/auth/me...")
        req_me = urllib.request.Request(f"{BASE_URL}/api/auth/me")
        with user_opener.open(req_me) as resp:
            data = json.loads(resp.read().decode())
            print(f"  -> HTTP {resp.status} - Authenticated user: {data['email']}")

        # 6. Sign out
        print("\n[Step 6] Signing out...")
        req_logout = urllib.request.Request(f"{BASE_URL}/api/auth/logout", method="POST")
        with user_opener.open(req_logout) as resp:
            data = json.loads(resp.read().decode())
            print(f"  -> HTTP {resp.status} - {data['message']}")

        # 7. Restart the backend process
        print("\n[Step 7] Stopping backend process...")
        proc.terminate()
        proc.wait(timeout=5)
        print("  -> Backend process stopped.")

        print("  -> Starting fresh backend process to simulate restart...")
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        server_up = False
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"{BASE_URL}/health", timeout=1) as r:
                    if r.status == 200:
                        server_up = True
                        break
            except Exception:
                time.sleep(0.3)
        assert server_up, "Backend failed to restart"
        print("  -> Backend restarted successfully!")

        # 8. Sign in again with the registered account after backend restart
        print(f"\n[Step 8] Signing in again with account ({test_email}) after restart...")
        restart_cj = http.cookiejar.CookieJar()
        restart_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(restart_cj))

        relogin_body = json.dumps({"email": test_email, "password": test_pass}).encode()
        req_relogin = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=relogin_body, headers={"Content-Type": "application/json"})
        with restart_opener.open(req_relogin) as resp:
            data = json.loads(resp.read().decode())
            print(f"  -> HTTP {resp.status} - Signed in after restart: {data['user']['name']} ({data['user']['email']})")

        # 9. Also verify existing user can still sign in after restart
        print("\n[Step 9] Signing in with existing user (dinesh@test.com) after restart...")
        dinesh_body = json.dumps({"email": "dinesh@test.com", "password": "password123"}).encode()
        req_dinesh = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=dinesh_body, headers={"Content-Type": "application/json"})
        with restart_opener.open(req_dinesh) as resp:
            data = json.loads(resp.read().decode())
            print(f"  -> HTTP {resp.status} - Existing user signed in: {data['user']['name']}")

        print("\n" + "=" * 70)
        print("ALL BACKEND RESTART & AUTHENTICATION LIFECYCLE TESTS PASSED!")
        print("=" * 70)

    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            pass

if __name__ == "__main__":
    run_lifecycle()

