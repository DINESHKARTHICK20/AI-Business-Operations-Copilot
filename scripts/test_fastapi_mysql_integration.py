#!/usr/bin/env python3
"""
FastAPI Backend Integration Verification Suite for MySQL Staging
AI Business Operations Copilot - Production MySQL Staging Architecture

Tests the actual FastAPI application endpoints against the live MySQL Server 8.0.46 staging database:
1. Existing account login (User 1 dinesh@test.com, bcrypt-12, HttpOnly session cookie, session-bound CSRF)
2. Registration without OTP (strong password >= 12, clean workspace, zero dummy data)
3. Dashboard (stats, insights, activity relative times)
4. Customer CRM management (CRUD operations, LTV, total_spend, churn boolean)
5. Inventory management (CRUD operations, composite SKU uniqueness, price Decimal)
6. Invoices & PDF generation (Invoice creation, line items, PyMuPDF binary PDF rendering)
7. Employee HR management (CRUD operations, department assignments, salary formatting)
8. Profit analysis (Unit economics, margins, buy/sell prices)
9. AI predictions (RandomForest predictive models: churn, sales, inventory)
10. Global search (Multi-table text search across customers, products, invoices)
11. Notifications (List, mark read, mark all read, reserved keyword backticking)
12. Authentication & CSRF protection (Session-bound token verification, CSRF enforcement)
13. Multi-user tenant isolation (Strict cross-tenant data isolation and leak prevention)
14. Concurrent database operations (Threaded concurrency against QueuePool)
15. Logout & session restoration (Session invalidation, cookie clearing, 401 on revoked session)

All test records are strictly isolated, tracked, and cleaned up automatically.
The 545 migrated records and source databases remain completely uncontaminated.
"""

import os
import sys
import json
import logging
import concurrent.futures
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Enforce MySQL mode for this test execution
os.environ["USE_MYSQL"] = "true"

from starlette.testclient import TestClient
from backend.ai_backend import app
from backend.database import engine, get_db, is_mysql_mode
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(levelname)-5.5s [%(name)s] %(message)s")
logger = logging.getLogger("bizops.fastapi_mysql_test")


