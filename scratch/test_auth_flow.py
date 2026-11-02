import urllib.request
import urllib.parse
import http.cookiejar
import json
import sqlite3
import uuid

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    print("=" * 60)
    print("RUNNING COMPLETE AUTHENTICATION FLOW TEST SUITE")
    print("=" * 60)

    # Setup cookie jar for session management
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    unique_suffix = str(uuid.uuid4())[:8]
    test_email = f"test-user-{unique_suffix}@example.com"
    test_password = "StrongPassword123!"
    test_name = f"Test User {unique_suffix}"

    # TEST A: Check Health
    req = urllib.request.Request(f"{BASE_URL}/health")
    res = opener.open(req)
    health = json.loads(res.read().decode("utf-8"))
    assert health["status"] == "healthy", "Health check failed"
    print("PASS: Backend health check successful")

    # TEST 2: Register a new account
    reg_payload = json.dumps({
        "name": test_name,
        "email": test_email,
        "password": test_password,
        "company": "Test Enterprise",
        "biz_type": "SaaS"
    }).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/api/auth/register", data=reg_payload, headers={"Content-Type": "application/json"})
    res = opener.open(req)
    reg_data = json.loads(res.read().decode("utf-8"))
    assert reg_data["status"] == "success", "Registration status != success"
    assert reg_data["user"]["email"] == test_email.lower(), "Registration returned wrong email"
    print(f"PASS [TEST 2]: Register account '{test_email}' succeeded: {reg_data['message']}")

    # Verify user saved in database with secure bcrypt hash (not plain text)
    conn = sqlite3.connect("backend/ai_bizops.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, password_hash, password FROM users WHERE email = ?", (test_email.lower(),))
    db_user = cur.fetchone()
    assert db_user is not None, "User not found in database!"
    assert db_user[3].startswith("$2b$") or db_user[3].startswith("$2a$"), "Password is not bcrypt hashed!"
    assert db_user[4] != test_password, "Plain-text password leaked in database!"
    conn.close()
    print("PASS: Verified user securely saved in database with bcrypt hash and no plain-text password")

    # TEST 3: Try registering same email again -> must return HTTP 400
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/auth/register", data=reg_payload, headers={"Content-Type": "application/json"})
        opener.open(req)
        assert False, "Duplicate registration should have failed with HTTP 400"
    except urllib.error.HTTPError as e:
        assert e.code == 400, f"Expected 400 but got {e.code}"
        err_body = json.loads(e.read().decode("utf-8"))
        print(f"PASS [TEST 3]: Duplicate registration rejected with 400: {err_body.get('detail')}")

    # TEST 4: Login with unknown email -> must return HTTP 401
    bad_email_payload = json.dumps({"email": "unknown-nonexistent@example.com", "password": test_password}).encode("utf-8")
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=bad_email_payload, headers={"Content-Type": "application/json"})
        opener.open(req)
        assert False, "Login with unknown email should have failed with HTTP 401"
    except urllib.error.HTTPError as e:
        assert e.code == 401, f"Expected 401 but got {e.code}"
        print(f"PASS [TEST 4]: Unknown email login rejected with 401")

    # TEST 5: Login with registered email + wrong password -> must return HTTP 401
    bad_pass_payload = json.dumps({"email": test_email, "password": "WrongPassword999!"}).encode("utf-8")
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=bad_pass_payload, headers={"Content-Type": "application/json"})
        opener.open(req)
        assert False, "Login with wrong password should have failed with HTTP 401"
    except urllib.error.HTTPError as e:
        assert e.code == 401, f"Expected 401 but got {e.code}"
        print(f"PASS [TEST 5]: Wrong password login rejected with 401")

    # TEST 6: Login with registered email + correct password -> must succeed and set session cookie
    login_payload = json.dumps({"email": test_email, "password": test_password}).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=login_payload, headers={"Content-Type": "application/json"})
    res = opener.open(req)
    login_data = json.loads(res.read().decode("utf-8"))
    assert login_data["status"] == "success", "Login status != success"
    assert login_data["user"]["name"] == test_name, "Login returned wrong name"
    cookies = {cookie.name: cookie.value for cookie in cookie_jar}
    assert "session_token" in cookies, "session_token cookie not set!"
    print(f"PASS [TEST 6]: Login succeeded for '{test_name}', session_token cookie received: {cookies['session_token'][:10]}...")

    # TEST 7: Page refresh / Current user (GET /api/auth/me) with session cookie
    req = urllib.request.Request(f"{BASE_URL}/api/auth/me")
    res = opener.open(req)
    me_data = json.loads(res.read().decode("utf-8"))
    assert me_data["status"] == "success", "GET /api/auth/me status != success"
    assert me_data["name"] == test_name or me_data["user"]["name"] == test_name, "GET /api/auth/me returned wrong name"
    print(f"PASS [TEST 7]: Page refresh session verification (GET /api/auth/me) returned authenticated user: {me_data['user']['name']} ({me_data['user']['email']})")

    # Verify protected business APIs are accessible with session
    req = urllib.request.Request(f"{BASE_URL}/api/customers")
    res = opener.open(req)
    customers = json.loads(res.read().decode("utf-8"))
    assert len(customers) > 0, "Customers empty"
    print(f"PASS: Protected API GET /api/customers accessible with session: {len(customers)} customers returned")

    # TEST 8: Logout (POST /api/auth/logout)
    req = urllib.request.Request(f"{BASE_URL}/api/auth/logout", data=b"{}", headers={"Content-Type": "application/json"})
    res = opener.open(req)
    logout_data = json.loads(res.read().decode("utf-8"))
    assert logout_data["status"] == "success", "Logout status != success"
    print(f"PASS [TEST 8]: Logout succeeded: {logout_data['message']}")

    # Clear client cookie jar to simulate browser clearing cookie on logout response
    cookie_jar.clear()

    # TEST 9: Refresh after logout -> GET /api/auth/me must return 401
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/auth/me")
        opener.open(req)
        assert False, "GET /api/auth/me after logout should have failed with HTTP 401"
    except urllib.error.HTTPError as e:
        assert e.code == 401, f"Expected 401 but got {e.code}"
        print(f"PASS [TEST 9]: Refresh after logout (GET /api/auth/me) returned 401 Unauthorized")

    # Verify protected business APIs reject logged out requests
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/customers")
        opener.open(req)
        assert False, "GET /api/customers after logout should have failed with HTTP 401"
    except urllib.error.HTTPError as e:
        assert e.code == 401, f"Expected 401 but got {e.code}"
        print(f"PASS: Protected API GET /api/customers correctly rejected logged out request with 401")

    # TEST 11: Database business records integrity check
    conn = sqlite3.connect("backend/ai_bizops.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM customers")
    cust_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM employees")
    emp_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM products")
    prod_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM invoices")
    inv_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM profit_products")
    profit_cnt = cur.fetchone()[0]
    conn.close()

    assert cust_cnt == 6, f"Customers count mismatch: {cust_cnt}"
    assert emp_cnt == 5, f"Employees count mismatch: {emp_cnt}"
    assert prod_cnt == 6, f"Products count mismatch: {prod_cnt}"
    assert inv_cnt >= 5, f"Invoices count mismatch: {inv_cnt}"
    assert profit_cnt == 10, f"Profit products count mismatch: {profit_cnt}"

    print("=" * 60)
    print("ALL 10 AUTHENTICATION & BUSINESS DATA INTEGRITY TESTS PASSED!")
    print(f"Business Data Preserved: {cust_cnt} customers, {emp_cnt} employees, {prod_cnt} products, {inv_cnt} invoices, {profit_cnt} profit products.")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
