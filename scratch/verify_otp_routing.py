import os
import sys
import json
import sqlite3
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath('.'))

from backend.ai_backend import (
    app,
    get_db,
    signup_send_otp,
    signup_resend_otp,
    signup_verify_otp,
    get_signup_smtp_status,
    get_signup_send_otp_info,
    get_signup_resend_otp_info,
    get_signup_verify_otp_info,
    SignupSendOtpRequest,
    SignupResendOtpRequest,
    SignupVerifyOtpRequest,
    HTTPException
)

print("=" * 75)
print("VERIFYING OTP ROUTING, METHOD HANDLERS & 405 ELIMINATION")
print("=" * 75)

# Verify all routes registered on app
routes_map = {}
for r in app.routes:
    path = getattr(r, 'path', '')
    methods = getattr(r, 'methods', set())
    if path:
        if path not in routes_map:
            routes_map[path] = set()
        routes_map[path].update(methods)

# ─── TEST 1: Check Send OTP route paths and methods ─────────────────────────
print("\n--- TEST 1: Send OTP route registrations ---")
send_otp_paths = [
    "/api/auth/signup/send-otp",
    "/api/auth/signup/send-otp/",
    "/api/auth/send-otp",
    "/api/auth/send-otp/",
    "/api/auth/otp/send",
    "/api/auth/otp/send/",
    "/api/auth/signup",
    "/api/auth/signup/",
]

for p in send_otp_paths:
    assert p in routes_map, f"Missing route {p} in router"
    methods = routes_map[p]
    assert "POST" in methods, f"Route {p} must support POST, got {methods}"
    assert "GET" in methods, f"Route {p} must support GET (informative handler), got {methods}"
    print(f"✓ {p:30} supports {sorted(list(methods))}")

# ─── TEST 2: Check Resend OTP route paths and methods ───────────────────────
print("\n--- TEST 2: Resend OTP route registrations ---")
resend_otp_paths = [
    "/api/auth/signup/resend-otp",
    "/api/auth/signup/resend-otp/",
    "/api/auth/resend-otp",
    "/api/auth/resend-otp/",
    "/api/auth/otp/resend",
    "/api/auth/otp/resend/",
]

for p in resend_otp_paths:
    assert p in routes_map, f"Missing route {p} in router"
    methods = routes_map[p]
    assert "POST" in methods, f"Route {p} must support POST"
    assert "GET" in methods, f"Route {p} must support GET"
    print(f"✓ {p:30} supports {sorted(list(methods))}")

# ─── TEST 3: Check Verify OTP route paths and methods ───────────────────────
print("\n--- TEST 3: Verify OTP route registrations ---")
verify_otp_paths = [
    "/api/auth/signup/verify-otp",
    "/api/auth/signup/verify-otp/",
    "/api/auth/verify-otp",
    "/api/auth/verify-otp/",
    "/api/auth/otp/verify",
    "/api/auth/otp/verify/",
]

for p in verify_otp_paths:
    assert p in routes_map, f"Missing route {p} in router"
    methods = routes_map[p]
    assert "POST" in methods, f"Route {p} must support POST"
    assert "GET" in methods, f"Route {p} must support GET"
    print(f"✓ {p:30} supports {sorted(list(methods))}")

# ─── TEST 4: Check SMTP/Email Status endpoints support both GET and POST ───
print("\n--- TEST 4: SMTP/Email Status endpoint registrations ---")
status_paths = [
    "/api/auth/signup/smtp-status",
    "/api/auth/signup/smtp-status/",
    "/api/auth/signup/email-status",
    "/api/auth/signup/email-status/",
    "/api/auth/smtp-status",
    "/api/auth/smtp-status/",
    "/api/auth/email-status",
    "/api/auth/email-status/",
]

for p in status_paths:
    assert p in routes_map, f"Missing route {p} in router"
    methods = routes_map[p]
    assert "GET" in methods and "POST" in methods, f"Route {p} must support GET and POST, got {methods}"
    print(f"✓ {p:30} supports {sorted(list(methods))}")

# ─── TEST 5: Verify informative GET handlers return 200 without 405 ────────
print("\n--- TEST 5: Informative GET handlers return HTTP 200 ---")
send_info = get_signup_send_otp_info()
assert send_info.status_code == 200
send_data = json.loads(send_info.body.decode())
assert send_data["status"] == "info"
assert "POST" in send_data["required_method"]
print(f"✓ get_signup_send_otp_info: status=200, message='{send_data['message']}'")

resend_info = get_signup_resend_otp_info()
assert resend_info.status_code == 200
resend_data = json.loads(resend_info.body.decode())
assert resend_data["status"] == "info"
print(f"✓ get_signup_resend_otp_info: status=200, message='{resend_data['message']}'")

verify_info = get_signup_verify_otp_info()
assert verify_info.status_code == 200
verify_data = json.loads(verify_info.body.decode())
assert verify_data["status"] == "info"
print(f"✓ get_signup_verify_otp_info: status=200, message='{verify_data['message']}'")

# ─── TEST 6: Verify SMTP status preserves Resend configuration ──────────────
print("\n--- TEST 6: Resend SMTP status preservation ---")
smtp_status = get_signup_smtp_status()
print("Current SMTP / Email Status:", smtp_status)
assert "provider" in smtp_status
assert "configured" in smtp_status
assert "smtp" in smtp_status
print("✓ Resend SMTP status correctly preserved without exposing credentials.")

# ─── TEST 7: Send OTP execution with valid test parameters ───────────────────
print("\n--- TEST 7: Functional OTP generation and delivery dispatch ---")
test_email = "test.routing.verification@example.com"
conn = get_db()
cursor = conn.cursor()
cursor.execute("DELETE FROM users WHERE LOWER(email) = LOWER(?)", (test_email,))
cursor.execute("DELETE FROM pending_registrations WHERE LOWER(email) = LOWER(?)", (test_email,))
conn.commit()
conn.close()

with patch("backend.ai_backend.dispatch_otp_email") as mock_dispatch:
    with patch("backend.ai_backend.validate_testing_recipient"):
        req = SignupSendOtpRequest(
            name="Routing Test User",
            email=test_email,
            password="SecureRoutingPass2026!",
            company="Routing Corp",
            biz_type="Testing"
        )
        res = signup_send_otp(req)
        assert res["status"] == "success"
        assert res["cooldown_seconds"] == 60
        assert res["expires_in_seconds"] == 300
        assert mock_dispatch.called
        print("✓ signup_send_otp executed successfully; OTP generated and dispatched via mock transport.")

print("\n" + "=" * 75)
print("ALL 7 TESTS PASSED — HTTP 405 METHOD NOT ALLOWED RESOLVED ACROSS ALL PATHS!")
print("=" * 75)