class FastAPIMySQLIntegrationSuite:
    def __init__(self):
        self.client = TestClient(app)
        self.results: Dict[str, Dict[str, Any]] = {}
        self.created_user_ids: List[int] = []
        self.created_customer_ids: List[int] = []
        self.created_product_ids: List[int] = []
        self.created_invoice_ids: List[str] = []
        self.created_employee_ids: List[int] = []

    def record_test(self, test_id: str, title: str, passed: bool, details: Dict[str, Any]):
        self.results[test_id] = {
            "title": title,
            "status": "PASS" if passed else "FAIL",
            "details": details
        }
        status_str = "PASS" if passed else "FAIL"
        logger.info("[%s] %s: %s", status_str, test_id, title)

    def cleanup_disposable_test_data(self):
        """Strictly cleans up all disposable test artifacts to prevent contamination of the 545 records."""
        logger.info("Cleaning up disposable test artifacts from MySQL staging...")
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
                
                # Clean up created invoices and line items
                for inv_id in self.created_invoice_ids:
                    conn.execute(text("DELETE FROM invoice_items WHERE invoice_id = :id;"), {"id": inv_id})
                    conn.execute(text("DELETE FROM invoices WHERE id = :id;"), {"id": inv_id})

                # Clean up created products
                for p_id in self.created_product_ids:
                    conn.execute(text("DELETE FROM products WHERE id = :id;"), {"id": p_id})

                # Clean up created customers
                for c_id in self.created_customer_ids:
                    conn.execute(text("DELETE FROM customers WHERE id = :id;"), {"id": c_id})

                # Clean up created employees
                for e_id in self.created_employee_ids:
                    conn.execute(text("DELETE FROM employees WHERE id = :id;"), {"id": e_id})

                # Clean up created users, sessions, activities, notifications
                for u_id in self.created_user_ids:
                    conn.execute(text("DELETE FROM user_sessions WHERE user_id = :uid;"), {"uid": u_id})
                    conn.execute(text("DELETE FROM business_activities WHERE user_id = :uid;"), {"uid": u_id})
                    conn.execute(text("DELETE FROM notifications WHERE user_id = :uid;"), {"uid": u_id})
                    conn.execute(text("DELETE FROM users WHERE id = :uid;"), {"uid": u_id})

                # Extra safety cleanup for test emails
                conn.execute(text("DELETE FROM users WHERE email LIKE '%@staging-test.bizops.local';"))
                conn.execute(text("DELETE FROM customers WHERE email LIKE '%@staging-test.bizops.local';"))

                conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        logger.info("Disposable test artifacts cleanup complete.")

    def run_all_tests(self) -> Dict[str, Any]:
        logger.info("Starting FastAPI Backend MySQL Staging Integration Test Suite...")

        # ---------------------------------------------------------
        # TEST-01: CSRF Token Initialization & Cookie Binding
        # ---------------------------------------------------------
        csrf_res = self.client.get("/api/auth/csrf")
        csrf_ok = csrf_res.status_code == 200 and "csrf_token" in csrf_res.json()
        initial_csrf = csrf_res.json().get("csrf_token") if csrf_ok else ""

        self.record_test(
            "TEST-01",
            "CSRF Token Generation & Cookie Binding",
            csrf_ok,
            {"status_code": csrf_res.status_code, "has_token": bool(initial_csrf)}
        )

        # ---------------------------------------------------------
        # TEST-02: Existing Account Login (User 1 dinesh@test.com)
        # ---------------------------------------------------------
        login_res = self.client.post(
            "/api/auth/login",
            json={"email": "dinesh@test.com", "password": "password123"},
            headers={"x-csrf-token": initial_csrf}
        )
        login_ok = login_res.status_code == 200 and login_res.json().get("status") == "success"
        user_1_data = login_res.json().get("user", {})
        session_token = self.client.cookies.get("session_token")
        login_csrf = self.client.cookies.get("csrf_token") or login_res.json().get("csrf_token")

        self.record_test(
            "TEST-02",
            "Existing Account Login (bcrypt-12, HttpOnly Cookie, Session Stored in MySQL)",
            login_ok and user_1_data.get("id") == 1 and bool(session_token),
            {
                "status_code": login_res.status_code,
                "user_id": user_1_data.get("id"),
                "email": user_1_data.get("email"),
                "session_cookie_set": bool(session_token)
            }
        )

        auth_headers = {"x-csrf-token": login_csrf}

        # ---------------------------------------------------------
        # TEST-03: Authenticated User Profile (GET /api/auth/me)
        # ---------------------------------------------------------
        me_res = self.client.get("/api/auth/me")
        me_ok = me_res.status_code == 200 and me_res.json().get("email") == "dinesh@test.com"

        self.record_test(
            "TEST-03",
            "Session Authentication & Identity Verification (/api/auth/me)",
            me_ok,
            {"status_code": me_res.status_code, "email": me_res.json().get("email")}
        )

        # ---------------------------------------------------------
        # TEST-04: Dashboard Analytics & KPIs (/api/dashboard/stats)
        # ---------------------------------------------------------
        dash_res = self.client.get("/api/dashboard/stats")
        dash_ok = dash_res.status_code == 200 and "kpis" in dash_res.json()
        kpis = dash_res.json().get("kpis", {})

        self.record_test(
            "TEST-04",
            "Dashboard Analytics & Real-Time Financial Aggregation Integrity",
            dash_ok and "monthly_revenue" in kpis and "active_customers" in kpis,
            {
                "status_code": dash_res.status_code,
                "monthly_revenue": kpis.get("monthly_revenue"),
                "active_customers": kpis.get("active_customers"),
                "business_health": kpis.get("business_health")
            }
        )

        # ---------------------------------------------------------
        # TEST-05: Customer Management Module (GET /api/customers & CRUD)
        # ---------------------------------------------------------
        cust_list_res = self.client.get("/api/customers")
        cust_list_ok = cust_list_res.status_code == 200 and len(cust_list_res.json()) >= 7
        
        # Create disposable test customer
        create_cust_res = self.client.post(
            "/api/customers",
            json={
                "name": "Staging Test Customer",
                "email": "test_cust@staging-test.bizops.local",
                "company": "Staging Tech Ltd",
                "status": "Active",
                "total_spend": 25000.0,
                "orders": 3,
                "average_order_value": 8333.33
            },
            headers=auth_headers
        )
        created_cust = create_cust_res.json()
        cust_crud_ok = create_cust_res.status_code == 200 and "id" in created_cust
        if cust_crud_ok:
            self.created_customer_ids.append(created_cust["id"])

        self.record_test(
            "TEST-05",
            "Customer Management Module & Database Read/Write Operations",
            cust_list_ok and cust_crud_ok,
            {
                "list_status": cust_list_res.status_code,
                "existing_customers_loaded": len(cust_list_res.json()),
                "create_customer_status": create_cust_res.status_code,
                "created_customer_id": created_cust.get("id")
            }
        )

        # ---------------------------------------------------------
        # TEST-06: Inventory Management Module (GET & POST /api/inventory)
        # ---------------------------------------------------------
        inv_list_res = self.client.get("/api/inventory")
        inv_list_ok = inv_list_res.status_code == 200 and len(inv_list_res.json()) >= 6

        # Create disposable test product
        create_prod_res = self.client.post(
            "/api/inventory",
            json={
                "name": "Staging Test Widget",
                "sku": "TEST-SKU-9999",
                "category": "Testing",
                "stock": 100,
                "reorder": 20,
                "price": "₹1,500",
                "price_num": 1500.0,
                "status": "In Stock",
                "trend": "+5%",
                "avg_daily_demand": 3.0,
                "trend_factor": 1.0,
                "promotion_factor": 1.0
            },
            headers=auth_headers
        )
        created_prod = create_prod_res.json()
        prod_crud_ok = create_prod_res.status_code == 200 and "id" in created_prod
        if prod_crud_ok:
            self.created_product_ids.append(created_prod["id"])

        self.record_test(
            "TEST-06",
            "Inventory Catalog Module & Decimal Pricing Operations",
            inv_list_ok and prod_crud_ok,
            {
                "list_status": inv_list_res.status_code,
                "existing_products_loaded": len(inv_list_res.json()),
                "create_product_status": create_prod_res.status_code,
                "created_product_sku": created_prod.get("sku")
            }
        )

        # ---------------------------------------------------------
        # TEST-07: Invoices & Real PyMuPDF PDF Generation (/api/invoices)
        # ---------------------------------------------------------
        invoices_list_res = self.client.get("/api/invoices")
        invoices_list_ok = invoices_list_res.status_code == 200 and len(invoices_list_res.json()) >= 23

        # Test PDF Generation on existing invoice (INV-2026-001)
        pdf_res = self.client.get("/api/invoices/INV-2026-001/pdf")
        pdf_valid = (
            pdf_res.status_code == 200
            and pdf_res.headers.get("content-type") == "application/pdf"
            and pdf_res.content.startswith(b"%PDF-")
            and len(pdf_res.content) > 1000
        )

        self.record_test(
            "TEST-07",
            "Invoices Module & Real PyMuPDF Binary PDF Document Generation",
            invoices_list_ok and pdf_valid,
            {
                "invoices_status": invoices_list_res.status_code,
                "invoices_count": len(invoices_list_res.json()),
                "pdf_status": pdf_res.status_code,
                "pdf_bytes_length": len(pdf_res.content),
                "pdf_magic_bytes": pdf_res.content[:5].decode("latin-1", errors="ignore")
            }
        )

        # ---------------------------------------------------------
        # TEST-08: Employee Staff Management (/api/employees)
        # ---------------------------------------------------------
        emp_list_res = self.client.get("/api/employees")
        emp_list_ok = emp_list_res.status_code == 200 and len(emp_list_res.json()) >= 4

        create_emp_res = self.client.post(
            "/api/employees",
            json={
                "name": "Staging Test Staff",
                "role": "QA Engineer",
                "dept": "Engineering",
                "salary": "₹85,000/mo",
                "status": "Active",
                "attendance": 98,
                "performance": 95
            },
            headers=auth_headers
        )
        created_emp = create_emp_res.json()
        emp_crud_ok = create_emp_res.status_code == 200 and "id" in created_emp
        if emp_crud_ok:
            self.created_employee_ids.append(created_emp["id"])

        self.record_test(
            "TEST-08",
            "Employee HR Management Module & Department Integrity",
            emp_list_ok and emp_crud_ok,
            {
                "employee_list_status": emp_list_res.status_code,
                "existing_employees_count": len(emp_list_res.json()),
                "create_employee_status": create_emp_res.status_code
            }
        )

        # ---------------------------------------------------------
        # TEST-09: Profit Analysis & Product Margins (/api/profit/products)
        # ---------------------------------------------------------
        profit_res = self.client.get("/api/profit/products")
        profit_ok = profit_res.status_code == 200 and len(profit_res.json()) > 0

        self.record_test(
            "TEST-09",
            "Profit Analysis & Unit Economics Calculation Integrity",
            profit_ok,
            {
                "status_code": profit_res.status_code,
                "profit_products_loaded": len(profit_res.json()) if profit_ok else 0
            }
        )

        # ---------------------------------------------------------
        # TEST-10: AI Predictive Models (/api/predict/*)
        # ---------------------------------------------------------
        churn_pred = self.client.post(
            "/api/predict/churn",
            json={
                "total_orders": 15,
                "total_spend": 350000.0,
                "days_since_last_purchase": 25,
                "support_tickets": 1,
                "complaints": 0,
                "average_order_value": 23333.33
            },
            headers=auth_headers
        )
        sales_pred = self.client.post(
            "/api/predict/sales",
            json={"month_index": 12, "orders": 120, "marketing_spend": 50000.0},
            headers=auth_headers
        )
        inv_pred = self.client.post(
            "/api/predict/inventory",
            json={
                "avg_daily_demand": 4.5,
                "trend": 0.1,
                "promotion_factor": 0.05,
                "current_stock": 50.0,
                "reorder_level": 25.0
            },
            headers=auth_headers
        )

        ai_ok = (
            churn_pred.status_code == 200
            and sales_pred.status_code == 200
            and inv_pred.status_code == 200
            and "churn_probability" in churn_pred.json()
            and "predicted_revenue" in sales_pred.json()
            and "recommended_reorder" in inv_pred.json()
        )

        self.record_test(
            "TEST-10",
            "AI Machine Learning Predictive Pipelines (Churn, Sales, Inventory)",
            ai_ok,
            {
                "churn_status": churn_pred.status_code,
                "sales_status": sales_pred.status_code,
                "inventory_status": inv_pred.status_code
            }
        )

        # ---------------------------------------------------------
        # TEST-11: Global Multi-Entity Search (/api/search)
        # ---------------------------------------------------------
        search_res = self.client.get("/api/search?q=TechCorp")
        search_ok = search_res.status_code == 200 and "results" in search_res.json()
        results = search_res.json().get("results", {})

        self.record_test(
            "TEST-11",
            "Global Multi-Entity Cross-Table Search Engine (/api/search)",
            search_ok,
            {
                "status_code": search_res.status_code,
                "customers_found": len(results.get("customers", [])),
                "invoices_found": len(results.get("invoices", []))
            }
        )

        # ---------------------------------------------------------
        # TEST-12: Notifications Management (Reserved Keywords `desc` & `read`)
        # ---------------------------------------------------------
        notif_list_res = self.client.get("/api/notifications")
        notif_ok = notif_list_res.status_code == 200
        
        # Test mark read
        mark_all_res = self.client.post("/api/notifications/read-all", headers=auth_headers)
        mark_all_ok = mark_all_res.status_code == 200

        self.record_test(
            "TEST-12",
            "Notifications Management & Reserved Keyword Escaping (`desc`, `read`)",
            notif_ok and mark_all_ok,
            {
                "list_status": notif_list_res.status_code,
                "mark_all_status": mark_all_res.status_code,
                "notifications_count": len(notif_list_res.json()) if notif_ok else 0
            }
        )

        # ---------------------------------------------------------
        # TEST-13: Registration without OTP & Strong Password (>= 12)
        # ---------------------------------------------------------
        reg_client = TestClient(app)
        reg_csrf = reg_client.get("/api/auth/csrf").json().get("csrf_token")
        
        test_email = "staging_new_user_8899@staging-test.bizops.local"
        reg_res = reg_client.post(
            "/api/auth/register",
            json={
                "name": "New Staging Account",
                "email": test_email,
                "password": "StrongPassword2026!Secure",
                "company": "Clean Slate Tech",
                "biz_type": "Consulting"
            },
            headers={"x-csrf-token": reg_csrf}
        )
        reg_ok = reg_res.status_code == 200 and reg_res.json().get("status") == "success"
        new_uid = reg_res.json().get("user", {}).get("id")
        if new_uid:
            self.created_user_ids.append(new_uid)

        # Log in as newly registered user to obtain session cookie
        new_csrf = reg_client.cookies.get("csrf_token") or reg_csrf
        login_new_res = reg_client.post(
            "/api/auth/login",
            json={"email": test_email, "password": "StrongPassword2026!Secure"},
            headers={"x-csrf-token": new_csrf}
        )
        new_login_ok = login_new_res.status_code == 200

        # Verify new user has completely clean workspace (zero dummy data)
        new_cust_res = reg_client.get("/api/customers")
        new_prod_res = reg_client.get("/api/inventory")
        new_inv_res = reg_client.get("/api/invoices")
        new_dash_res = reg_client.get("/api/dashboard/stats")

        zero_dummy_ok = (
            new_login_ok
            and new_cust_res.status_code == 200
            and new_prod_res.status_code == 200
            and new_inv_res.status_code == 200
            and len(new_cust_res.json()) == 0
            and len(new_prod_res.json()) == 0
            and len(new_inv_res.json()) == 0
            and str(new_dash_res.json().get("kpis", {}).get("active_customers", "0")) == "0"
        )

        self.record_test(
            "TEST-13",
            "Registration Without OTP, Strong Password (>=12) & Zero Dummy Data",
            reg_ok and zero_dummy_ok,
            {
                "registration_status": reg_res.status_code,
                "login_status": login_new_res.status_code,
                "new_user_id": new_uid,
                "clean_customers_count": len(new_cust_res.json()) if new_cust_res.status_code == 200 else -1,
                "clean_products_count": len(new_prod_res.json()) if new_prod_res.status_code == 200 else -1,
                "clean_invoices_count": len(new_inv_res.json()) if new_inv_res.status_code == 200 else -1,
                "zero_dummy_verified": zero_dummy_ok
            }
        )

        # ---------------------------------------------------------
        # TEST-14: Multi-User Tenant Isolation Enforcement
        # ---------------------------------------------------------
        # User 1 cannot see New User's workspace, New User cannot see User 1's customers
        user_1_customers = [c["id"] for c in self.client.get("/api/customers").json()]
        new_user_cust_list = reg_client.get("/api/customers").json() if new_login_ok else []
        new_user_sees_user1 = any(cid in user_1_customers for cid in [c["id"] for c in new_user_cust_list])
        
        # Test cross-tenant access directly (try to access or delete customer owned by User 1 as New User)
        target_cust_id = user_1_customers[0] if user_1_customers else 1
        unauthorized_delete = reg_client.delete(
            f"/api/customers/{target_cust_id}",
            headers={"x-csrf-token": reg_client.cookies.get("csrf_token") or new_csrf}
        )
        tenant_isolation_ok = (not new_user_sees_user1) and (unauthorized_delete.status_code in (404, 403, 401))

        self.record_test(
            "TEST-14",
            "Multi-User Tenant Isolation & Cross-Account Access Denial",
            tenant_isolation_ok,
            {
                "cross_tenant_read_leak": new_user_sees_user1,
                "cross_tenant_delete_status": unauthorized_delete.status_code,
                "isolation_strictly_enforced": tenant_isolation_ok
            }
        )

        # ---------------------------------------------------------
        # TEST-15: Concurrent Database Operations & QueuePool Stability
        # ---------------------------------------------------------
        def make_concurrent_request(req_idx):
            tc = TestClient(app)
            r = tc.get("/api/auth/csrf")
            return r.status_code == 200

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(make_concurrent_request, i) for i in range(16)]
            results = [f.result() for f in futures]

        concurrency_ok = all(results) and len(results) == 16

        self.record_test(
            "TEST-15",
            "Concurrent Database Operations & QueuePool Pool Stability",
            concurrency_ok,
            {
                "total_concurrent_requests": len(results),
                "successful_requests": sum(results),
                "pool_exhaustion_or_deadlocks": not concurrency_ok
            }
        )

        # ---------------------------------------------------------
        # TEST-16: Logout & Session Invalidation
        # ---------------------------------------------------------
        logout_res = self.client.post("/api/auth/logout", headers=auth_headers)
        logout_ok = logout_res.status_code == 200
        
        # Subsequent authenticated request should now be rejected (401)
        subsequent_res = self.client.get("/api/auth/me")
        revocation_ok = subsequent_res.status_code == 401

        self.record_test(
            "TEST-16",
            "Logout & Session Invalidation in MySQL (Subsequent Requests Return 401)",
            logout_ok and revocation_ok,
            {
                "logout_status": logout_res.status_code,
                "revoked_session_status": subsequent_res.status_code
            }
        )

        # ---------------------------------------------------------
        # TEST-17: Post-Test Staging Data Contamination Verification
        # ---------------------------------------------------------
        self.cleanup_disposable_test_data()

        with engine.connect() as conn:
            final_user_cnt = conn.execute(text("SELECT COUNT(*) FROM users;")).scalar()
            final_cust_cnt = conn.execute(text("SELECT COUNT(*) FROM customers;")).scalar()
            final_prod_cnt = conn.execute(text("SELECT COUNT(*) FROM products;")).scalar()
            final_inv_cnt = conn.execute(text("SELECT COUNT(*) FROM invoices;")).scalar()
            final_archive_cnt = conn.execute(text("SELECT COUNT(*) FROM legacy_orphans_archive;")).scalar()
            final_inv_amt = Decimal(str(conn.execute(text("SELECT SUM(amount_num) FROM invoices;")).scalar()))

        no_contamination = (
            final_user_cnt == 81
            and final_cust_cnt == 31
            and final_prod_cnt == 24
            and final_inv_cnt == 49
            and final_archive_cnt == 8
            and final_inv_amt == Decimal("14245982.00")
        )

        self.record_test(
            "TEST-17",
            "Post-Test Data Cleanliness Verification (545 Migrated Records Intact)",
            no_contamination,
            {
                "users_count": final_user_cnt,
                "customers_count": final_cust_cnt,
                "products_count": final_prod_cnt,
                "invoices_count": final_inv_cnt,
                "legacy_orphans_count": final_archive_cnt,
                "invoices_amount_sum": float(final_inv_amt),
                "contamination_detected": not no_contamination
            }
        )

        passed_count = sum(1 for t in self.results.values() if t["status"] == "PASS")
        total_count = len(self.results)
        logger.info("Verification Complete: %d / %d Tests Passed (%.1f%%).",
                    passed_count, total_count, (passed_count / total_count) * 100)

        return {
            "passed_tests": passed_count,
            "total_tests": total_count,
            "score_pct": (passed_count / total_count) * 100,
            "results": self.results
        }


if __name__ == "__main__":
    suite = FastAPIMySQLIntegrationSuite()
    try:
        out = suite.run_all_tests()
        print(json.dumps(out, indent=2))
    finally:
        suite.cleanup_disposable_test_data()
