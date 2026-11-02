"""
Diagnostic script: Reproduce and analyze the rate-limiter lockout issue.
Tests the exact sequence that causes the "Too many failed login attempts" error.
"""
import urllib.request
import urllib.error
import http.cookiejar
import json

BASE_URL = "http://127.0.0.1:8000"

class Client:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def post(self, path, data):
        body = json.dumps(data).encode()
        req = urllib.request.Request(f"{BASE_URL}{path}", data=body, headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(req) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())


def main():
    print("=" * 70)
    print("RATE LIMITER DIAGNOSTIC")
    print("=" * 70)

    # --- Scenario 1: The security test suite triggers rate limiting ---
    # The verify_security_suite.py sends 5 wrong-password attempts to
    # "bruteforce.target@bizops.in" (a nonexistent user) from 127.0.0.1.
    #
    # Each failure records TWO keys:
    #   1. rate_key = "127.0.0.1:bruteforce.target@bizops.in"
    #   2. client_ip = "127.0.0.1"
    #
    # After 5 failures, the IP key "127.0.0.1" has 10 recorded failures
    # (2 per attempt: rate_key + client_ip). Wait -- let me check: each
    # attempt records to rate_key AND to client_ip. So:
    #
    # Attempt 1: rate_key gets 1 failure, client_ip gets 1 failure
    # Attempt 2: rate_key gets 2 failures, client_ip gets 2 failures
    # ...
    # Attempt 5: rate_key gets 5 failures, client_ip gets 5 failures
    #
    # At this point, client_ip "127.0.0.1" has 5 failures >= max_attempts(5).
    # So ANY login from 127.0.0.1 is now blocked for 5 minutes!
    #
    # The verify_security_suite.py Test 9 intentionally triggers this,
    # but it never RESETS the IP-level lockout afterward.

    print()
    print("REPRODUCING: 5 failed logins with wrong passwords from 127.0.0.1")
    client = Client()
    for i in range(5):
        st, body = client.post("/api/auth/login", {
            "email": "bruteforce.target@bizops.in",
            "password": f"wrong_{i}"
        })
        print(f"  Attempt {i+1}: HTTP {st} - {body.get('detail', '')}")

    print()
    print("NOW: Trying a VALID login from same IP (127.0.0.1)...")
    st, body = client.post("/api/auth/login", {
        "email": "security.officer@bizops.in",
        "password": "SecurePassword2026!"
    })
    print(f"  Result: HTTP {st} - {body.get('detail', body.get('status', ''))}")

    if st == 429:
        print()
        print(">>> ROOT CAUSE CONFIRMED <<<")
        print("The IP-level rate limiter (key='127.0.0.1') is blocking ALL")
        print("login attempts from localhost after any test or user triggers")
        print("5 failures -- even for completely different email addresses.")
        print()
        print("In development, ALL requests come from 127.0.0.1 (or the")
        print("Vite proxy), so a single brute-force test locks out EVERY user.")
        print()
        print("The verify_security_suite.py Test 9 triggers exactly this,")
        print("and does NOT reset the IP-level counter afterward.")
    else:
        print("  (Rate limiter has expired or was reset -- not currently blocked)")

    print()
    print("=" * 70)

if __name__ == "__main__":
    main()
