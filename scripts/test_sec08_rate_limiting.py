"""
SEC-08 Master Verification Suite: Persistent and Distributed Rate Limiting
Tests all 15 required security scenarios:
1. Normal login succeeds.
2. Repeated failed login attempts trigger rate limiting.
3. Rate-limit counters persist across backend restarts.
4. Multiple FastAPI worker processes share the same counters.
5. Concurrent attempts cannot bypass configured limits.
6. Expired rate limits reset correctly.
7. Different account identifiers are handled appropriately.
8. Different IP addresses are handled appropriately.
9. Spoofed forwarding headers cannot bypass rate limits.
10. HTTP 429 and Retry-After responses work correctly.
11. Legitimate users are not permanently locked out.
12. Expired rate-limit records are cleaned safely.
13. Database failures do not silently disable authentication protection.
14. No permanent test-data contamination occurs.
15. Existing login and registration remain functional.
"""

import os
import sys
import time
import json
import socket
import logging
import urllib.request
import subprocess
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from sqlalchemy import text
from backend.database import engine, is_mysql_mode
from backend.rate_limiter import (
    get_client_ip,
    login_limiter,
    signup_limiter,
    DistributedRateLimiter,
)
from backend.ai_backend import app, hash_password
from fastapi.testclient import TestClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sec08_test")

passed_tests = 0
total_tests = 15

print("=" * 75)
print("SEC-08: PERSISTENT AND DISTRIBUTED RATE LIMITING TEST SUITE")
print("=" * 75)


def cleanup_test_artifacts():
    """Remove all test keys and records from rate_limits and users."""
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM rate_limits WHERE rate_key LIKE '%sec08%' OR rate_key LIKE '%test%'"))
            conn.execute(text("DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%sec08%')"))
            conn.execute(text("DELETE FROM users WHERE email LIKE '%sec08%'"))
    except Exception as e:
        logger.warning("Cleanup error: %s", e)


# Clean any previous run
cleanup_test_artifacts()

client = TestClient(app)

# ============================================================
# SCENARIO 1: Normal login succeeds
# ============================================================
print("\n--- Test 1: Normal login succeeds ---")
test_email_1 = "sec08_user1@example.com"
test_pass_1 = "SuperSecurePassword123!@#"

# Register user 1
reg_res = client.post("/api/auth/register", json={
    "name": "SEC08 User One",
    "email": test_email_1,
    "password": test_pass_1,
    "company": "SEC08 Corp",
    "biz_type": "Technology"
})
assert reg_res.status_code == 200, f"Registration failed: {reg_res.text}"

# Login with correct password
login_res = client.post("/api/auth/login", json={
    "email": test_email_1,
    "password": test_pass_1
})
assert login_res.status_code == 200, f"Login failed: {login_res.text}"
login_data = login_res.json()
assert login_data.get("status") == "success"
assert "session_token" in login_res.cookies or "csrf_token" in login_data
print("PASS: Normal login succeeds with valid credentials.")
passed_tests += 1


# ============================================================
# SCENARIO 2: Repeated failed login attempts trigger rate limiting
# ============================================================
print("\n--- Test 2: Repeated failed login attempts trigger rate limiting ---")
test_email_2 = "sec08_fail_user@example.com"
# Register user 2
client.post("/api/auth/register", json={
    "name": "SEC08 Fail User",
    "email": test_email_2,
    "password": "ValidPassword999!@#",
    "company": "SEC08 Corp"
})

# Make 5 failed attempts
for i in range(1, 6):
    res = client.post("/api/auth/login", json={"email": test_email_2, "password": f"WrongPass{i}"})
    assert res.status_code == 401, f"Attempt {i} expected 401, got {res.status_code}"

# Attempt 6 must be 429
res_blocked = client.post("/api/auth/login", json={"email": test_email_2, "password": "WrongPassword6"})
assert res_blocked.status_code == 429, f"Attempt 6 expected 429, got {res_blocked.status_code}: {res_blocked.text}"
assert "Too many failed login attempts" in res_blocked.json()["detail"]
print("PASS: 5 failed attempts triggered HTTP 429 rate limit.")
passed_tests += 1


