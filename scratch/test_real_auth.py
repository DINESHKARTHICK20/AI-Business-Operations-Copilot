import sys
import uuid
import sqlite3
import bcrypt
from datetime import datetime
from pathlib import Path
from fastapi import Request, Response, HTTPException

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.ai_backend import (
    register_user,
    login_user,
    logout_user,
    get_authenticated_user,
    get_current_user_me,
    UserRegisterRequest,
    UserLoginRequest,
    verify_password,
    hash_password,
    get_db,
    login_limiter
)

class MockRequest:
    def __init__(self, cookies=None, headers=None, client_host="127.0.0.1"):
        self.cookies = cookies or {}
        self.headers = headers or {}
        self.client = type("Client", (), {"host": client_host})()

def run_auth_verification():
    print("=" * 65)
    print("AI BUSINESS OPERATIONS COPILOT - REAL AUTHENTICATION TEST SUITE")
    print("=" * 65)

    tests_passed = 0
    total_tests = 0

    def test(name, condition, details=""):
        nonlocal tests_passed, total_tests
        total_tests += 1
        if condition:
            tests_passed += 1
            print(f" [PASS] Test {total_tests:02d}: {name}")
            if details:
                print(f"        -> {details}")
        else:
            print(f"![FAIL] Test {total_tests:02d}: {name}")
            if details:
                print(f"        -> {details}")
            raise AssertionError(f"Test failed: {name}")

    unique_id = str(uuid.uuid4())[:8]
    test_name = f"Enterprise Admin {unique_id}"
    test_email = f"admin.{unique_id}@copilot.biz"
    test_password = "SecurePassword2026!"
    test_company = "Apex Systems India"
    test_biz = "SaaS"

    # -------------------------------------------------------------
    # 1. Test registration with a new email
    # -------------------------------------------------------------
    reg_req = UserRegisterRequest(
        name=test_name,
        email=test_email,
        password=test_password,
        company=test_company,
        biz_type=test_biz
    )
    reg_resp = Response()
    reg_result = register_user(reg_req, reg_resp)

    test(
        "Registration with a new email",
        reg_result["status"] == "success" and reg_result["user"]["email"] == test_email.lower(),
        f"User ID {reg_result['user']['id']}, email: {reg_result['user']['email']}"
    )

    # -------------------------------------------------------------
    # 2. Verify password is securely bcrypt hashed in SQLite
    # -------------------------------------------------------------
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, email, password_hash, password FROM users WHERE LOWER(email) = LOWER(?)", (test_email,))
    user_row = cur.fetchone()
    conn.close()

    is_bcrypt = user_row["password_hash"].startswith("$2b$")
    not_plain = user_row["password_hash"] != test_password and user_row["password"] != test_password
    test(
        "Password stored as secure bcrypt hash (never plain text)",
        is_bcrypt and not_plain,
        f"Stored hash prefix: {user_row['password_hash'][:12]}..., plain password never saved"
    )

    # -------------------------------------------------------------
    # 3. Test duplicate registration rejection (HTTP 400)
    # -------------------------------------------------------------
    try:
        register_user(reg_req, Response())
        dup_passed = False
    except HTTPException as e:
        dup_passed = (e.status_code == 400 and "already exists" in e.detail)

    test("Duplicate registration rejected with HTTP 400", dup_passed, "Rejected duplicate email")

    # -------------------------------------------------------------
    # 4. Test invalid email and weak password validation
    # -------------------------------------------------------------
    try:
        bad_email_req = UserRegisterRequest(name="A", email="not-an-email", password=test_password)
        register_user(bad_email_req, Response())
        val_passed = False
    except HTTPException as e:
        val_passed = (e.status_code == 400)

    try:
        short_pw_req = UserRegisterRequest(name="A", email=f"short.{unique_id}@test.com", password="123")
        register_user(short_pw_req, Response())
        short_passed = False
    except HTTPException as e:
        short_passed = (e.status_code == 400 and "at least 6" in e.detail)

    test(
        "Email format and password length validation",
        val_passed and short_passed,
        "Rejected invalid email format and passwords shorter than 6 characters"
    )

    # -------------------------------------------------------------
    # 5. Test login with unregistered email (HTTP 401)
    # -------------------------------------------------------------
    unregistered_login = UserLoginRequest(email=f"ghost.{unique_id}@nowhere.org", password="SomePassword123")
    mock_req_unregistered = MockRequest(client_host="192.168.1.101")
    try:
        login_user(unregistered_login, mock_req_unregistered, Response())
        unregistered_passed = False
    except HTTPException as e:
        unregistered_passed = (e.status_code == 401 and "Invalid email or password" in e.detail)

    test("Login with unregistered email returns HTTP 401", unregistered_passed, "Invalid credentials error displayed")

    # -------------------------------------------------------------
    # 6. Test login with incorrect password (HTTP 401)
    # -------------------------------------------------------------
    wrong_pw_login = UserLoginRequest(email=test_email, password="WrongPassword999!")
    mock_req_wrong = MockRequest(client_host="192.168.1.102")
    try:
        login_user(wrong_pw_login, mock_req_wrong, Response())
        wrong_passed = False
    except HTTPException as e:
        wrong_passed = (e.status_code == 401 and "Invalid email or password" in e.detail)

    test("Login with incorrect password returns HTTP 401", wrong_passed, "Invalid credentials error displayed")

    # -------------------------------------------------------------
    # 7. Test login with valid credentials
    # -------------------------------------------------------------
    valid_login = UserLoginRequest(email=test_email, password=test_password)
    login_resp = Response()
    mock_req_valid = MockRequest(client_host="192.168.1.103")
    login_result = login_user(valid_login, mock_req_valid, login_resp)

    session_token = login_result.get("token")
    set_cookie_headers = [v for k, v in login_resp.raw_headers if k.decode().lower() == "set-cookie"]
    has_cookie = any(b"session_token=" in c for c in set_cookie_headers)

    test(
        "Login with valid credentials succeeds & issues secure session",
        login_result["status"] == "success" and session_token and has_cookie,
        f"Session token generated: {session_token[:15]}..., HTTP-only cookie dispatched"
    )

    # -------------------------------------------------------------
    # 8. Verify session persistence in SQLite database
    # -------------------------------------------------------------
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT token, user_id, expires_at, revoked_at FROM user_sessions WHERE token = ?", (session_token,))
    sess_row = cur.fetchone()
    conn.close()

    sess_persisted = (
        sess_row is not None and
        sess_row["user_id"] == reg_result["user"]["id"] and
        sess_row["revoked_at"] is None
    )
    test(
        "Session persistence in SQLite user_sessions table",
        sess_persisted,
        f"DB verified token for user_id={sess_row['user_id']}, expires_at={sess_row['expires_at']}"
    )

    # -------------------------------------------------------------
    # 9. Test authenticated session retrieval (GET /api/auth/me)
    # -------------------------------------------------------------
    # Simulate page refresh using session cookie
    auth_req_cookie = MockRequest(cookies={"session_token": session_token})
    auth_user_cookie = get_authenticated_user(auth_req_cookie)
    me_result_cookie = get_current_user_me(auth_user_cookie)

    # Simulate authorization using Bearer header fallback
    auth_req_header = MockRequest(headers={"Authorization": f"Bearer {session_token}"})
    auth_user_header = get_authenticated_user(auth_req_header)
    me_result_header = get_current_user_me(auth_user_header)

    session_valid = (
        me_result_cookie["status"] == "success" and
        me_result_cookie["user"]["email"] == test_email.lower() and
        me_result_header["user"]["email"] == test_email.lower()
    )
    test(
        "Session authentication via Cookie & Bearer header (/api/auth/me)",
        session_valid,
        f"Authenticated as: {me_result_cookie['user']['name']} ({me_result_cookie['user']['email']})"
    )

    # -------------------------------------------------------------
    # 10. Test logout revokes and deletes session
    # -------------------------------------------------------------
    logout_resp = Response()
    logout_req = MockRequest(cookies={"session_token": session_token})
    logout_result = logout_user(logout_req, logout_resp)

    # Verify session is removed/revoked from DB
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT token FROM user_sessions WHERE token = ?", (session_token,))
    revoked_check = cur.fetchone()
    conn.close()

    # Try accessing protected route with revoked session -> must raise 401
    try:
        get_authenticated_user(auth_req_cookie)
        revoked_access_denied = False
    except HTTPException as e:
        revoked_access_denied = (e.status_code == 401)

    test(
        "Logout revokes session and deletes database session record",
        logout_result["status"] == "success" and revoked_check is None and revoked_access_denied,
        "Session token destroyed; subsequent requests rejected with HTTP 401"
    )

    # -------------------------------------------------------------
    # 11. Test protected routes cannot be accessed without authentication
    # -------------------------------------------------------------
    unauth_req = MockRequest(cookies={}, headers={})
    try:
        get_authenticated_user(unauth_req)
        protected_blocked = False
    except HTTPException as e:
        protected_blocked = (e.status_code == 401 and "authentication required" in e.detail)

    test(
        "Protected routes reject unauthenticated requests (HTTP 401)",
        protected_blocked,
        "Unauthorized access blocked: authentication required"
    )

    # -------------------------------------------------------------
    # 12. Verify existing user accounts still work
    # -------------------------------------------------------------
    # Test existing account 1: dinesh@test.com / password123
    existing_login = UserLoginRequest(email="dinesh@test.com", password="password123")
    existing_resp = Response()
    existing_res = login_user(existing_login, MockRequest(client_host="192.168.1.104"), existing_resp)

    # Test existing account 2: arun@company.com / password123
    arun_login = UserLoginRequest(email="arun@company.com", password="password123")
    arun_resp = Response()
    arun_res = login_user(arun_login, MockRequest(client_host="192.168.1.105"), arun_resp)

    # Test existing account 3: priya@nexus.in / password123
    priya_login = UserLoginRequest(email="priya@nexus.in", password="password123")
    priya_resp = Response()
    priya_res = login_user(priya_login, MockRequest(client_host="192.168.1.106"), priya_resp)

    existing_accounts_work = (
        existing_res["status"] == "success" and existing_res["user"]["email"] == "dinesh@test.com" and
        arun_res["status"] == "success" and arun_res["user"]["email"] == "arun@company.com" and
        priya_res["status"] == "success" and priya_res["user"]["email"] == "priya@nexus.in"
    )
    test(
        "Existing accounts (dinesh@test.com, arun@company.com, priya@nexus.in) fully operational",
        existing_accounts_work,
        "Verified all legacy and bcrypt existing users login successfully"
    )

    # -------------------------------------------------------------
    # 13. Test Rate Limiting Protection (Brute Force Prevention)
    # -------------------------------------------------------------
    rate_ip = "192.168.99.99"
    rate_email = f"target.{unique_id}@victim.com"
    rate_key = f"{rate_ip}:{rate_email}"
    login_limiter.reset(rate_key)
    login_limiter.reset(rate_ip)

    # Trigger failed attempts up to limit
    for _ in range(5):
        try:
            login_user(UserLoginRequest(email=rate_email, password="BadPassword"), MockRequest(client_host=rate_ip), Response())
        except HTTPException:
            pass

    # 6th attempt must trigger HTTP 429
    try:
        login_user(UserLoginRequest(email=rate_email, password="BadPassword"), MockRequest(client_host=rate_ip), Response())
        rate_limit_triggered = False
    except HTTPException as e:
        rate_limit_triggered = (e.status_code == 429 and "Too many failed login attempts" in e.detail)

    login_limiter.reset(rate_key)
    login_limiter.reset(rate_ip)

    test(
        "Brute-force rate limiting protection triggers HTTP 429",
        rate_limit_triggered,
        "5 failed attempts in 5 minutes locks out subsequent attempts with HTTP 429"
    )

    # -------------------------------------------------------------
    # 14. Verify database business data preservation
    # -------------------------------------------------------------
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM customers")
    cust_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM employees")
    emp_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM products")
    prod_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM invoices")
    inv_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM profit_products")
    profit_count = cur.fetchone()[0]
    conn.close()

    data_intact = (
        cust_count >= 6 and
        emp_count >= 4 and
        prod_count >= 6 and
        inv_count >= 5 and
        profit_count >= 10
    )
    test(
        "Database business data integrity preserved",
        data_intact,
        f"Verified: {cust_count} customers, {emp_count} employees, {prod_count} products, {inv_count} invoices, {profit_count} profit products"
    )

    print("=" * 65)
    print(f"RESULTS: {tests_passed} of {total_tests} REAL AUTHENTICATION TESTS PASSED!")
    print("=" * 65)

if __name__ == "__main__":
    run_auth_verification()

