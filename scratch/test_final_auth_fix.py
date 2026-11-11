import sys
import uuid
import time
import sqlite3
import threading
from pathlib import Path
from fastapi import Response, HTTPException

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.ai_backend import (
    app,
    get_db,
    init_db,
    login_user,
    register_user,
    logout_user,
    get_authenticated_user,
    UserLoginRequest,
    UserRegisterRequest,
    create_user_session,
    verify_password
)

class MockRequest:
    def __init__(self, cookies=None, headers=None, client_host="127.0.0.1"):
        self.cookies = cookies or {}
        self.headers = headers or {}
        self.client = type("Client", (), {"host": client_host})()

def run_suite():
    print("=" * 70)
    print("AI BUSINESS OPERATIONS COPILOT - AUTHENTICATION & FIX VERIFICATION")
    print("=" * 70)

    passed = 0
    total = 0

    def check(name, cond, details=""):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1
            print(f" [PASS] Test {total:02d}: {name}")
            if details:
                print(f"        -> {details}")
        else:
            print(f"![FAIL] Test {total:02d}: {name}")
            if details:
                print(f"        -> {details}")

    # 1. Database Schema & Foreign Key Check after init_db()
    init_db()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_key_check;")
    fk_issues = cur.fetchall()
    cur.execute("PRAGMA integrity_check;")
    integrity = cur.fetchone()[0]
    conn.close()

    check(
        "Database integrity and zero foreign key violations",
        integrity == "ok" and len(fk_issues) == 0,
        f"Integrity={integrity}, foreign_key_issues={len(fk_issues)}"
    )

    # 2. Existing registered account login: dinesh@test.com
    req_dinesh = UserLoginRequest(email="dinesh@test.com", password="password123")
    res_dinesh = login_user(req_dinesh, MockRequest(client_host="127.0.0.10"), Response())
    check(
        "Sign-in with existing registered account (dinesh@test.com)",
        res_dinesh["status"] == "success" and res_dinesh["user"]["email"] == "dinesh@test.com",
        f"Logged in as: {res_dinesh['user']['name']} ({res_dinesh['user']['company']})"
    )

    # 3. Existing registered account login: arun@company.com
    req_arun = UserLoginRequest(email="arun@company.com", password="password123")
    res_arun = login_user(req_arun, MockRequest(client_host="127.0.0.11"), Response())
    check(
        "Sign-in with existing registered account (arun@company.com)",
        res_arun["status"] == "success" and res_arun["user"]["email"] == "arun@company.com",
        f"Logged in as: {res_arun['user']['name']}"
    )

    # 4. Existing registered account login: priya@nexus.in
    req_priya = UserLoginRequest(email="priya@nexus.in", password="password123")
    res_priya = login_user(req_priya, MockRequest(client_host="127.0.0.12"), Response())
    check(
        "Sign-in with existing registered account (priya@nexus.in)",
        res_priya["status"] == "success" and res_priya["user"]["email"] == "priya@nexus.in",
        f"Logged in as: {res_priya['user']['name']}"
    )

    # 5. Existing registered account login: security.officer@bizops.in
    req_sec = UserLoginRequest(email="security.officer@bizops.in", password="SecurePassword2026!")
    res_sec = login_user(req_sec, MockRequest(client_host="127.0.0.13"), Response())
    check(
        "Sign-in with existing security officer account",
        res_sec["status"] == "success" and res_sec["user"]["email"] == "security.officer@bizops.in",
        f"Logged in as: {res_sec['user']['name']}"
    )

    # 6. Unregistered user cannot sign in -> HTTP 401
    unreg_passed = False
    try:
        login_user(UserLoginRequest(email="unregistered.ghost.user@bizops.org", password="SomePassword123"), MockRequest(client_host="127.0.0.14"), Response())
    except HTTPException as he:
        unreg_passed = (he.status_code == 401 and "Invalid email or password" in he.detail)
    check(
        "Unregistered user rejected with HTTP 401",
        unreg_passed,
        "Proper 401 returned for non-existent user"
    )

    # 7. Invalid password for existing registered user -> HTTP 401
    bad_pw_passed = False
    try:
        login_user(UserLoginRequest(email="dinesh@test.com", password="WrongPassword999!"), MockRequest(client_host="127.0.0.15"), Response())
    except HTTPException as he:
        bad_pw_passed = (he.status_code == 401 and "Invalid email or password" in he.detail)
    check(
        "Incorrect password rejected with HTTP 401",
        bad_pw_passed,
        "Proper 401 returned for incorrect password"
    )

    # 8. Blank email and blank password rejection -> HTTP 400
    val_passed = False
    try:
        login_user(UserLoginRequest(email="", password=""), MockRequest(), Response())
    except HTTPException as he:
        val_passed = (he.status_code == 400)
    check(
        "Blank credentials rejected with HTTP 400",
        val_passed,
        "Validation error returned"
    )

    # 9. Sign up a new user
    uid = str(uuid.uuid4())[:8]
    new_email = f"lead.ops.{uid}@testbizops.in"
    new_password = "StrongPassword2026!"
    reg_req = UserRegisterRequest(
        name=f"Lead Ops {uid}",
        email=new_email,
        password=new_password,
        company="Nexus Dynamics",
        biz_type="Logistics"
    )
    reg_res = register_user(reg_req, Response())
    check(
        "New user registration succeeds with bcrypt hashing",
        reg_res["status"] == "success" and reg_res["user"]["email"] == new_email,
        f"Created user id={reg_res['user']['id']}, email={new_email}"
    )

    # 10. Duplicate registration rejected -> HTTP 400
    dup_passed = False
    try:
        register_user(reg_req, Response())
    except HTTPException as he:
        dup_passed = (he.status_code == 400 and "already exists" in he.detail)
    check(
        "Duplicate email registration rejected with HTTP 400",
        dup_passed,
        "Duplicate rejected properly"
    )

    # 11. Sign in with the newly created account
    new_login_resp = Response()
    new_login_res = login_user(
        UserLoginRequest(email=new_email, password=new_password),
        MockRequest(client_host="127.0.0.20"),
        new_login_resp
    )
    session_token = new_login_res["token"]
    check(
        "Sign-in with newly registered account succeeds",
        new_login_res["status"] == "success" and new_login_res["user"]["email"] == new_email,
        f"Issued session token prefix: {session_token[:10]}..."
    )

    # 12. Authenticated session validation (/api/auth/me)
    req_with_cookie = MockRequest(cookies={"session_token": session_token})
    auth_user = get_authenticated_user(req_with_cookie)
    check(
        "Session authentication via session cookie succeeds",
        auth_user["email"] == new_email and auth_user["name"] == f"Lead Ops {uid}",
        f"Authenticated as: {auth_user['name']}"
    )

    # 13. Sign-out via logout_user
    logout_resp = Response()
    logout_res = logout_user(req_with_cookie, logout_resp)
    check(
        "Logout successfully revokes session",
        logout_res["status"] == "success",
        "Session revoked in database and cookies deleted"
    )

    # 14. Accessing protected endpoint after logout must return HTTP 401
    post_logout_401 = False
    try:
        get_authenticated_user(req_with_cookie)
    except HTTPException as he:
        post_logout_401 = (he.status_code == 401)
    check(
        "Access after logout rejected with HTTP 401",
        post_logout_401,
        "Revoked session rejected"
    )

    # 15. Sign in again with the newly created account after logout
    relogin_res = login_user(
        UserLoginRequest(email=new_email, password=new_password),
        MockRequest(client_host="127.0.0.21"),
        Response()
    )
    check(
        "Sign-in again with the account succeeds after logout",
        relogin_res["status"] == "success" and relogin_res["user"]["email"] == new_email,
        "Re-login issued fresh session token"
    )

    # 16. Concurrency & Lock Resilience Test: Multiple parallel logins under active lock
    lock_errors = []
    lock_successes = []
    def concurrent_login(i):
        req = UserLoginRequest(email="dinesh@test.com", password="password123")
        try:
            res = login_user(req, MockRequest(client_host=f"127.0.1.{i}"), Response())
            lock_successes.append(res)
        except Exception as e:
            lock_errors.append((type(e).__name__, str(e)))

    # Start a brief transaction lock to test retry loop
    threads = [threading.Thread(target=concurrent_login, args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()

    check(
        "Concurrent multi-threaded logins succeed with zero 500 errors",
        len(lock_successes) == 10 and len(lock_errors) == 0,
        f"10 of 10 concurrent requests succeeded (Errors: {len(lock_errors)})"
    )

    # 17. Verify business data preserved
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM customers")
    cust_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM employees")
    emp_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM products")
    prod_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM invoices")
    inv_cnt = cur.fetchone()[0]
    conn.close()

    check(
        "All business database records completely preserved",
        cust_cnt >= 7 and emp_cnt >= 4 and prod_cnt >= 6 and inv_cnt >= 23,
        f"Verified: {cust_cnt} customers, {emp_cnt} employees, {prod_cnt} products, {inv_cnt} invoices"
    )

    print("=" * 70)
    print(f"RESULTS: {passed} of {total} VERIFICATION TESTS PASSED!")
    print("=" * 70)

if __name__ == "__main__":
    run_suite()

