#!/usr/bin/env python3
"""
SEC-13 Comprehensive Security & Concurrency Verification Suite:
Invoice ID Collision Protection and Tenant-Safe Invoice Generation
AI Business Operations Copilot

Covers all 20 mandatory verification scenarios:
1.  Normal invoice creation
2.  Server-generated internal identifiers
3.  Rejection / safe ignoring of client-supplied internal identifiers & user_id
4.  Two separate businesses creating invoices with identical business-facing numbers
5.  Duplicate invoice numbers within the same business (HTTP 409)
6.  Concurrent invoice creation for one business
7.  Concurrent invoice creation across multiple businesses
8.  Invoice creation across separate OS backend workers (multiprocessing)
9.  Cross-tenant invoice access denial (GET / PUT / PATCH / DELETE / PDF)
10. Cross-tenant customer references rejected
11. Cross-tenant product references rejected
12. Duplicate submission protection (idempotency_key / X-Idempotency-Key)
13. Transaction rollback during invoice creation failure (stock/items/customer atomicity)
14. Invoice items consistency & zero orphans
15. Atomic inventory deduction consistency under concurrent load
16. Correct HTTP 409 conflict & HTTP 422 validation & HTTP 500 separation
17. Existing invoice editing (PUT / PATCH) & permitted deletion without number reuse
18. Actual PDF generation and download (PyMuPDF binary & invoice_number content)
19. Genuine frontend browser invoice creation workflow via CDP (http://localhost:5173/)
20. Before-and-after financial data integrity (545 records, ₹14,245,982.00 sum)
"""

import os
import sys
import re
import json
import time
import asyncio
import tempfile
import subprocess
import urllib.request
import multiprocessing
import concurrent.futures
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

# Enforce MySQL mode
os.environ["USE_MYSQL"] = "true"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _mp_worker_create_invoice(task_args):
    """Top-level multiprocessing worker running inside an independent OS process."""
    token, csrf_tok, cust_id, prod_id, custom_inv_num = task_args
    os.environ["USE_MYSQL"] = "true"
    sys.path.insert(0, str(PROJECT_ROOT))
    from starlette.testclient import TestClient
    from backend.ai_backend import app

    client = TestClient(app, base_url="http://testserver")
    payload = {
        "customer_id": cust_id,
        "status": "Pending",
        "tax": 18.0,
        "discount": 0.0,
        "line_items": [{"product_id": prod_id, "quantity": 1}]
    }
    if custom_inv_num:
        payload["invoice_number"] = custom_inv_num

    res = client.post(
        "/api/invoices",
        json=payload,
        cookies={"session_token": token},
        headers={"X-CSRF-Token": csrf_tok}
    )
    body = {}
    try:
        body = res.json()
    except Exception:
        pass
    return {
        "pid": os.getpid(),
        "status": res.status_code,
        "id": body.get("id"),
        "invoice_number": body.get("invoice_number"),
        "detail": body.get("detail")
    }


def find_browser():
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError("No Chromium-based browser found on host system.")


