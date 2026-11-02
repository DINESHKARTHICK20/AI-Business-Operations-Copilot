import urllib.request
import urllib.parse
import urllib.error
import json
import http.cookiejar
import sqlite3
import os
import sys

BASE_URL = "http://127.0.0.1:8000"
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "backend", "ai_bizops.db")
DB_PATH = os.path.abspath(DB_PATH)
if not os.path.exists(DB_PATH):
    DB_PATH = r"d:\My Projects\AI Business Operations Copilot\backend\ai_bizops.db"

results = []

def record(test_num, name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append((test_num, name, status, detail))
    print(f"[{status}] Test {test_num}: {name} -> {detail}")

class CookieClient:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def request(self, method, path, data=None, headers=None):
        url = f"{BASE_URL}{path}"
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)
        
        encoded_data = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=encoded_data, headers=req_headers, method=method)
        try:
            with self.opener.open(req) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                headers_dict = dict(resp.headers)
                raw_cookies = resp.headers.get_all("Set-Cookie") if hasattr(resp.headers, "get_all") else None
                headers_dict["_set_cookie_list"] = raw_cookies if raw_cookies is not None else []
                try:
                    json_body = json.loads(body)
                except Exception:
                    json_body = body
                return status, json_body, headers_dict
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            headers_dict = dict(e.headers)
            raw_cookies = e.headers.get_all("Set-Cookie") if hasattr(e.headers, "get_all") else None
            headers_dict["_set_cookie_list"] = raw_cookies if raw_cookies is not None else []
            try:
                json_body = json.loads(body)
            except Exception:
                json_body = body
            return e.code, json_body, headers_dict
        except Exception as e:
            return 500, {"error": str(e)}, {}

    def get_cookies_dict(self):
        return {cookie.name: cookie.value for cookie in self.cj}

