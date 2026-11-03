import sys
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi import HTTPException, Response

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.ai_backend import (
    app,
    home,
    health,
    serve_spa_frontend,
    DIST_DIR,
    DIST_INDEX_FILE,
    DIST_ASSETS_DIR,
    login_user,
    UserLoginRequest,
    get_dashboard_stats,
    get_customers
)

class MockRequest:
    def __init__(self, cookies=None, headers=None, client_host="127.0.0.1"):
        self.cookies = cookies or {}
        self.headers = headers or {}
        self.client = type("Client", (), {"host": client_host})()

def run_tests():
    print("=" * 65)
    print("AI BUSINESS OPERATIONS COPILOT - UNIFIED PORT (8000) TEST SUITE")
    print("=" * 65)

    passed = 0
    total = 0

    def check(name, cond, info=""):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1
            print(f" [PASS] Test {total:02d}: {name}")
            if info:
                print(f"        -> {info}")
        else:
            print(f"![FAIL] Test {total:02d}: {name}")
            if info:
                print(f"        -> {info}")

    # 1. Dist directory and entry point exist
    check(
        "Build directory and dist/index.html exist",
        DIST_INDEX_FILE.exists() and DIST_ASSETS_DIR.exists(),
        f"dist/index.html exists ({DIST_INDEX_FILE.stat().st_size} bytes)"
    )

    # 2. Root route serves FileResponse(dist/index.html)
    root_res = home()
    is_fileresponse = isinstance(root_res, FileResponse) and Path(root_res.path) == DIST_INDEX_FILE
    check(
        "Root '/' serves built frontend dist/index.html",
        is_fileresponse,
        f"home() returned FileResponse pointing to {root_res.path if is_fileresponse else root_res}"
    )

    # 3. Static assets directory contains compiled js and css
    js_files = list(DIST_ASSETS_DIR.glob("*.js"))
    css_files = list(DIST_ASSETS_DIR.glob("*.css"))
    check(
        "Static assets directory contains compiled JS and CSS",
        len(js_files) >= 1 and len(css_files) >= 1,
        f"Found {len(js_files)} JS chunk(s) ({js_files[0].name}) and {len(css_files)} CSS file(s) ({css_files[0].name})"
    )

    # 4. SPA fallback handles client-side routes (e.g. /dashboard, /login)
    spa_dashboard = serve_spa_frontend("dashboard")
    is_spa_ok = isinstance(spa_dashboard, FileResponse) and Path(spa_dashboard.path) == DIST_INDEX_FILE
    check(
        "SPA client route '/dashboard' serves dist/index.html",
        is_spa_ok,
        "serve_spa_frontend('dashboard') returned FileResponse for index.html"
    )

    spa_login = serve_spa_frontend("login")
    check(
        "SPA client route '/login' serves dist/index.html",
        isinstance(spa_login, FileResponse) and Path(spa_login.path) == DIST_INDEX_FILE,
        "serve_spa_frontend('login') returned FileResponse for index.html"
    )

    # 5. Non-existent API route must raise 404 (and NOT return index.html)
    api_404_ok = False
    try:
        serve_spa_frontend("api/auth/nonexistent")
    except HTTPException as e:
        api_404_ok = (e.status_code == 404)
    check(
        "Invalid API route raises HTTP 404 and does NOT return index.html",
        api_404_ok,
        "Checked /api/auth/nonexistent -> correctly raised HTTPException 404"
    )

    # 6. /health endpoint is intact and returns JSON
    health_res = health()
    check(
        "/health route is intact and returns JSON status",
        health_res.get("status") == "healthy" and health_res.get("database") == "connected",
        f"health() returned: {health_res}"
    )

    # 7. Test login with existing user (dinesh@test.com / password123)
    login_req = UserLoginRequest(email="dinesh@test.com", password="password123")
    mock_http_res = Response()
    mock_req = MockRequest()
    login_res = login_user(login_req, mock_req, mock_http_res)
    has_token = bool(login_res.get("token"))
    has_cookie = "session_token" in mock_http_res.headers.get("set-cookie", "")
    check(
        "Login with existing account (dinesh@test.com) succeeds on unified backend",
        has_token and has_cookie and login_res.get("user", {}).get("email") == "dinesh@test.com",
        f"User logged in: {login_res.get('user', {}).get('name')}, company: {login_res.get('user', {}).get('company')}"
    )

    user_ctx = login_res.get("user")
    # 8. Authenticated dashboard endpoints load data properly
    stats = get_dashboard_stats(user=user_ctx)
    rev_str = str(stats['kpis'].get('monthly_revenue', '')).replace('₹', 'Rs.')
    check(
        "Authenticated /api/dashboard/stats loads data for dashboard",
        "kpis" in stats and "active_customers" in stats["kpis"],
        f"Dashboard stats returned: revenue={rev_str}, customers={stats['kpis'].get('active_customers')}"
    )

    customers = get_customers(user=user_ctx)
    check(
        "Authenticated /api/customers loads business data",
        isinstance(customers, list) and len(customers) > 0,
        f"Loaded {len(customers)} customer records"
    )

    # 9. Verify compiled JS bundle uses relative paths for API calls
    js_content = js_files[0].read_text(encoding="utf-8")
    has_relative_api = "/api/auth/login" in js_content and "/health" in js_content
    check(
        "Compiled frontend bundle uses relative API routes",
        has_relative_api,
        "Verified /api/auth/login and /health present as relative routes in production bundle"
    )

    print("=" * 65)
    print(f"RESULTS: {passed} of {total} UNIFIED PORT TESTS PASSED!")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()
