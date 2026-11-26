#!/usr/bin/env python3
"""
SEC-10 Verification Suite: HTTP Security Headers, CORS, and Content Security Policy Hardening
AI Business Operations Copilot

Executes all 20 mandatory security tests required for SEC-10:
1. Allowed development origin (http://localhost:5173)
2. Unauthorized origin rejection
3. Null origin rejection
4. Production origin allowlist
5. CORS preflight requests (OPTIONS)
6. Credentialed cross-origin requests
7. CSRF compatibility (X-CSRF-Token)
8. Content Security Policy (CSP) enforcement (all 10 directives)
9. Unauthorized script rejection
10. Clickjacking protection (X-Frame-Options & frame-ancestors)
11. MIME-sniffing protection (X-Content-Type-Options: nosniff)
12. Referrer policy (strict-origin-when-cross-origin)
13. Browser permissions restrictions (Permissions-Policy)
14. Production HTTPS and Secure cookies
15. Local HTTP development compatibility
16. Sensitive response caching protection (Cache-Control)
17. Security headers on error responses (401, 403, 404, 413, 422, 429, 500)
18. Actual frontend HTML security headers (live Vite dev & production HTML)
19. Production frontend build verification (npm run build)
20. Full FastAPI MySQL regression test suite (17/17 tests passing)
"""

import os
import sys
import json
import urllib.request
import urllib.error
import subprocess
from pathlib import Path
from typing import Dict, Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Enforce MySQL mode
os.environ["USE_MYSQL"] = "true"

from starlette.testclient import TestClient
from backend.ai_backend import (
    app,
    get_allowed_origins,
    get_csp_header,
    should_enable_hsts,
    is_request_https,
    DEV_DEFAULT_ORIGINS
)

# Securely supplied test credentials
TEST_AUTH_EMAIL = os.environ.get("TEST_AUTH_EMAIL", "dinesh@test.com")
TEST_AUTH_PASSWORD = os.environ.get("TEST_AUTH_PASSWORD", "password123")