def run_tests():
    print("==================================================")
    print("STARTING PRODUCTION SECURITY VERIFICATION SUITE")
    print("==================================================")

    client = CookieClient()
    test_email = "security.officer@bizops.in"
    test_password = "SecurePassword2026!"
    test_name = "Security Officer"

    # Test 1: Register new user
    status, body, headers = client.request("POST", "/api/auth/register", {
        "name": test_name,
        "email": test_email,
        "password": test_password,
        "company": "CyberSec Defense India",
        "biz_type": "Enterprise Security"
    })
    # If already exists from earlier run, that's fine, we can test duplicate or clean up
    if status == 400 and "already exists" in str(body):
        record(1, "User Registration / Pre-existence", True, "User account exists and ready")
    else:
        record(1, "User Registration", status == 200, f"Status: {status}, response: {body}")

    # Test 2: Duplicate registration rejected
    status, body, _ = client.request("POST", "/api/auth/register", {
        "name": "Duplicate Test",
        "email": test_email,
        "password": test_password
    })
    record(2, "Duplicate Email Registration Rejection", status == 400, f"Status: {status} (Expected 400)")

    # Test 3: Login with unknown email
    status, body, _ = client.request("POST", "/api/auth/login", {
        "email": "nonexistent.user.2026@domain.xyz",
        "password": "RandomPassword123"
    })
    record(3, "Unknown Email Login Rejection", status == 401, f"Status: {status} (Expected 401)")

    # Test 4: Login with wrong password
    status, body, _ = client.request("POST", "/api/auth/login", {
        "email": test_email,
        "password": "WrongPassword999!"
    })
    record(4, "Incorrect Password Rejection", status == 401, f"Status: {status} (Expected 401)")

    # Test 5: Successful Login & HTTP-Only Cookie Verification
    login_client = CookieClient()
    status, body, headers = login_client.request("POST", "/api/auth/login", {
        "email": test_email,
        "password": test_password
    })
    cookies = login_client.get_cookies_dict()
    has_session_cookie = "session_token" in cookies
    has_csrf_cookie = "csrf_token" in cookies
    set_cookie_list = headers.get("_set_cookie_list", [])
    session_cookie_header = next((c for c in set_cookie_list if "session_token=" in c), "")
    is_httponly = "httponly" in session_cookie_header.lower()
    
    passed_5 = status == 200 and has_session_cookie and is_httponly
    record(5, "Login Success & HttpOnly Cookie Set", passed_5, f"Status: {status}, session_token HttpOnly: {is_httponly}, Header: {session_cookie_header}")

    # Test 6: Verify Authenticated Session (/api/auth/me) with Cookie
    status, body, _ = login_client.request("GET", "/api/auth/me")
    passed_6 = status == 200 and body.get("user", {}).get("email") == test_email
    record(6, "Session Restoration via /api/auth/me", passed_6, f"Status: {status}, User: {body.get('user', {}).get('name')}")

    # Test 7: Unauthenticated Request to Protected Business APIs must return 401
    unauth_client = CookieClient()
    protected_endpoints = [
        ("GET", "/api/customers"),
        ("GET", "/api/employees"),
        ("GET", "/api/inventory"),
        ("GET", "/api/invoices"),
        ("GET", "/api/sales/overview"),
        ("GET", "/api/sales/forecast"),
        ("GET", "/api/business-health"),
        ("GET", "/api/dashboard/stats"),
        ("GET", "/api/dashboard/insights"),
        ("GET", "/api/dashboard/activity"),
        ("GET", "/api/profit/products"),
        ("GET", "/api/action-center")
    ]
    all_401 = True
    details_7 = []
    for method, ep in protected_endpoints:
        st, b, _ = unauth_client.request(method, ep)
        if st != 401:
            all_401 = False
            details_7.append(f"{ep} -> {st}")
        else:
            details_7.append(f"{ep} -> 401 OK")
    record(7, "Protected Business APIs 401 Enforcement", all_401, f"Tested {len(protected_endpoints)} endpoints. Result: {'All 401 Unauthorized' if all_401 else ', '.join(details_7)}")

    # Test 8: Authenticated Request to Protected Business APIs returns 200 with data
    all_200 = True
    for method, ep in protected_endpoints:
        st, b, _ = login_client.request(method, ep)
        if st != 200:
            all_200 = False
            break
    record(8, "Authenticated Access to Business APIs", all_200, f"Status: {'All 200 OK' if all_200 else 'Failed on some endpoints'}")

    # Test 9: Rate Limiter on Failed Logins (Max 5 attempts -> 429)
    rate_client = CookieClient()
    rate_target_email = "bruteforce.target@bizops.in"
    # Execute 5 failures
    for i in range(5):
        rate_client.request("POST", "/api/auth/login", {
            "email": rate_target_email,
            "password": f"wrong_{i}"
        })
    # 6th attempt should be 429
    st_6, b_6, _ = rate_client.request("POST", "/api/auth/login", {
        "email": rate_target_email,
        "password": "wrong_6th_attempt"
    })
    record(9, "Rate Limiting (5 failures -> 429 Too Many Requests)", st_6 == 429, f"Status: {st_6}, message: {b_6.get('detail') if isinstance(b_6, dict) else b_6}")

    # Test 10: Logout & Session Revocation
    st_logout, b_logout, logout_headers = login_client.request("POST", "/api/auth/logout")
    record(10, "Logout API Success", st_logout == 200, f"Status: {st_logout}, Message: {b_logout}")

    # Test 11: Access /api/auth/me After Logout must return 401
    st_me_after, b_me_after, _ = login_client.request("GET", "/api/auth/me")
    record(11, "Revoked Session Rejection after Logout", st_me_after == 401, f"Status: {st_me_after} (Expected 401)")

    # Test 12: Database Password Encryption Verification (Bcrypt $2b$)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT email, password_hash FROM users WHERE LOWER(email) = LOWER(?)", (test_email,))
    user_row = cursor.fetchone()
    conn.close()

    if user_row and user_row[1] and user_row[1].startswith(("$2b$", "$2a$", "$2y$")):
        record(12, "Bcrypt Password Hashing in Database", True, f"Hash starts with '{user_row[1][:7]}...' (Salted & Hashed with bcrypt)")
    else:
        record(12, "Bcrypt Password Hashing in Database", False, f"Stored hash: {user_row[1] if user_row else 'None'}")

    print("==================================================")
    pass_count = sum(1 for _, _, status, _ in results if status == "PASS")
    total_count = len(results)
    print(f"SECURITY SUITE SUMMARY: {pass_count}/{total_count} PASSED")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