class SEC13VerificationSuite:
    def __init__(self):
        from starlette.testclient import TestClient
        from backend.ai_backend import app
        self.app = app
        self.client = TestClient(app, base_url="http://testserver")
        self.test_records = []
        self.disposable_user_ids = []
        self.disposable_emails = []

    def record_test(self, test_id: str, desc: str, passed: bool, detail: str = ""):
        self.test_records.append({
            "id": test_id,
            "desc": desc,
            "passed": passed,
            "detail": detail
        })
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {test_id}: {desc}")
        if detail:
            print(f"       Details: {detail}")

    def _snapshot_baseline(self):
        from backend.database import mysql_engine
        from sqlalchemy import text
        with mysql_engine.connect() as conn:
            return {
                "users": conn.execute(text("SELECT COUNT(*) FROM users")).scalar(),
                "customers": conn.execute(text("SELECT COUNT(*) FROM customers")).scalar(),
                "products": conn.execute(text("SELECT COUNT(*) FROM products")).scalar(),
                "invoices": conn.execute(text("SELECT COUNT(*) FROM invoices")).scalar(),
                "invoice_items": conn.execute(text("SELECT COUNT(*) FROM invoice_items")).scalar(),
                "employees": conn.execute(text("SELECT COUNT(*) FROM employees")).scalar(),
                "legacy_orphans": conn.execute(text("SELECT COUNT(*) FROM legacy_orphans_archive")).scalar(),
                "sum_amount_num": Decimal(str(conn.execute(text("SELECT COALESCE(SUM(amount_num), 0) FROM invoices")).scalar())),
                "paid_revenue": Decimal(str(conn.execute(text("SELECT COALESCE(SUM(amount_num), 0) FROM invoices WHERE LOWER(status) = 'paid'")).scalar())),
                "sum_total": Decimal(str(conn.execute(text("SELECT COALESCE(SUM(total), 0) FROM invoices")).scalar())),
                "orphan_items": conn.execute(text("SELECT COUNT(*) FROM invoice_items ii LEFT JOIN invoices i ON ii.invoice_id = i.id WHERE i.id IS NULL")).scalar(),
                "historical_ids": [r[0] for r in conn.execute(text("SELECT id FROM invoices ORDER BY id")).fetchall()],
            }

    def _create_disposable_tenant(self, tag: str, initial_stock: int = 200):
        from backend.database import get_db
        from backend.ai_backend import hash_password, create_user_session, generate_session_csrf_token

        rand = os.urandom(4).hex()
        email = f"sec13_{tag}_{rand}@disposable.local"
        pw = "StrongSec13TestPW!2026"
        pw_hash = hash_password(pw)
        self.disposable_emails.append(email)

        with get_db() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO users (name, email, password_hash, password, company, biz_type, is_active, is_verified)
                VALUES (?, ?, ?, ?, ?, 'E-commerce', 1, 1)
            """, (f"Sec13 {tag}", email, pw_hash, pw_hash, f"Sec13 {tag} Corp"))
            uid = c.lastrowid
            self.disposable_user_ids.append(uid)

            c.execute("""
                INSERT INTO customers (user_id, name, email, company, status, ltv, total_spend, orders, joined, churn)
                VALUES (?, ?, ?, ?, 'Active', '₹0', 0.00, 0, 'Nov 2026', 0)
            """, (uid, f"Client {tag}", f"client_{tag}_{rand}@disposable.local", f"{tag} Buyer Co"))
            cust_id = c.lastrowid

            c.execute("""
                INSERT INTO products (user_id, name, sku, category, stock, reorder, price, price_num, status, trend)
                VALUES (?, ?, ?, 'Software', ?, 5, '₹10,000', 10000.00, 'In Stock', ?)
            """, (uid, f"Product {tag} Alpha", f"SKU-{tag.upper()}-A-{rand}", initial_stock, "+10%"))
            prod_a_id = c.lastrowid

            c.execute("""
                INSERT INTO products (user_id, name, sku, category, stock, reorder, price, price_num, status, trend)
                VALUES (?, ?, ?, 'Software', 1, 5, '₹5,000', 5000.00, 'Low Stock', ?)
            """, (uid, f"Product {tag} LowStock", f"SKU-{tag.upper()}-B-{rand}", "+5%"))
            prod_b_id = c.lastrowid

            tok = create_user_session(c, uid)
            csrf = generate_session_csrf_token(tok)
            conn.commit()

        return {
            "user_id": uid,
            "email": email,
            "password": pw,
            "company": f"{tag} Buyer Co",
            "customer_id": cust_id,
            "prod_a_id": prod_a_id,
            "prod_b_id": prod_b_id,
            "token": tok,
            "csrf": csrf,
        }

    def _cleanup_all_disposable(self):
        from backend.database import mysql_engine
        from sqlalchemy import text

        # Discover any browser-created disposable users as well
        with mysql_engine.connect() as conn:
            extra_rows = conn.execute(text(
                "SELECT id, email FROM users WHERE email LIKE 'sec13_%@disposable.local' OR email LIKE 'browser_sec13_%@disposable.local'"
            )).fetchall()
            for r in extra_rows:
                if r[0] not in self.disposable_user_ids:
                    self.disposable_user_ids.append(r[0])
                if r[1] not in self.disposable_emails:
                    self.disposable_emails.append(r[1])

            if self.disposable_user_ids:
                for uid in self.disposable_user_ids:
                    conn.execute(text("DELETE FROM invoice_items WHERE user_id = :uid"), {"uid": uid})
                    conn.execute(text("DELETE FROM invoices WHERE user_id = :uid"), {"uid": uid})
                    conn.execute(text("DELETE FROM invoice_sequences WHERE user_id = :uid"), {"uid": uid})
                    conn.execute(text("DELETE FROM products WHERE user_id = :uid"), {"uid": uid})
                    conn.execute(text("DELETE FROM customers WHERE user_id = :uid"), {"uid": uid})
                    conn.execute(text("DELETE FROM business_activities WHERE user_id = :uid"), {"uid": uid})
                    conn.execute(text("DELETE FROM notifications WHERE user_id = :uid"), {"uid": uid})
                    conn.execute(text("DELETE FROM user_sessions WHERE user_id = :uid"), {"uid": uid})
                    conn.execute(text("DELETE FROM concurrency_leases WHERE user_id = :uid"), {"uid": uid})
                    conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": uid})

            for email in self.disposable_emails:
                conn.execute(text("DELETE FROM rate_limits WHERE rate_key LIKE :pat"), {"pat": f"%{email}%"})
            conn.commit()

    def run_all(self):
        import pymupdf
        from backend.database import mysql_engine
        from sqlalchemy import text

        print("=" * 74)
        print(" SEC-13 INVOICE ID COLLISION PROTECTION & TENANT-SAFE NUMBERING")
        print("=" * 74)

        baseline_before = self._snapshot_baseline()
        print(f"Baseline BEFORE: invoices={baseline_before['invoices']}, items={baseline_before['invoice_items']}, sum(amount_num)=₹{baseline_before['sum_amount_num']:,.2f}")

        try:
            tenant_a = self._create_disposable_tenant("tenantA", initial_stock=300)
            tenant_b = self._create_disposable_tenant("tenantB", initial_stock=300)
            tenant_c = self._create_disposable_tenant("tenantC", initial_stock=5)

            # ---------------------------------------------------------
            # TEST-01 & TEST-02: Normal Creation + Server-Generated UUID PK
            # ---------------------------------------------------------
            res_01 = self.client.post(
                "/api/invoices",
                json={
                    "client": tenant_a["company"],
                    "status": "Pending",
                    "tax": 18.0,
                    "discount": 0.0,
                    "line_items": [{"product_id": tenant_a["prod_a_id"], "quantity": 2}]
                },
                cookies={"session_token": tenant_a["token"]},
                headers={"X-CSRF-Token": tenant_a["csrf"]}
            )
            inv_01 = res_01.json()
            ok_01 = (
                res_01.status_code == 200
                and inv_01.get("amount_num") == 23600.0
                and inv_01.get("invoice_number") == "INV-2026-001"
                and len(inv_01.get("line_items", [])) == 1
            )
            ok_02 = (
                isinstance(inv_01.get("id"), str)
                and inv_01["id"].startswith("inv_")
                and len(inv_01["id"]) == 36
                and inv_01["id"] != inv_01["invoice_number"]
            )
            self.record_test("TEST-01", "Normal Invoice Creation & Totals Calculation", ok_01,
                             f"Status: {res_01.status_code}, Number: {inv_01.get('invoice_number')}, Total: {inv_01.get('amount_num')}")
            self.record_test("TEST-02", "Server-Generated Internal UUID Identifier (Separated from Number)", ok_02,
                             f"Internal PK id: {inv_01.get('id')} vs Business Number: {inv_01.get('invoice_number')}")

            # ---------------------------------------------------------
            # TEST-03: Client-Supplied Internal ID & Untrusted user_id Ignored
            # ---------------------------------------------------------
            res_03 = self.client.post(
                "/api/invoices",
                json={
                    "id": "INV-2026-001",  # Untrusted attempt to collide with historical PK!
                    "user_id": 1,          # Untrusted attempt to hijack user_id=1!
                    "customer_id": tenant_b["customer_id"],
                    "status": "Draft",
                    "tax": 0.0,
                    "line_items": [{"product_id": tenant_b["prod_a_id"], "quantity": 1}]
                },
                cookies={"session_token": tenant_b["token"]},
                headers={"X-CSRF-Token": tenant_b["csrf"]}
            )
            inv_03 = res_03.json()
            ok_03 = (
                res_03.status_code == 200
                and inv_03.get("id") != "INV-2026-001"
                and inv_03.get("id", "").startswith("inv_")
                and inv_03.get("user_id") == tenant_b["user_id"]
            )
            self.record_test("TEST-03", "Client-Supplied Internal ID & Untrusted user_id Safely Ignored", ok_03,
                             f"Assigned id: {inv_03.get('id')}, Assigned user_id: {inv_03.get('user_id')}")

            # ---------------------------------------------------------
            # TEST-04: Two Businesses Creating Identical Business Invoice Numbers
            # ---------------------------------------------------------
            shared_num = "INV-2026-001"  # tenant_a already has INV-2026-001 (and user 1 also has historical INV-2026-001)
            # Now tenant_b explicitly requests invoice_number = INV-2026-001? Wait: test 03 auto-generated INV-2026-001 for tenant_b!
            # So let's test custom shared number "FY26-Q4-100" for BOTH tenant_a and tenant_b!
            custom_shared = "FY26-Q4-100"
            r_sh_a = self.client.post(
                "/api/invoices",
                json={"customer_id": tenant_a["customer_id"], "invoice_number": custom_shared, "line_items": [{"product_id": tenant_a["prod_a_id"], "quantity": 1}]},
                cookies={"session_token": tenant_a["token"]},
                headers={"X-CSRF-Token": tenant_a["csrf"]}
            )
            r_sh_b = self.client.post(
                "/api/invoices",
                json={"customer_id": tenant_b["customer_id"], "invoice_number": custom_shared, "line_items": [{"product_id": tenant_b["prod_a_id"], "quantity": 1}]},
                cookies={"session_token": tenant_b["token"]},
                headers={"X-CSRF-Token": tenant_b["csrf"]}
            )
            ok_04 = (
                r_sh_a.status_code == 200
                and r_sh_b.status_code == 200
                and r_sh_a.json()["invoice_number"] == custom_shared
                and r_sh_b.json()["invoice_number"] == custom_shared
                and r_sh_a.json()["id"] != r_sh_b.json()["id"]
                and inv_01["invoice_number"] == "INV-2026-001"
                and inv_03["invoice_number"] == "INV-2026-001"
            )
            self.record_test("TEST-04", "Identical Business Invoice Numbers Allowed Across Different Tenants", ok_04,
                             f"TenantA '{custom_shared}' pk={r_sh_a.json().get('id')}, TenantB '{custom_shared}' pk={r_sh_b.json().get('id')}")

            # ---------------------------------------------------------
            # TEST-05: Duplicate Invoice Number Within Same Business -> HTTP 409
            # ---------------------------------------------------------
            r_dup_a = self.client.post(
                "/api/invoices",
                json={"customer_id": tenant_a["customer_id"], "invoice_number": custom_shared, "line_items": [{"product_id": tenant_a["prod_a_id"], "quantity": 1}]},
                cookies={"session_token": tenant_a["token"]},
                headers={"X-CSRF-Token": tenant_a["csrf"]}
            )
            ok_05 = (
                r_dup_a.status_code == 409
                and "already exists" in r_dup_a.json().get("detail", "").lower()
                and "sql" not in r_dup_a.json().get("detail", "").lower()
                and "uq_" not in r_dup_a.json().get("detail", "").lower()
            )
            self.record_test("TEST-05", "Same-Tenant Duplicate Invoice Number Rejected (HTTP 409 Conflict)", ok_05,
                             f"Status: {r_dup_a.status_code}, Detail: '{r_dup_a.json().get('detail')}'")

            # ---------------------------------------------------------
            # TEST-06 & TEST-07: Concurrent Creation (Single Tenant & Multi-Tenant Threads)
            # ---------------------------------------------------------
            def thread_create(ten):
                from starlette.testclient import TestClient
                c = TestClient(self.app, base_url="http://testserver")
                return c.post(
                    "/api/invoices",
                    json={"customer_id": ten["customer_id"], "line_items": [{"product_id": ten["prod_a_id"], "quantity": 1}]},
                    cookies={"session_token": ten["token"]},
                    headers={"X-CSRF-Token": ten["csrf"]}
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
                futs_single = [ex.submit(thread_create, tenant_a) for _ in range(10)]
                res_single = [f.result() for f in futs_single]

            single_ids = {r.json()["id"] for r in res_single if r.status_code == 200}
            single_nums = {r.json()["invoice_number"] for r in res_single if r.status_code == 200}
            ok_06 = (all(r.status_code == 200 for r in res_single) and len(single_ids) == 10 and len(single_nums) == 10)
            self.record_test("TEST-06", "Concurrent Invoice Creation for One Business (Zero Races/500s)", ok_06,
                             f"10/10 succeeded, unique PKs={len(single_ids)}, unique numbers={len(single_nums)}")

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
                tasks = [tenant_a if i % 2 == 0 else tenant_b for i in range(10)]
                futs_multi = [ex.submit(thread_create, t) for t in tasks]
                res_multi = [f.result() for f in futs_multi]

            multi_ids = {r.json()["id"] for r in res_multi if r.status_code == 200}
            ok_07 = (all(r.status_code == 200 for r in res_multi) and len(multi_ids) == 10)
            self.record_test("TEST-07", "Concurrent Invoice Creation Across Multiple Businesses", ok_07,
                             f"10/10 succeeded across TenantA & TenantB, unique PKs={len(multi_ids)}")

            # ---------------------------------------------------------
            # TEST-08: Separate OS Backend Workers (Multiprocessing)
            # ---------------------------------------------------------
            mp_args = [
                (tenant_a["token"], tenant_a["csrf"], tenant_a["customer_id"], tenant_a["prod_a_id"], None)
                for _ in range(6)
            ] + [
                (tenant_b["token"], tenant_b["csrf"], tenant_b["customer_id"], tenant_b["prod_a_id"], None)
                for _ in range(4)
            ]
            ctx = multiprocessing.get_context("spawn")
            with ctx.Pool(processes=4) as pool:
                mp_results = pool.map(_mp_worker_create_invoice, mp_args)

            mp_pids = {r["pid"] for r in mp_results}
            mp_ids = {r["id"] for r in mp_results if r["status"] == 200}
            mp_nums_a = {r["invoice_number"] for r in mp_results[:6] if r["status"] == 200}
            mp_nums_b = {r["invoice_number"] for r in mp_results[6:] if r["status"] == 200}
            ok_08 = (
                all(r["status"] == 200 for r in mp_results)
                and len(mp_pids) >= 2
                and len(mp_ids) == 10
                and len(mp_nums_a) == 6
                and len(mp_nums_b) == 4
            )
            self.record_test("TEST-08", "Multi-Process OS Worker Concurrency Enforcement", ok_08,
                             f"10/10 succeeded across {len(mp_pids)} OS PIDs, unique numbers A={len(mp_nums_a)}/6, B={len(mp_nums_b)}/4")

            # ---------------------------------------------------------
            # TEST-09, TEST-10, TEST-11: Cross-Tenant Access & Reference Denial
            # ---------------------------------------------------------
            ta_inv_id = inv_01["id"]
            cross_get = self.client.get(f"/api/invoices/{ta_inv_id}", cookies={"session_token": tenant_b["token"]})
            cross_pdf = self.client.get(f"/api/invoices/{ta_inv_id}/pdf", cookies={"session_token": tenant_b["token"]})
            cross_put = self.client.put(f"/api/invoices/{ta_inv_id}", json={"due": "Dec 31, 2026"},
                                        cookies={"session_token": tenant_b["token"]}, headers={"X-CSRF-Token": tenant_b["csrf"]})
            cross_patch = self.client.patch(f"/api/invoices/{ta_inv_id}/status", json={"status": "Paid"},
                                            cookies={"session_token": tenant_b["token"]}, headers={"X-CSRF-Token": tenant_b["csrf"]})
            cross_del = self.client.delete(f"/api/invoices/{ta_inv_id}",
                                           cookies={"session_token": tenant_b["token"]}, headers={"X-CSRF-Token": tenant_b["csrf"]})
            ok_09 = all(r.status_code == 404 for r in (cross_get, cross_pdf, cross_put, cross_patch, cross_del))
            self.record_test("TEST-09", "Cross-Tenant Invoice Access Denial (GET/PDF/PUT/PATCH/DELETE -> 404)", ok_09,
                             f"Statuses: {[r.status_code for r in (cross_get, cross_pdf, cross_put, cross_patch, cross_del)]}")

            # TEST-10: Cross-tenant customer_id rejected
            cross_cust = self.client.post(
                "/api/invoices",
                json={"customer_id": tenant_a["customer_id"], "line_items": [{"product_id": tenant_b["prod_a_id"], "quantity": 1}]},
                cookies={"session_token": tenant_b["token"]},
                headers={"X-CSRF-Token": tenant_b["csrf"]}
            )
            ok_10 = (cross_cust.status_code == 404)
            self.record_test("TEST-10", "Cross-Tenant Customer Reference Rejected (HTTP 404)", ok_10,
                             f"Status: {cross_cust.status_code}, Detail: {cross_cust.json().get('detail')}")

            # TEST-11: Cross-tenant product_id rejected
            cross_prod = self.client.post(
                "/api/invoices",
                json={"customer_id": tenant_b["customer_id"], "line_items": [{"product_id": tenant_a["prod_a_id"], "quantity": 1}]},
                cookies={"session_token": tenant_b["token"]},
                headers={"X-CSRF-Token": tenant_b["csrf"]}
            )
            ok_11 = (cross_prod.status_code == 404)
            self.record_test("TEST-11", "Cross-Tenant Product Reference Rejected (HTTP 404)", ok_11,
                             f"Status: {cross_prod.status_code}, Detail: {cross_prod.json().get('detail')}")

            # ---------------------------------------------------------
            # TEST-12: Duplicate Submission Protection via Idempotency-Key
            # ---------------------------------------------------------
            with mysql_engine.connect() as conn:
                stock_before_idem = conn.execute(text("SELECT stock FROM products WHERE id = :pid"), {"pid": tenant_b["prod_a_id"]}).scalar()
                spend_before_idem = Decimal(str(conn.execute(text("SELECT total_spend FROM customers WHERE id = :cid"), {"cid": tenant_b["customer_id"]}).scalar()))

            idem_key = f"idem_test_{os.urandom(8).hex()}"
            r_idem_1 = self.client.post(
                "/api/invoices",
                json={"customer_id": tenant_b["customer_id"], "line_items": [{"product_id": tenant_b["prod_a_id"], "quantity": 3}]},
                cookies={"session_token": tenant_b["token"]},
                headers={"X-CSRF-Token": tenant_b["csrf"], "X-Idempotency-Key": idem_key}
            )
            r_idem_2 = self.client.post(
                "/api/invoices",
                json={"customer_id": tenant_b["customer_id"], "line_items": [{"product_id": tenant_b["prod_a_id"], "quantity": 3}]},
                cookies={"session_token": tenant_b["token"]},
                headers={"X-CSRF-Token": tenant_b["csrf"], "X-Idempotency-Key": idem_key}
            )
            with mysql_engine.connect() as conn:
                stock_after_idem = conn.execute(text("SELECT stock FROM products WHERE id = :pid"), {"pid": tenant_b["prod_a_id"]}).scalar()
                spend_after_idem = Decimal(str(conn.execute(text("SELECT total_spend FROM customers WHERE id = :cid"), {"cid": tenant_b["customer_id"]}).scalar()))
                cnt_idem_rows = conn.execute(text("SELECT COUNT(*) FROM invoices WHERE user_id = :uid AND idempotency_key = :k"),
                                             {"uid": tenant_b["user_id"], "k": idem_key}).scalar()

            ok_12 = (
                r_idem_1.status_code == 200
                and r_idem_2.status_code == 200
                and r_idem_1.json()["id"] == r_idem_2.json()["id"]
                and cnt_idem_rows == 1
                and stock_before_idem - stock_after_idem == 3  # Deducted ONCE, not 6!
                and spend_after_idem - spend_before_idem == Decimal("30000.00")
            )
            self.record_test("TEST-12", "Idempotent Duplicate Submission Prevention (Zero Double Billing/Stock Deduction)", ok_12,
                             f"Same PK returned: {r_idem_1.json()['id'] == r_idem_2.json()['id']}, DB rows={cnt_idem_rows}, Stock deducted={stock_before_idem - stock_after_idem}")

            # ---------------------------------------------------------
            # TEST-13 & TEST-14: Transaction Rollback & Line Item Consistency
            # ---------------------------------------------------------
            with mysql_engine.connect() as conn:
                stock_a_before = conn.execute(text("SELECT stock FROM products WHERE id = :pid"), {"pid": tenant_a["prod_a_id"]}).scalar()
                inv_cnt_before = conn.execute(text("SELECT COUNT(*) FROM invoices WHERE user_id = :uid"), {"uid": tenant_a["user_id"]}).scalar()
                item_cnt_before = conn.execute(text("SELECT COUNT(*) FROM invoice_items WHERE user_id = :uid"), {"uid": tenant_a["user_id"]}).scalar()
                spend_a_before = Decimal(str(conn.execute(text("SELECT total_spend FROM customers WHERE id = :cid"), {"cid": tenant_a["customer_id"]}).scalar()))

            # Item 1 is valid in-stock, Item 2 fails (qty 50 > stock 1) -> whole tx MUST rollback!
            res_rb = self.client.post(
                "/api/invoices",
                json={
                    "customer_id": tenant_a["customer_id"],
                    "line_items": [
                        {"product_id": tenant_a["prod_a_id"], "quantity": 2},
                        {"product_id": tenant_a["prod_b_id"], "quantity": 50},
                    ]
                },
                cookies={"session_token": tenant_a["token"]},
                headers={"X-CSRF-Token": tenant_a["csrf"]}
            )
            with mysql_engine.connect() as conn:
                stock_a_after = conn.execute(text("SELECT stock FROM products WHERE id = :pid"), {"pid": tenant_a["prod_a_id"]}).scalar()
                inv_cnt_after = conn.execute(text("SELECT COUNT(*) FROM invoices WHERE user_id = :uid"), {"uid": tenant_a["user_id"]}).scalar()
                item_cnt_after = conn.execute(text("SELECT COUNT(*) FROM invoice_items WHERE user_id = :uid"), {"uid": tenant_a["user_id"]}).scalar()
                spend_a_after = Decimal(str(conn.execute(text("SELECT total_spend FROM customers WHERE id = :cid"), {"cid": tenant_a["customer_id"]}).scalar()))
                orphans_now = conn.execute(text("SELECT COUNT(*) FROM invoice_items ii LEFT JOIN invoices i ON ii.invoice_id = i.id WHERE i.id IS NULL")).scalar()

            ok_13 = (
                res_rb.status_code == 422
                and stock_a_after == stock_a_before
                and inv_cnt_after == inv_cnt_before
                and item_cnt_after == item_cnt_before
                and spend_a_after == spend_a_before
            )
            ok_14 = (orphans_now == 0)
            self.record_test("TEST-13", "Full Atomic Transaction Rollback on Multi-Item Failure", ok_13,
                             f"Status: {res_rb.status_code}, Stock unchanged ({stock_a_before}->{stock_a_after}), Invoices/Items unchanged")
            self.record_test("TEST-14", "Invoice Items Relational Consistency & Zero Orphans", ok_14,
                             f"Orphaned invoice_items across DB: {orphans_now}")

            # ---------------------------------------------------------
            # TEST-15: Concurrent Atomic Inventory Deduction Consistency
            # ---------------------------------------------------------
            # tenant_c prod_a_id has exact stock = 5. Launch 10 concurrent threads each requesting qty = 1!
            def race_stock(_):
                from starlette.testclient import TestClient
                c = TestClient(self.app, base_url="http://testserver")
                return c.post(
                    "/api/invoices",
                    json={"customer_id": tenant_c["customer_id"], "line_items": [{"product_id": tenant_c["prod_a_id"], "quantity": 1}]},
                    cookies={"session_token": tenant_c["token"]},
                    headers={"X-CSRF-Token": tenant_c["csrf"]}
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
                race_res = list(ex.map(race_stock, range(10)))

            race_200 = sum(1 for r in race_res if r.status_code == 200)
            race_422 = sum(1 for r in race_res if r.status_code == 422)
            with mysql_engine.connect() as conn:
                final_c_stock = conn.execute(text("SELECT stock FROM products WHERE id = :pid"), {"pid": tenant_c["prod_a_id"]}).scalar()
            ok_15 = (race_200 == 5 and race_422 == 5 and final_c_stock == 0)
            self.record_test("TEST-15", "Concurrent Atomic Stock Locking Prevents Overselling", ok_15,
                             f"Initial stock=5, 10 concurrent requests -> 200 OK={race_200}, 422 Insufficient={race_422}, Final stock={final_c_stock}")

            # ---------------------------------------------------------
            # TEST-16: HTTP 409 Conflict, HTTP 422 Validation & Real HTTP 500 Separation
            # ---------------------------------------------------------
            r_422_tax = self.client.post(
                "/api/invoices",
                json={"customer_id": tenant_a["customer_id"], "tax": -5, "amount": "1000"},
                cookies={"session_token": tenant_a["token"]}, headers={"X-CSRF-Token": tenant_a["csrf"]}
            )
            r_422_status = self.client.post(
                "/api/invoices",
                json={"customer_id": tenant_a["customer_id"], "status": "BOGUS_STATE", "amount": "1000"},
                cookies={"session_token": tenant_a["token"]}, headers={"X-CSRF-Token": tenant_a["csrf"]}
            )
            r_422_num = self.client.post(
                "/api/invoices",
                json={"customer_id": tenant_a["customer_id"], "invoice_number": "   ", "amount": "1000"},
                cookies={"session_token": tenant_a["token"]}, headers={"X-CSRF-Token": tenant_a["csrf"]}
            )
            # Test unexpected exception -> HTTP 500 (never disguised as 409)
            import backend.ai_backend as ai_mod
            orig_get_db = ai_mod.get_db
            class _BoomConn:
                def cursor(self):
                    raise RuntimeError("Simulated unexpected fault inside invoice transaction")
                def rollback(self): pass
                def close(self): pass
            try:
                ai_mod.get_db = lambda: _BoomConn()
                r_500 = self.client.post(
                    "/api/invoices",
                    json={"customer_id": tenant_a["customer_id"], "amount": "1000"},
                    cookies={"session_token": tenant_a["token"]}, headers={"X-CSRF-Token": tenant_a["csrf"]}
                )
            finally:
                ai_mod.get_db = orig_get_db

            ok_16 = (
                r_422_tax.status_code == 422
                and r_422_status.status_code == 422
                and r_422_num.status_code == 422
                and r_500.status_code == 500
            )
            self.record_test("TEST-16", "HTTP 422 Validation, 409 Conflict & True 500 Error Classification", ok_16,
                             f"Bad tax={r_422_tax.status_code}, Bad status={r_422_status.status_code}, Blank num={r_422_num.status_code}, Unexpected={r_500.status_code}")

            # ---------------------------------------------------------
            # TEST-17: Editing (PUT / PATCH) & Deletion Without Number Reuse
            # ---------------------------------------------------------
            # Edit tenant_b's inv_03 due date and try duplicate invoice_number -> 409
            r_edit_ok = self.client.put(
                f"/api/invoices/{inv_03['id']}",
                json={"due": "Dec 20, 2026", "status": "Paid"},
                cookies={"session_token": tenant_b["token"]}, headers={"X-CSRF-Token": tenant_b["csrf"]}
            )
            r_edit_dup = self.client.put(
                f"/api/invoices/{inv_03['id']}",
                json={"invoice_number": custom_shared},
                cookies={"session_token": tenant_b["token"]}, headers={"X-CSRF-Token": tenant_b["csrf"]}
            )
            r_patch_ok = self.client.patch(
                f"/api/invoices/{inv_03['id']}/status",
                json={"status": "Pending"},
                cookies={"session_token": tenant_b["token"]}, headers={"X-CSRF-Token": tenant_b["csrf"]}
            )
            # Create one disposable invoice for Tenant A, inspect its number, delete it, create next -> must NOT reuse!
            r_pre_del = self.client.post(
                "/api/invoices",
                json={"customer_id": tenant_a["customer_id"], "amount": "1000"},
                cookies={"session_token": tenant_a["token"]}, headers={"X-CSRF-Token": tenant_a["csrf"]}
            )
            del_target = r_pre_del.json()
            r_del = self.client.delete(
                f"/api/invoices/{del_target['id']}",
                cookies={"session_token": tenant_a["token"]}, headers={"X-CSRF-Token": tenant_a["csrf"]}
            )
            r_post_del = self.client.post(
                "/api/invoices",
                json={"customer_id": tenant_a["customer_id"], "amount": "1000"},
                cookies={"session_token": tenant_a["token"]}, headers={"X-CSRF-Token": tenant_a["csrf"]}
            )
            ok_17 = (
                r_edit_ok.status_code == 200 and r_edit_ok.json()["status"] == "Paid"
                and r_edit_dup.status_code == 409
                and r_patch_ok.status_code == 200 and r_patch_ok.json()["status"] == "Pending"
                and r_del.status_code == 200
                and r_post_del.status_code == 200
                and r_post_del.json()["invoice_number"] != del_target["invoice_number"]
            )
            self.record_test("TEST-17", "Permitted Editing (409 on Conflict) & Delete Without Number Reuse", ok_17,
                             f"Deleted {del_target['invoice_number']}, Next generated {r_post_del.json()['invoice_number']}")

            # ---------------------------------------------------------
            # TEST-18: Actual PDF Generation & Business Number Rendering
            # ---------------------------------------------------------
            r_pdf = self.client.get(f"/api/invoices/{ta_inv_id}/pdf", cookies={"session_token": tenant_a["token"]})
            pdf_text = ""
            if r_pdf.status_code == 200 and r_pdf.content.startswith(b"%PDF-"):
                doc = pymupdf.open(stream=r_pdf.content, filetype="pdf")
                pdf_text = "".join(pg.get_text() for pg in doc)
                doc.close()

            ok_18 = (
                r_pdf.status_code == 200
                and r_pdf.content.startswith(b"%PDF-")
                and inv_01["invoice_number"] in pdf_text
                and f"Invoice_{inv_01['invoice_number']}.pdf" in r_pdf.headers.get("content-disposition", "")
            )
            self.record_test("TEST-18", "Real PyMuPDF PDF Generation Contains Business Invoice Number", ok_18,
                             f"PDF bytes={len(r_pdf.content)}, Disposition='{r_pdf.headers.get('content-disposition')}', Has INV-2026-001={inv_01['invoice_number'] in pdf_text}")

            # ---------------------------------------------------------
            # TEST-19: Genuine Browser Invoice Workflow via CDP
            # ---------------------------------------------------------
            try:
                asyncio.run(self.run_browser_invoice_workflow())
            except Exception as be:
                self.record_test("TEST-19", "Browser Invoice Creation, Duplicate 409 & PDF Download via CDP", False, str(be))

        finally:
            self._cleanup_all_disposable()

        # ---------------------------------------------------------
        # TEST-20: Before-and-After Financial Data Integrity
        # ---------------------------------------------------------
        baseline_after = self._snapshot_baseline()
        ok_20 = (
            baseline_after["users"] == 81
            and baseline_after["customers"] == 31
            and baseline_after["products"] == 24
            and baseline_after["invoices"] == 49
            and baseline_after["invoice_items"] == 30
            and baseline_after["employees"] == 18
            and baseline_after["legacy_orphans"] == 8
            and baseline_after["orphan_items"] == 0
            and baseline_after["sum_amount_num"] == Decimal("14245982.00")
            and baseline_after["paid_revenue"] == Decimal("4091666.00")
            and baseline_after["sum_total"] == Decimal("13531382.00")
            and baseline_after["historical_ids"] == baseline_before["historical_ids"]
        )
        self.record_test(
            "TEST-20",
            "Before-and-After Business & Financial Integrity (Zero Drift/Contamination)",
            ok_20,
            f"Users={baseline_after['users']}/81, Cust={baseline_after['customers']}/31, Prod={baseline_after['products']}/24, "
            f"Inv={baseline_after['invoices']}/49, Items={baseline_after['invoice_items']}/30, Emp={baseline_after['employees']}/18, "
            f"Arch={baseline_after['legacy_orphans']}/8, SUM(amount_num)=₹{baseline_after['sum_amount_num']:,.2f}, Paid=₹{baseline_after['paid_revenue']:,.2f}"
        )

        passed = sum(1 for t in self.test_records if t["passed"])
        total = len(self.test_records)
        print("=" * 74)
        print(f" SEC-13 Verification Complete: {passed} / {total} Passed ({passed/total*100:.1f}%)")
        print("=" * 74)
        return passed == total

    async def run_browser_invoice_workflow(self):
        import websockets

        browser_bin = find_browser()
        temp_dir = tempfile.mkdtemp(prefix="bizops_sec13_browser_")
        debug_port = 9229
        rand = os.urandom(4).hex()
        b_email = f"browser_sec13_{rand}@disposable.local"
        self.disposable_emails.append(b_email)

        chrome_cmd = [
            browser_bin,
            "--headless=new",
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={temp_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-fre",
            "--inprivate",
            "--disable-features=msFirstRunExperience,msEdgeWelcomePage",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-translate",
            "http://localhost:5173/"
        ]
        chrome_proc = subprocess.Popen(chrome_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await asyncio.sleep(2.0)

        try:
            ws_url = None
            for _ in range(25):
                await asyncio.sleep(0.4)
                try:
                    req = urllib.request.Request(f"http://127.0.0.1:{debug_port}/json")
                    with urllib.request.urlopen(req, timeout=1) as resp:
                        data = json.loads(resp.read().decode())
                        for target in data:
                            if "5173" in target.get("url", ""):
                                ws_url = target.get("webSocketDebuggerUrl")
                                break
                        if not ws_url and data:
                            ws_url = data[0].get("webSocketDebuggerUrl")
                        if ws_url:
                            break
                except Exception:
                    pass

            if not ws_url:
                raise RuntimeError("Could not connect to Chromium CDP WebSocket")

            async with websockets.connect(ws_url, max_size=10_000_000) as ws:
                msg_counter = 100
                async def send_cmd(method, params=None):
                    nonlocal msg_counter
                    msg_counter += 1
                    mid = msg_counter
                    await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
                    while True:
                        msg = await ws.recv()
                        res = json.loads(msg)
                        if res.get("id") == mid:
                            return res.get("result", {})

                async def eval_js(expr):
                    r = await send_cmd("Runtime.evaluate", {
                        "expression": expr,
                        "returnByValue": True,
                        "awaitPromise": True
                    })
                    return r.get("result", {}).get("value")

                await send_cmd("Page.navigate", {"url": "http://localhost:5173/"})
                await asyncio.sleep(2.5)

                # Register + login disposable user via browser session, seed customer & product, reload UI
                setup_js = f"""
                (async () => {{
                    const csrfRes = await fetch('/api/auth/csrf');
                    const csrfPre = (await csrfRes.json()).csrf_token;
                    const pw = 'K9#mP4$xQ7!vZ2wR';
                    const reg = await fetch('/api/auth/register', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json', 'X-CSRF-Token': csrfPre }},
                        body: JSON.stringify({{
                            name: 'Test Operator One',
                            email: '{b_email}',
                            password: pw,
                            company: 'Acme Operations',
                            biz_type: 'SaaS'
                        }})
                    }});
                    if (!reg.ok) {{
                        const errJ = await reg.json().catch(() => ({{}}));
                        return {{ ok: false, step: 'register', status: reg.status, detail: errJ.detail }};
                    }}

                    const logRes = await fetch('/api/auth/login', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json', 'X-CSRF-Token': csrfPre }},
                        body: JSON.stringify({{ email: '{b_email}', password: pw }})
                    }});
                    if (!logRes.ok) {{
                        const errL = await logRes.json().catch(() => ({{}}));
                        return {{ ok: false, step: 'login', status: logRes.status, detail: errL.detail }};
                    }}
                    const logData = await logRes.json();
                    const csrf = logData.csrf_token;

                    const cust = await fetch('/api/customers', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }},
                        body: JSON.stringify({{ name: 'Browser Client', email: 'bclient@test.com', company: 'Browser Client Corp', status: 'Active' }})
                    }});
                    const prod = await fetch('/api/inventory', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }},
                        body: JSON.stringify({{ name: 'Browser Cloud License', sku: 'BR-CLD-01', category: 'SaaS', stock: 50, reorder: 5, price: '₹20,000', price_num: 20000 }})
                    }});
                    localStorage.setItem('bizops_active_page', 'invoices');
                    return {{ ok: cust.ok && prod.ok, custStatus: cust.status, prodStatus: prod.status }};
                }})()
                """
                setup_res = await eval_js(setup_js)
                if not setup_res or not setup_res.get("ok"):
                    raise RuntimeError(f"Browser disposable user setup failed: {setup_res}")

                await send_cmd("Page.reload")
                await asyncio.sleep(2.5)

                # Click "New Invoice" button in UI, verify modal opens, wait for async data & submit without invoice #
                ui_create_js = """
                (async () => {
                    const sleep = ms => new Promise(r => setTimeout(r, ms));
                    const waitFor = async (fn, timeoutMs = 6000) => {
                        const deadline = Date.now() + timeoutMs;
                        while (Date.now() < deadline) {
                            const val = fn();
                            if (val) return val;
                            await sleep(150);
                        }
                        return fn();
                    };
                    const findBtn = (txt) => Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.includes(txt));

                    const newBtn = await waitFor(() => findBtn('New Invoice'));
                    if (!newBtn) return { ok: false, err: 'New Invoice button not found', snippet: document.body.innerText.slice(0, 600) };
                    newBtn.click();

                    const submitBtn = await waitFor(() => {
                        const btn = findBtn('Save Invoice');
                        const textOk = document.body.innerText.includes('Browser Client');
                        return btn && textOk ? btn : null;
                    });
                    if (!submitBtn) return { ok: false, err: 'Save Invoice button or seeded customer not ready in modal', snippet: document.body.innerText.slice(0, 600) };
                    submitBtn.click();

                    const createdVisible = await waitFor(() => {
                        const txt = document.body.innerText;
                        return txt.includes('INV-2026-001') && txt.includes('Browser Client');
                    });
                    if (!createdVisible) {
                        return {
                            ok: false,
                            err: 'Created invoice INV-2026-001 not visible in UI within timeout',
                            snippet: document.body.innerText.slice(0, 800)
                        };
                    }

                    // Fetch list via authenticated browser session to grab internal UUID id and test PDF download
                    const invsRes = await fetch('/api/invoices');
                    const invs = await invsRes.json();
                    const created = invs.find(i => i.invoice_number === 'INV-2026-001') || invs[0];
                    if (!created) return { ok: false, err: 'No invoice returned from /api/invoices' };
                    const pdfRes = await fetch('/api/invoices/' + encodeURIComponent(created.id) + '/pdf');
                    const pdfBlob = await pdfRes.blob();

                    // Now test submitting duplicate custom number "INV-2026-001" through the UI modal
                    const newBtn2 = await waitFor(() => findBtn('New Invoice'));
                    if (!newBtn2) return { ok: false, err: 'Second New Invoice button not found' };
                    newBtn2.click();

                    const invInput = await waitFor(() => document.querySelector('input[placeholder*="Auto-generated"]'));
                    if (!invInput) return { ok: false, err: 'Invoice # input not found' };
                    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    nativeSetter.call(invInput, 'INV-2026-001');
                    invInput.dispatchEvent(new Event('input', { bubbles: true }));
                    invInput.dispatchEvent(new Event('change', { bubbles: true }));
                    await sleep(200);

                    const submitBtn2 = await waitFor(() => findBtn('Save Invoice'));
                    if (!submitBtn2) return { ok: false, err: 'Second Save Invoice button not found' };
                    submitBtn2.click();

                    const modalErr = await waitFor(() => document.body.innerText.includes('already exists'));

                    return {
                        ok: Boolean(createdVisible && pdfRes.ok && pdfBlob.size > 1000 && modalErr),
                        internalId: created.id,
                        invNum: created.invoice_number,
                        pdfSize: pdfBlob.size,
                        dup409Shown: Boolean(modalErr),
                        snippet: modalErr ? undefined : document.body.innerText.slice(0, 800)
                    };
                })()
                """
                ui_res = await eval_js(ui_create_js)
                passed = bool(ui_res and ui_res.get("ok"))
                self.record_test(
                    "TEST-19",
                    "Browser Invoice Creation, Duplicate 409 Alert & PDF Download via CDP",
                    passed,
                    f"Result: {ui_res}"
                )
        finally:
            try:
                chrome_proc.terminate()
                chrome_proc.wait(timeout=3)
            except Exception:
                pass


if __name__ == "__main__":
    multiprocessing.freeze_support()
    suite = SEC13VerificationSuite()
    success = suite.run_all()
    sys.exit(0 if success else 1)