# ============================================================
# SCENARIO 3: Rate-limit counters persist across backend restarts
# ============================================================
print("\n--- Test 3: Rate-limit counters persist across backend restarts ---")
restart_email = "sec08_restart_test@example.com"
restart_ip = "192.0.2.100"
rate_key_restart = f"{restart_ip}:{restart_email}"

# Simulate process 1 recording 5 failures directly in MySQL rate limiter
login_limiter.reset(rate_key_restart)
for _ in range(5):
    login_limiter.record_failure(rate_key_restart)

assert login_limiter.is_rate_limited_key(rate_key_restart), "Should be locked out in Process 1"

# "Restart": Re-instantiate a completely new limiter instance (simulating fresh process boot)
fresh_limiter = DistributedRateLimiter(prefix="login", max_attempts=5, window_seconds=300)
is_blocked = fresh_limiter.is_rate_limited(rate_key_restart, threshold=5)
remaining = fresh_limiter.get_remaining_seconds(rate_key_restart)

assert is_blocked, "Fresh limiter process did not see persisted lockout in MySQL!"
assert remaining > 0, f"Remaining seconds must be > 0, got {remaining}"
print(f"PASS: Lockout persisted across simulated process restart (remaining: {remaining}s).")
passed_tests += 1


# ============================================================
# SCENARIO 4: Multiple FastAPI worker processes share the same counters
# ============================================================
print("\n--- Test 4: Multiple FastAPI worker processes share the same counters ---")
# Start Worker 1 on port 8013 and Worker 2 on port 8014
python_bin = sys.executable
port_w1 = 8013
port_w2 = 8014

proc_w1 = subprocess.Popen(
    [python_bin, "-m", "uvicorn", "backend.ai_backend:app", "--port", str(port_w1), "--log-level", "error"],
    cwd=ROOT_DIR
)
proc_w2 = subprocess.Popen(
    [python_bin, "-m", "uvicorn", "backend.ai_backend:app", "--port", str(port_w2), "--log-level", "error"],
    cwd=ROOT_DIR
)

