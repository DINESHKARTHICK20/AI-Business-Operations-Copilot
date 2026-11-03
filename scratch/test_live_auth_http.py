import json
import urllib.request
import urllib.parse
import http.cookiejar

cookie_jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

login_url = "http://127.0.0.1:8000/api/auth/login"
login_payload = json.dumps({
    "email": "dinesh@test.com",
    "password": "password123"
}).encode("utf-8")

req = urllib.request.Request(
    login_url,
    data=login_payload,
    headers={"Content-Type": "application/json"}
)

print("=" * 65)
print("TESTING LIVE HTTP LOGIN & AUTHENTICATION ON PORT 8000")
print("=" * 65)

try:
    with opener.open(req) as resp:
        print("[PASS] HTTP Login status:", resp.status)
        login_data = json.loads(resp.read().decode("utf-8"))
        print("[PASS] Logged in as:", login_data.get("user", {}).get("name"), f"({login_data.get('user', {}).get('email')})")
        print("[PASS] Token issued:", bool(login_data.get("token")))

    # Print cookies received
    cookies = {c.name: c.value for c in cookie_jar}
    print("[PASS] Cookies received:", list(cookies.keys()))
    assert "session_token" in cookies, "Missing session_token cookie"

    # Test /api/auth/me with cookie
    me_req = urllib.request.Request("http://127.0.0.1:8000/api/auth/me")
    with opener.open(me_req) as resp:
        print("[PASS] /api/auth/me status:", resp.status)
        me_data = json.loads(resp.read().decode("utf-8"))
        print("[PASS] /api/auth/me authenticated user:", me_data.get("email"))

    # Test /api/dashboard/stats with cookie
    stats_req = urllib.request.Request("http://127.0.0.1:8000/api/dashboard/stats")
    with opener.open(stats_req) as resp:
        print("[PASS] /api/dashboard/stats status:", resp.status)
        stats_data = json.loads(resp.read().decode("utf-8"))
        print("[PASS] /api/dashboard/stats loaded active customers:", stats_data.get("kpis", {}).get("active_customers"))

    # Test /api/customers with cookie
    cust_req = urllib.request.Request("http://127.0.0.1:8000/api/customers")
    with opener.open(cust_req) as resp:
        print("[PASS] /api/customers status:", resp.status)
        cust_data = json.loads(resp.read().decode("utf-8"))
        print(f"[PASS] /api/customers loaded {len(cust_data)} customers")

    print("=" * 65)
    print("ALL LIVE HTTP AUTHENTICATION TESTS PASSED ON PORT 8000!")
    print("=" * 65)
except Exception as e:
    print("[FAIL] Error during live HTTP login test:", type(e), e)

