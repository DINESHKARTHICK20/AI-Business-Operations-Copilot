import sys
import os
import sqlite3
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
import ai_backend
from ai_backend import (
    app,
    get_db,
    signup_send_otp,
    signup_resend_otp,
    signup_verify_otp,
    get_signup_smtp_status,
    serve_spa_frontend,
    SignupSendOtpRequest,
    SignupResendOtpRequest,
    SignupVerifyOtpRequest,
    HTTPException
)
from starlette.requests import Request

print("=" * 70)
print("RUNNING COMPREHENSIVE OTP & ROUTING VERIFICATION SUITE")
print("=" * 70)

# ─── 1. Canonical Endpoint Registration Verification ───
print("\n[TEST 1] Verifying Canonical Route Registrations...")
route_map = {}
for r in app.routes:
    p = getattr(r, "path", None)
    m = getattr(r, "methods", None)
    if p:
        if p not in route_map:
            route_map[p] = set()
        if m:
            route_map[p].update(m)

expected_routes = {
    "/api/auth/signup/send-otp": {"POST"},
    "/api/auth/signup/resend-otp": {"POST"},
    "/api/auth/signup/verify-otp": {"POST"},
    "/api/auth/signup/smtp-status": {"GET"},
}

for ep, methods in expected_routes.items():
    assert ep in route_map, f"Missing canonical endpoint: {ep}"
    assert methods.issubset(route_map[ep]), f"Wrong methods for {ep}: got {route_map[ep]}, expected {methods}"
    # Verify GET is NOT registered on POST endpoints
    if "POST" in methods:
        assert "GET" not in route_map[ep], f"GET should NOT be registered on {ep}"
    print(f"  ✓ {ep}: Methods = {route_map[ep]}")

# ─── 2. SPA Fallback & 404 Protection Verification ───
print("\n[TEST 2] Verifying SPA Fallback & 404 Route Protection...")

def mock_request(method: str, path: str):
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": []
    }
    return Request(scope)

# Unknown API path with POST must raise 404, never 405
try:
    serve_spa_frontend("api/auth/unknown-action", mock_request("POST", "/api/auth/unknown-action"))
    assert False, "Should have raised 404"
except HTTPException as e:
    assert e.status_code == 404, f"Expected 404 for POST /api/..., got {e.status_code}"
    print(f"  ✓ POST /api/auth/unknown-action -> HTTP {e.status_code}: {e.detail}")

# Unknown API path with GET must raise 404, never fallback to SPA
try:
    serve_spa_frontend("api/auth/unknown-action", mock_request("GET", "/api/auth/unknown-action"))
    assert False, "Should have raised 404"
except HTTPException as e:
    assert e.status_code == 404, f"Expected 404 for GET /api/..., got {e.status_code}"
    print(f"  ✓ GET /api/auth/unknown-action -> HTTP {e.status_code}: {e.detail}")

# Unknown non-API path with POST must raise 404, never 405
try:
    serve_spa_frontend("unknown-page", mock_request("POST", "/unknown-page"))
    assert False, "Should have raised 404"
except HTTPException as e:
    assert e.status_code == 404, f"Expected 404 for POST /unknown-page, got {e.status_code}"
    print(f"  ✓ POST /unknown-page -> HTTP {e.status_code}: {e.detail}")

# ─── 3. Full OTP Lifecycle End-to-End Verification ───
print("\n[TEST 3] Verifying OTP Signup Workflow & Database States...")

test_email = "autotest_user_otp@bizops.test"
conn = get_db()
cursor = conn.cursor()
cursor.execute("DELETE FROM users WHERE email = ?", (test_email,))
cursor.execute("DELETE FROM pending_registrations WHERE email = ?", (test_email,))
conn.commit()
conn.close()

captured_otp = []
def mock_send(to_email, name, otp):
    captured_otp.append(otp)
    return True

with patch.object(ai_backend, "dispatch_otp_email", side_effect=mock_send):
    # Step 3a: Send OTP
    send_req = SignupSendOtpRequest(
        name="Auto Test User",
        email=test_email,
        password="TestPassword123!",
        company="AutoBiz Test",
        biz_type="Technology"
    )
    res_send = signup_send_otp(send_req)
    assert res_send["status"] == "success"
    assert res_send["cooldown_seconds"] == 60
    assert len(captured_otp) == 1
    otp1 = captured_otp[0]
    print(f"  ✓ Step 1: Send OTP successful! Status: {res_send['status']}, Cooldown: {res_send['cooldown_seconds']}s")

    # Step 3b: Verify user is NOT yet in users table
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (test_email,))
    assert cursor.fetchone() is None, "User should NOT be created before OTP verification!"
    print("  ✓ User account correctly NOT created prior to OTP verification")

    # Step 3c: Cooldown enforcement on immediate resend
    resend_req = SignupResendOtpRequest(email=test_email)
    try:
        signup_resend_otp(resend_req)
        assert False, "Should have rejected due to 60s cooldown"
    except HTTPException as e:
        assert e.status_code == 429
        print(f"  ✓ Cooldown enforced on immediate resend: HTTP {e.status_code} ({e.detail})")

    # Step 3d: Invalid OTP attempt verification
    verify_bad = SignupVerifyOtpRequest(email=test_email, otp="000000")
    try:
        signup_verify_otp(verify_bad)
        assert False, "Should have rejected invalid OTP"
    except HTTPException as e:
        assert e.status_code == 400
        print(f"  ✓ Invalid OTP rejected: HTTP {e.status_code} ({e.detail})")

    # Step 3e: Valid OTP verification
    verify_good = SignupVerifyOtpRequest(email=test_email, otp=otp1)
    res_verify = signup_verify_otp(verify_good)
    assert res_verify["status"] == "success"
    print(f"  ✓ Step 2: Valid OTP verification successful! Message: {res_verify['message']}")

    # Step 3f: Verify user IS now in users table with is_verified = 1
    cursor.execute("SELECT id, name, email, is_verified, company FROM users WHERE email = ?", (test_email,))
    user_row = cursor.fetchone()
    assert user_row is not None, "User MUST exist in users table after verification!"
    assert user_row["is_verified"] == 1, "User must have is_verified = 1"
    assert user_row["name"] == "Auto Test User"
    print(f"  ✓ Step 3: User record confirmed in DB: id={user_row['id']}, verified={user_row['is_verified']}")

    # Step 3g: Pending registration must be cleaned up
    cursor.execute("SELECT id FROM pending_registrations WHERE email = ?", (test_email,))
    assert cursor.fetchone() is None, "Pending registration must be deleted after successful verification!"
    print("  ✓ Pending registration table atomically cleaned up")

    # Step 3h: Duplicate signup rejection
    try:
        signup_send_otp(send_req)
        assert False, "Should reject signup for existing user"
    except HTTPException as e:
        assert e.status_code == 400
        assert "already exists" in e.detail
        print(f"  ✓ Duplicate signup rejected: HTTP {e.status_code} ({e.detail})")

    # Clean up test user
    cursor.execute("DELETE FROM users WHERE email = ?", (test_email,))
    conn.commit()
    conn.close()

print("\n" + "=" * 70)
print("ALL TESTS PASSED SUCCESSFULLY! ZERO ERRORS.")
print("=" * 70)