try:
    # Wait for both workers to come up
    for port in (port_w1, port_w2):
        up = False
        for _ in range(20):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as r:
                    if r.status == 200:
                        up = True
                        break
            except Exception:
                time.sleep(0.5)
        assert up, f"Worker on port {port} failed to start"

    multi_worker_email = "sec08_multi_worker@example.com"
    # Send 3 failed attempts to Worker 1
    for i in range(3):
        req_data = json.dumps({"email": multi_worker_email, "password": f"BadPassW1_{i}"}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{port_w1}/api/auth/login", data=req_data, headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            assert e.code == 401, f"Worker 1 expected 401, got {e.code}"

    # Send 2 failed attempts to Worker 2
    for i in range(2):
        req_data = json.dumps({"email": multi_worker_email, "password": f"BadPassW2_{i}"}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{port_w2}/api/auth/login", data=req_data, headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            assert e.code == 401, f"Worker 2 expected 401, got {e.code}"

    # Total attempts = 5. Now Worker 1 MUST return 429
    req_w1_check = urllib.request.Request(
        f"http://127.0.0.1:{port_w1}/api/auth/login",
        data=json.dumps({"email": multi_worker_email, "password": "FinalWrongPass"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    w1_code = 0
    try:
        urllib.request.urlopen(req_w1_check)
    except urllib.error.HTTPError as e:
        w1_code = e.code
    assert w1_code == 429, f"Worker 1 failed to enforce shared counter, returned HTTP {w1_code}"

    # Worker 2 MUST ALSO return 429
    req_w2_check = urllib.request.Request(
        f"http://127.0.0.1:{port_w2}/api/auth/login",
        data=json.dumps({"email": multi_worker_email, "password": "FinalWrongPass"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    w2_code = 0
    try:
        urllib.request.urlopen(req_w2_check)
    except urllib.error.HTTPError as e:
        w2_code = e.code
    assert w2_code == 429, f"Worker 2 failed to enforce shared counter, returned HTTP {w2_code}"

    print(f"PASS: Two separate OS worker processes (ports {port_w1}, {port_w2}) synchronized counters and enforced 429.")
    passed_tests += 1

finally:
    for proc in (proc_w1, proc_w2):
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


# ============================================================
# SCENARIO 5: Concurrent attempts cannot bypass configured limits
# ============================================================
print("\n--- Test 5: Concurrent attempts cannot bypass configured limits ---")
concurrent_email = "sec08_concurrent@example.com"
login_limiter.reset(f"testclient:{concurrent_email}")
login_limiter.reset("testclient")

def send_login_attempt(idx):
    c = TestClient(app)
    return c.post("/api/auth/login", json={"email": concurrent_email, "password": f"Pass{idx}"})

with ThreadPoolExecutor(max_workers=10) as executor:
    responses = list(executor.map(send_login_attempt, range(15)))

status_codes = [r.status_code for r in responses]
count_401 = status_codes.count(401)
count_429 = status_codes.count(429)

print(f"   Concurrent results: 401={count_401}, 429={count_429}")
assert count_401 == 5, f"Expected exactly 5 failures before lock, got {count_401}"
assert count_429 == 10, f"Expected 10 blocked requests, got {count_429}"
print("PASS: Concurrency test verified atomic serialization with zero bypass.")
passed_tests += 1


# ============================================================
# SCENARIO 6: Expired rate limits reset correctly
# ============================================================
print("\n--- Test 6: Expired rate limits reset correctly ---")
expired_key = "sec08_expired_test_key"
past_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=60)

with engine.begin() as conn:
    conn.execute(
        text("REPLACE INTO rate_limits (rate_key, attempts, first_attempt_at, last_attempt_at, expires_at, created_at, updated_at) "
             "VALUES (:k, 5, :p, :p, :p, :p, :p)"),
        {"k": f"login:{expired_key}", "p": past_time}
    )

# Check limiter: should NOT be rate limited because window expired
assert not login_limiter.is_rate_limited_key(expired_key), "Expired key was incorrectly marked as rate-limited"
assert login_limiter.get_remaining_seconds(expired_key) == 0, "Expired key had non-zero remaining seconds"

# Recording a new attempt should reset attempts counter to 1
new_count = login_limiter._backend.record_attempt(expired_key, window_seconds=300)
assert new_count == 1, f"Expected attempts to reset to 1 after expiration, got {new_count}"
print("PASS: Expired rate limit reset correctly to 1 attempt.")
passed_tests += 1


# ============================================================
# SCENARIO 7: Different account identifiers are handled appropriately
# ============================================================
print("\n--- Test 7: Different account identifiers handled appropriately ---")
acc_a = "sec08_target_a@example.com"
acc_b = "sec08_target_b@example.com"
client_ip_test = "192.0.2.55"

# Register account B
client.post("/api/auth/register", json={
    "name": "Target Account B",
    "email": acc_b,
    "password": "SecureK3y!987#xyz",
    "company": "B Corp"
})

# Lock account A for this IP
key_a = f"{client_ip_test}:{acc_a}"
key_b = f"{client_ip_test}:{acc_b}"
login_limiter.reset(key_a)
login_limiter.reset(key_b)

for _ in range(5):
    login_limiter.record_failure(key_a)

assert login_limiter.is_rate_limited_key(key_a), "Account A should be rate limited"
assert not login_limiter.is_rate_limited_key(key_b), "Account B should NOT be rate limited"

print("PASS: Account A lockout does not affect Account B.")
passed_tests += 1


# ============================================================
# SCENARIO 8: Different IP addresses are handled appropriately
# ============================================================
print("\n--- Test 8: Different IP addresses handled appropriately ---")
shared_acc = "sec08_shared_account@example.com"
ip_attacker = "198.51.100.99"
ip_legitimate = "203.0.113.11"

key_attacker = f"{ip_attacker}:{shared_acc}"
key_legitimate = f"{ip_legitimate}:{shared_acc}"

login_limiter.reset(key_attacker)
login_limiter.reset(key_legitimate)

# Attacker fails 5 times
for _ in range(5):
    login_limiter.record_failure(key_attacker)

assert login_limiter.is_rate_limited_key(key_attacker), "Attacker IP should be locked"
assert not login_limiter.is_rate_limited_key(key_legitimate), "Legitimate IP should NOT be locked"
print("PASS: Brute force from IP 1 does not lock out legitimate user on IP 2.")
passed_tests += 1


# ============================================================
# SCENARIO 9: Spoofed forwarding headers cannot bypass rate limits
# ============================================================
print("\n--- Test 9: Spoofed forwarding headers cannot bypass rate limits ---")
untrusted_client = TestClient(app, client=("203.0.113.44", 50000))
spoof_email = "sec08_spoof_victim@example.com"

# Untrusted client sends 5 failed attempts with fake X-Forwarded-For: 1.1.1.1
for i in range(5):
    res = untrusted_client.post(
        "/api/auth/login",
        json={"email": spoof_email, "password": f"Pass_{i}"},
        headers={"X-Forwarded-For": "1.1.1.1"}
    )
    assert res.status_code == 401

# Attempt 6 tries to forge a new IP: X-Forwarded-For: 2.2.2.2
res_spoof_bypass = untrusted_client.post(
    "/api/auth/login",
    json={"email": spoof_email, "password": "TryBypassWithNewIP"},
    headers={"X-Forwarded-For": "2.2.2.2"}
)

assert res_spoof_bypass.status_code == 429, f"Spoofed XFF bypassed rate limit! Got {res_spoof_bypass.status_code}"
print("PASS: Spoofed X-Forwarded-For headers from untrusted connection correctly ignored.")
passed_tests += 1


# ============================================================
# SCENARIO 10: HTTP 429 and Retry-After responses work correctly
# ============================================================
print("\n--- Test 10: HTTP 429 and Retry-After responses work correctly ---")
# Check res_spoof_bypass headers from Test 9
retry_after = res_spoof_bypass.headers.get("Retry-After")
assert retry_after is not None, "Retry-After header missing from 429 response"
retry_int = int(retry_after)
assert 1 <= retry_int <= 300, f"Retry-After should be between 1 and 300, got {retry_int}"

body = res_spoof_bypass.json()
assert "detail" in body
assert "Too many" in body["detail"]
print(f"PASS: HTTP 429 returned with valid Retry-After: {retry_after} seconds.")
passed_tests += 1


# ============================================================
# SCENARIO 11: Legitimate users are not permanently locked out
# ============================================================
print("\n--- Test 11: Legitimate users are not permanently locked out ---")
unblock_email = "sec08_unblock_user@example.com"
unblock_pass = "X9#kL!vP2$wZ8@mQ"

reg_res = client.post("/api/auth/register", json={
    "name": "Robert Taylor",
    "email": unblock_email,
    "password": unblock_pass,
    "company": "Unblock Inc"
})
assert reg_res.status_code == 200, f"Registration failed: {reg_res.text}"

# Force 5 failures
for i in range(5):
    client.post("/api/auth/login", json={"email": unblock_email, "password": "BadPassword"})

# Confirm locked
res_locked = client.post("/api/auth/login", json={"email": unblock_email, "password": "BadPassword"})
assert res_locked.status_code == 429

# Reset lockout via reset() or window expiration
rate_key_unblock = f"testclient:{unblock_email}"
login_limiter.reset(rate_key_unblock)
login_limiter.reset("testclient")

# Now authenticating with correct password MUST succeed
res_recovered = client.post("/api/auth/login", json={"email": unblock_email, "password": unblock_pass})
assert res_recovered.status_code == 200, f"Recovered login failed: {res_recovered.text}"
print("PASS: Legitimate user recovered and authenticated successfully.")
passed_tests += 1


# ============================================================
# SCENARIO 12: Expired rate-limit records are cleaned safely
# ============================================================
print("\n--- Test 12: Expired rate-limit records are cleaned safely ---")
limiter_test = DistributedRateLimiter(prefix="cleanup_test")
now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
past = now_utc - timedelta(hours=1)
future = now_utc + timedelta(hours=1)

with engine.begin() as conn:
    # Insert 5 expired records
    for i in range(5):
        conn.execute(
            text("REPLACE INTO rate_limits (rate_key, attempts, first_attempt_at, last_attempt_at, expires_at, created_at, updated_at) "
                 "VALUES (:k, 1, :p, :p, :p, :p, :p)"),
            {"k": f"cleanup_test:expired_{i}", "p": past}
        )
    # Insert 2 active records
    for i in range(2):
        conn.execute(
            text("REPLACE INTO rate_limits (rate_key, attempts, first_attempt_at, last_attempt_at, expires_at, created_at, updated_at) "
                 "VALUES (:k, 1, :n, :n, :f, :n, :n)"),
            {"k": f"cleanup_test:active_{i}", "n": now_utc, "f": future}
        )

deleted = limiter_test.cleanup_expired(limit=10)
assert deleted >= 5, f"Expected at least 5 expired rows deleted, got {deleted}"

with engine.connect() as conn:
    active_count = conn.execute(
        text("SELECT COUNT(*) FROM rate_limits WHERE rate_key LIKE 'cleanup_test:active_%'")
    ).scalar()
assert active_count == 2, f"Active records were erroneously deleted: {active_count}"

print(f"PASS: Bounded cleanup safely purged {deleted} expired records and preserved active records.")
passed_tests += 1


# ============================================================
# SCENARIO 13: Database failures do not silently disable protection
# ============================================================
print("\n--- Test 13: Database failures do not silently disable protection (Fail-Secure) ---")
fail_secure_limiter = DistributedRateLimiter(prefix="fail_test", max_attempts=3, window_seconds=60)
mock_fail_key = "simulate_db_crash_user"

# Mock engine.connect and engine.begin to simulate database outage
with patch("backend.rate_limiter.engine.connect", side_effect=Exception("Database connection failure [WinError 10061]")):
    with patch("backend.rate_limiter.engine.begin", side_effect=Exception("Database connection failure [WinError 10061]")):
        # Record attempts under simulated outage
        for _ in range(3):
            fail_secure_limiter.record_attempt(mock_fail_key)

        # Check limit under simulated outage
        blocked = fail_secure_limiter.is_rate_limited(mock_fail_key, threshold=3)
        rem = fail_secure_limiter.get_remaining_seconds(mock_fail_key, threshold=3)

        assert blocked, "FAIL-OPEN DETECTED! Database outage allowed rate limit bypass!"
        assert rem > 0, "Remaining seconds was 0 during fallback lockout"

print("PASS: Database failure engaged in-memory fail-secure fallback; rate limiting remained active.")
passed_tests += 1


# ============================================================
# SCENARIO 14: No permanent test-data contamination occurs
# ============================================================
print("\n--- Test 14: No permanent test-data contamination occurs ---")
cleanup_test_artifacts()

with engine.connect() as conn:
    remaining_rl = conn.execute(text("SELECT COUNT(*) FROM rate_limits WHERE rate_key LIKE '%sec08%' OR rate_key LIKE '%test%'")).scalar()
    remaining_users = conn.execute(text("SELECT COUNT(*) FROM users WHERE email LIKE '%sec08%'")).scalar()

assert remaining_rl == 0, f"Found {remaining_rl} contaminated rate_limit records"
assert remaining_users == 0, f"Found {remaining_users} contaminated user records"
print("PASS: All test records and rate limit keys cleaned up completely.")
passed_tests += 1


# ============================================================
# SCENARIO 15: Existing login and registration remain functional
# ============================================================
print("\n--- Test 15: Existing login and registration remain functional ---")
legit_email = "clean_legit_user@example.com"
legit_pass = "P@ssw0rdSecure!999#"

# Register
reg_res = client.post("/api/auth/register", json={
    "name": "Alexander Wright",
    "email": legit_email,
    "password": legit_pass,
    "company": "Clean Legit Corp"
})
assert reg_res.status_code == 200, f"Clean registration failed: {reg_res.text}"

# Login
log_res = client.post("/api/auth/login", json={
    "email": legit_email,
    "password": legit_pass
})
assert log_res.status_code == 200, f"Clean login failed: {log_res.text}"
user_info = log_res.json()["user"]
assert user_info["email"] == legit_email
assert "session_token" in log_res.cookies

# Rate limit diagnostic endpoint
status_res = client.get(f"/api/auth/rate-limit-status?email={legit_email}")
assert status_res.status_code == 200
status_data = status_res.json()
assert "ip_rate_limit" in status_data
assert "account_rate_limit" in status_data

# Clean up legit test user
with engine.begin() as conn:
    conn.execute(text("DELETE FROM user_sessions WHERE user_id = :uid"), {"uid": user_info["id"]})
    conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_info["id"]})

print("PASS: Core authentication, session issuance, and rate limit diagnostics fully functional.")
passed_tests += 1

print("\n" + "=" * 75)
print(f"ALL SEC-08 TESTS PASSED: {passed_tests} / {total_tests}")
print("=" * 75)