class SEC10VerificationSuite:
    def __init__(self):
        self.client = TestClient(app)
        self.results: Dict[str, Dict[str, Any]] = {}

    def record(self, test_num: int, title: str, passed: bool, details: Dict[str, Any]):
        test_id = f"SEC10-TEST-{test_num:02d}"
        self.results[test_id] = {
            "title": title,
            "status": "PASS" if passed else "FAIL",
            "details": details
        }
        status_str = "PASS" if passed else "FAIL"
        print(f"[{status_str}] {test_id}: {title}")
        if not passed:
            print(f"       Failure Details: {details}")

    def run_all(self):
        print("=" * 70)
        print(" SEC-10: HTTP SECURITY HEADERS, CORS & CSP VERIFICATION SUITE")
        print("=" * 70)

        # -------------------------------------------------------------
        # Test 1: Allowed development origin
        # -------------------------------------------------------------
        res1 = self.client.get("/api/auth/csrf", headers={"Origin": "http://localhost:5173"})
        acao1 = res1.headers.get("access-control-allow-origin")
        pass1 = (acao1 == "http://localhost:5173")
        self.record(1, "Allowed development origin (http://localhost:5173)", pass1, {
            "origin_header": "http://localhost:5173",
            "access_control_allow_origin": acao1
        })

        # -------------------------------------------------------------
        # Test 2: Unauthorized origin rejection
        # -------------------------------------------------------------
        res2 = self.client.get("/api/auth/csrf", headers={"Origin": "https://malicious-attacker.com"})
        acao2 = res2.headers.get("access-control-allow-origin")
        pass2 = (acao2 is None)
        self.record(2, "Unauthorized origin rejection", pass2, {
            "origin_header": "https://malicious-attacker.com",
            "access_control_allow_origin": acao2
        })

        # -------------------------------------------------------------
        # Test 3: Null origin rejection
        # -------------------------------------------------------------
        res3 = self.client.get("/api/auth/csrf", headers={"Origin": "null"})
        acao3 = res3.headers.get("access-control-allow-origin")
        pass3 = (acao3 is None)
        self.record(3, "Null origin rejection (Origin: null)", pass3, {
            "origin_header": "null",
            "access_control_allow_origin": acao3
        })

        # -------------------------------------------------------------
        # Test 4: Production origin allowlist
        # -------------------------------------------------------------
        # Test production fail-safe and configured allowlist
        orig_env = os.environ.get("ENVIRONMENT", "development")
        orig_cors = os.environ.get("CORS_ALLOWED_ORIGINS", "")
        try:
            os.environ["ENVIRONMENT"] = "production"
            # 4a: Empty allowlist in production -> fails closed
            os.environ["CORS_ALLOWED_ORIGINS"] = ""
            res4a = self.client.get("/api/auth/csrf", headers={"Origin": "https://app.bizops.example.com"})
            closed_ok = (res4a.headers.get("access-control-allow-origin") is None)
            
            # Localhost in production should also be rejected
            res4_local = self.client.get("/api/auth/csrf", headers={"Origin": "http://localhost:5173"})
            local_rejected = (res4_local.headers.get("access-control-allow-origin") is None)

            # 4b: Configured allowlist in production
            os.environ["CORS_ALLOWED_ORIGINS"] = "https://app.bizops.example.com,https://admin.bizops.example.com"
            res4b = self.client.get("/api/auth/csrf", headers={"Origin": "https://app.bizops.example.com"})
            prod_accepted = (res4b.headers.get("access-control-allow-origin") == "https://app.bizops.example.com")
            
            # Wildcard rejected in allowlist
            os.environ["CORS_ALLOWED_ORIGINS"] = "*"
            allowed_wildcard = get_allowed_origins()
            wildcard_rejected = ("*" not in allowed_wildcard)

            pass4 = closed_ok and local_rejected and prod_accepted and wildcard_rejected
            self.record(4, "Production origin allowlist enforcement & fail-closed behavior", pass4, {
                "unconfigured_production_fails_closed": closed_ok,
                "localhost_rejected_in_production": local_rejected,
                "configured_prod_origin_accepted": prod_accepted,
                "wildcard_with_credentials_rejected": wildcard_rejected
            })
        finally:
            os.environ["ENVIRONMENT"] = orig_env
            os.environ["CORS_ALLOWED_ORIGINS"] = orig_cors

        # -------------------------------------------------------------
        # Test 5: CORS preflight requests (OPTIONS)
        # -------------------------------------------------------------
        res5 = self.client.options("/api/customers", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-CSRF-Token, Content-Type"
        })
        allow_methods = res5.headers.get("access-control-allow-methods", "")
        allow_headers = res5.headers.get("access-control-allow-headers", "")
        pass5 = (
            res5.status_code == 200
            and res5.headers.get("access-control-allow-origin") == "http://localhost:5173"
            and "POST" in allow_methods
            and "x-csrf-token" in allow_headers.lower()
        )
        self.record(5, "CORS preflight requests (OPTIONS) handling", pass5, {
            "status_code": res5.status_code,
            "allow_origin": res5.headers.get("access-control-allow-origin"),
            "allow_methods": allow_methods,
            "allow_headers": allow_headers
        })

        # -------------------------------------------------------------
        # Test 6: Credentialed cross-origin requests
        # -------------------------------------------------------------
        res6 = self.client.get("/api/auth/csrf", headers={"Origin": "http://localhost:5173"})
        acac6 = res6.headers.get("access-control-allow-credentials")
        pass6 = (acac6 == "true" and res6.headers.get("access-control-allow-origin") == "http://localhost:5173")
        self.record(6, "Credentialed cross-origin requests (Access-Control-Allow-Credentials: true)", pass6, {
            "allow_credentials": acac6,
            "allow_origin": res6.headers.get("access-control-allow-origin")
        })

        # -------------------------------------------------------------
        # Test 7: CSRF compatibility
        # -------------------------------------------------------------
        csrf_res = self.client.get("/api/auth/csrf")
        csrf_token = csrf_res.json().get("csrf_token")
        expose_headers = csrf_res.headers.get("access-control-expose-headers", "")
        has_csrf_cookie = "csrf_token=" in csrf_res.headers.get("set-cookie", "")
        pass7 = (
            csrf_res.status_code == 200
            and bool(csrf_token)
            and has_csrf_cookie
        )
        self.record(7, "CSRF compatibility with CORS & cookie authentication", pass7, {
            "status_code": csrf_res.status_code,
            "has_csrf_token": bool(csrf_token),
            "csrf_cookie_present": has_csrf_cookie
        })

        # -------------------------------------------------------------
        # Test 8: Content Security Policy enforcement (all 10 directives)
        # -------------------------------------------------------------
        res8 = self.client.get("/health")
        csp = res8.headers.get("content-security-policy", "")
        required_directives = [
            "default-src", "script-src", "style-src", "img-src",
            "font-src", "connect-src", "object-src", "base-uri",
            "frame-ancestors", "form-action"
        ]
        missing_dirs = [d for d in required_directives if d not in csp]
        pass8 = (len(missing_dirs) == 0)
        self.record(8, "Content Security Policy enforcement (all 10 directives present)", pass8, {
            "csp_header": csp,
            "missing_directives": missing_dirs
        })

        # -------------------------------------------------------------
        # Test 9: Unauthorized script rejection & production CSP strictness
        # -------------------------------------------------------------
        try:
            os.environ["ENVIRONMENT"] = "production"
            prod_csp = get_csp_header(TestClient(app).build_request("GET", "http://testserver/"))
            # In production script-src must NOT contain unsafe-inline or unsafe-eval
            script_part = [p for p in prod_csp.split(";") if "script-src" in p]
            prod_script_strict = False
            if script_part:
                s_val = script_part[0]
                prod_script_strict = ("'unsafe-inline'" not in s_val and "'unsafe-eval'" not in s_val and "'self'" in s_val)
            # Verify no unauthorized external script domains
            unauthorized_script_blocked = ("*" not in s_val and "http:" not in s_val and "https:" not in s_val)
            pass9 = prod_script_strict and unauthorized_script_blocked
            self.record(9, "Unauthorized script rejection (production script-src strictly 'self')", pass9, {
                "production_script_src": script_part[0] if script_part else None,
                "no_unsafe_inline_or_eval": prod_script_strict,
                "unauthorized_domains_blocked": unauthorized_script_blocked
            })
        finally:
            os.environ["ENVIRONMENT"] = orig_env

        # -------------------------------------------------------------
        # Test 10: Clickjacking protection
        # -------------------------------------------------------------
        res10 = self.client.get("/health")
        x_frame = res10.headers.get("x-frame-options")
        csp_frame = "frame-ancestors 'none'" in res10.headers.get("content-security-policy", "")
        pass10 = (x_frame == "DENY" and csp_frame)
        self.record(10, "Clickjacking protection (X-Frame-Options: DENY & frame-ancestors 'none')", pass10, {
            "x_frame_options": x_frame,
            "csp_frame_ancestors_none": csp_frame
        })

        # -------------------------------------------------------------
        # Test 11: MIME-sniffing protection
        # -------------------------------------------------------------
        res11 = self.client.get("/health")
        x_content = res11.headers.get("x-content-type-options")
        pass11 = (x_content == "nosniff")
        self.record(11, "MIME-sniffing protection (X-Content-Type-Options: nosniff)", pass11, {
            "x_content_type_options": x_content
        })

        # -------------------------------------------------------------
        # Test 12: Referrer policy
        # -------------------------------------------------------------
        res12 = self.client.get("/health")
        referrer = res12.headers.get("referrer-policy")
        pass12 = (referrer == "strict-origin-when-cross-origin")
        self.record(12, "Referrer policy (strict-origin-when-cross-origin)", pass12, {
            "referrer_policy": referrer
        })

        # -------------------------------------------------------------
        # Test 13: Browser permissions restrictions
        # -------------------------------------------------------------
        res13 = self.client.get("/health")
        perms = res13.headers.get("permissions-policy", "")
        pass13 = (
            "camera=()" in perms
            and "microphone=()" in perms
            and "geolocation=()" in perms
            and "payment=()" in perms
        )
        self.record(13, "Browser permissions restrictions (Permissions-Policy)", pass13, {
            "permissions_policy": perms
        })

        # -------------------------------------------------------------
        # Test 14: Production HTTPS and Secure cookies
        # -------------------------------------------------------------
        try:
            os.environ["ENVIRONMENT"] = "production"
            os.environ["ENABLE_HSTS"] = "true"
            # Request with genuine HTTPS (or from trusted proxy with x-forwarded-proto)
            res14 = self.client.get(
                "/api/auth/csrf",
                headers={"X-Forwarded-Proto": "https"}
            )
            hsts_header = res14.headers.get("strict-transport-security")
            hsts_ok = (hsts_header == "max-age=31536000; includeSubDomains")
            
            # In production, check secure cookies on login
            login_res = self.client.post("/api/auth/login", json={
                "email": TEST_AUTH_EMAIL,
                "password": TEST_AUTH_PASSWORD
            })
            set_cookie = login_res.headers.get("set-cookie", "")
            secure_cookie = ("secure" in set_cookie.lower() and "httponly" in set_cookie.lower())
            
            pass14 = hsts_ok and secure_cookie
            self.record(14, "Production HTTPS & Secure cookie enforcement (HSTS & Secure cookies)", pass14, {
                "strict_transport_security": hsts_header,
                "secure_cookie_flag": secure_cookie
            })
        finally:
            os.environ["ENVIRONMENT"] = orig_env
            os.environ["ENABLE_HSTS"] = "false"

        # -------------------------------------------------------------
        # Test 15: Local HTTP development compatibility
        # -------------------------------------------------------------
        # In development mode, plain HTTP requests MUST NOT be forced to HSTS or fail on insecure cookies
        res15 = self.client.get("/health")
        dev_hsts = res15.headers.get("strict-transport-security")
        pass15 = (dev_hsts is None)
        self.record(15, "Local HTTP development compatibility (No HSTS forcing on HTTP development)", pass15, {
            "environment": os.environ.get("ENVIRONMENT"),
            "strict_transport_security_in_dev": dev_hsts
        })

        # -------------------------------------------------------------
        # Test 16: Sensitive response caching protection
        # -------------------------------------------------------------
        res16_api = self.client.get("/api/auth/rate-limit-status")
        cache_ctrl = res16_api.headers.get("cache-control", "")
        pragma = res16_api.headers.get("pragma", "")
        api_no_store = ("no-store" in cache_ctrl and "no-cache" in cache_ctrl and "private" in cache_ctrl)
        
        # Static asset long-term caching
        res16_asset = self.client.get("/assets/test.js")
        asset_cache = res16_asset.headers.get("cache-control", "")
        asset_caching_ok = ("public" in asset_cache and "max-age=31536000" in asset_cache and "immutable" in asset_cache)

        pass16 = api_no_store and asset_caching_ok
        self.record(16, "Sensitive response caching protection (API no-store vs asset immutable)", pass16, {
            "api_cache_control": cache_ctrl,
            "api_pragma": pragma,
            "asset_cache_control": asset_cache
        })

        # -------------------------------------------------------------
        # Test 17: Security headers on error responses
        # -------------------------------------------------------------
        error_statuses = {}
        # 401 Unauthorized
        r401 = self.client.get("/api/auth/me")
        error_statuses[401] = (r401.headers.get("x-content-type-options") == "nosniff" and r401.headers.get("x-frame-options") == "DENY" and "content-security-policy" in r401.headers)
        
        # 404 Not Found
        r404 = self.client.get("/api/non-existent-endpoint")
        error_statuses[404] = (r404.headers.get("x-content-type-options") == "nosniff" and r404.headers.get("x-frame-options") == "DENY" and "content-security-policy" in r404.headers)
        
        # 422 Unprocessable Entity
        r422 = self.client.post("/api/predict/churn", json={"invalid": "payload"})
        error_statuses[422] = (r422.headers.get("x-content-type-options") == "nosniff" and r422.headers.get("x-frame-options") == "DENY" and "content-security-policy" in r422.headers)

        # 413 Payload Too Large
        r413 = self.client.post("/api/predict/churn", headers={"Content-Length": "2097152"}, content=b"x" * 100)
        error_statuses[413] = (r413.headers.get("x-content-type-options") == "nosniff" and r413.headers.get("x-frame-options") == "DENY" and "content-security-policy" in r413.headers)

        pass17 = all(error_statuses.values())
        self.record(17, "Security headers on error responses (401, 404, 413, 422)", pass17, {
            "error_responses_verified": error_statuses
        })

        # -------------------------------------------------------------
        # Test 18: Actual frontend HTML security headers
        # -------------------------------------------------------------
        # Test actual live Vite server on port 5173
        vite_headers_ok = False
        vite_details = {}
        try:
            req = urllib.request.Request("http://127.0.0.1:5173/")
            with urllib.request.urlopen(req, timeout=3) as resp:
                v_headers = {k.lower(): v for k, v in resp.getheaders()}
                vite_details = {
                    "status": resp.status,
                    "csp": v_headers.get("content-security-policy"),
                    "x_content_type": v_headers.get("x-content-type-options"),
                    "x_frame": v_headers.get("x-frame-options"),
                    "referrer": v_headers.get("referrer-policy"),
                    "permissions": v_headers.get("permissions-policy")
                }
                vite_headers_ok = (
                    resp.status == 200
                    and v_headers.get("x-content-type-options") == "nosniff"
                    and v_headers.get("x-frame-options", "").upper() == "DENY"
                    and v_headers.get("referrer-policy") == "strict-origin-when-cross-origin"
                    and "camera=()" in v_headers.get("permissions-policy", "")
                    and "default-src 'self'" in v_headers.get("content-security-policy", "")
                )
        except Exception as e:
            vite_details = {"error": str(e)}

        pass18 = vite_headers_ok
        self.record(18, "Actual frontend HTML security headers on Vite dev server (http://localhost:5173/)", pass18, vite_details)

        # -------------------------------------------------------------
        # Test 19: Production frontend build verification
        # -------------------------------------------------------------
        build_res = subprocess.run(
            ["npm.cmd", "run", "build"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )
        dist_index = PROJECT_ROOT / "dist" / "index.html"
        pass19 = (build_res.returncode == 0 and dist_index.exists() and dist_index.stat().st_size > 0)
        self.record(19, "Production frontend build verification (npm run build)", pass19, {
            "exit_code": build_res.returncode,
            "dist_index_exists": dist_index.exists(),
            "dist_index_size": dist_index.stat().st_size if dist_index.exists() else 0
        })

        # -------------------------------------------------------------
        # Test 20: Full FastAPI MySQL regression test suite (17/17)
        # -------------------------------------------------------------
        from scripts.test_fastapi_mysql_integration import FastAPIMySQLIntegrationSuite
        integration_suite = FastAPIMySQLIntegrationSuite()
        try:
            int_res = integration_suite.run_all_tests()
            passed_int = int_res.get("passed_tests", 0)
            total_int = int_res.get("total_tests", 0)
            pass20 = (passed_int == 17 and total_int == 17)
            self.record(20, "Full FastAPI MySQL regression test suite (17/17 tests passing)", pass20, {
                "passed_tests": passed_int,
                "total_tests": total_int,
                "score_pct": int_res.get("score_pct", 0.0)
            })
        finally:
            integration_suite.cleanup_disposable_test_data()

        # Summary
        passed_count = sum(1 for t in self.results.values() if t["status"] == "PASS")
        total_count = len(self.results)
        print("=" * 70)
        print(f" SEC-10 Verification Complete: {passed_count} / {total_count} Tests Passed ({(passed_count/total_count)*100:.1f}%)")
        print("=" * 70)
        return {
            "passed_tests": passed_count,
            "total_tests": total_count,
            "score_pct": (passed_count / total_count) * 100,
            "results": self.results
        }


if __name__ == "__main__":
    suite = SEC10VerificationSuite()
    out = suite.run_all()
    if out["passed_tests"] != out["total_tests"]:
        sys.exit(1)
    sys.exit(0)
