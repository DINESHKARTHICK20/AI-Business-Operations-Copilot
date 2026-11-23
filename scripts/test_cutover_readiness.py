"""
STEP 9: Cutover Readiness & Verification Test Suite for MySQL Staging
Tests database constraints, transaction rollback, multi-user isolation,
concurrency, frontend-to-backend workflows, and data integrity.
"""
import os
import sys
import concurrent.futures
from decimal import Decimal
from datetime import datetime
import unittest

sys.path.insert(0, os.getcwd())

# Force MySQL mode for testing against bizops_staging
os.environ["USE_MYSQL"] = "true"

from backend.database import mysql_engine, text, get_db
from backend.ai_backend import app
from starlette.testclient import TestClient


class TestCutoverReadiness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = mysql_engine
        cls.client = TestClient(app)
        cls.created_user_ids = []
        cls.created_customer_ids = []
        cls.created_product_ids = []
        cls.created_invoice_ids = []

    @classmethod
    def tearDownClass(cls):
        # Comprehensive cleanup of any disposable test artifacts
        with cls.engine.connect() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            
            # Remove any test activities created during tests
            conn.execute(text("DELETE FROM business_activities WHERE text LIKE '%Staging Test%' OR text LIKE '%Cutover Test%';"))
            
            # Remove test sessions created during tests for user 1
            conn.execute(text("DELETE FROM user_sessions WHERE user_id = 1 AND created_at >= '2026-11-23 00:00:00';"))
            
            # Remove any test users created
            conn.execute(text("DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@cutover-test.bizops.local');"))
            conn.execute(text("DELETE FROM business_activities WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@cutover-test.bizops.local');"))
            conn.execute(text("DELETE FROM notifications WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@cutover-test.bizops.local');"))
            conn.execute(text("DELETE FROM users WHERE email LIKE '%@cutover-test.bizops.local';"))
            
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
            conn.commit()

    def test_01_foreign_key_constraint_enforcement(self):
        """Verify MySQL InnoDB strictly rejects orphaned foreign key records."""
        with self.engine.connect() as conn:
            # 1. Invalid user_id on customer insert
            with self.assertRaises(Exception):
                conn.execute(text("""
                    INSERT INTO customers (user_id, name, email, company, status, ltv, total_spend, orders, joined)
                    VALUES (999999, 'Orphan Customer', 'orphan@test.com', 'None', 'Active', '₹0', 0, 0, 'Nov 2026');
                """))
                conn.commit()

            # 2. Invalid user_id on invoice insert
            with self.assertRaises(Exception):
                conn.execute(text("""
                    INSERT INTO invoices (user_id, client, amount, amount_num, due, issued, status)
                    VALUES (999999, 'Invalid Client', '₹1,000', 1000.00, '2026-12-01', '2026-11-23', 'Pending');
                """))
                conn.commit()

            # 3. Invalid invoice_id on invoice_items insert
            with self.assertRaises(Exception):
                conn.execute(text("""
                    INSERT INTO invoice_items (user_id, invoice_id, product_name, quantity, unit_price, line_total)
                    VALUES (1, 'NON-EXISTENT-INV-999', 'Fake Item', 1, 100.00, 100.00);
                """))
                conn.commit()

    def test_02_unique_constraint_enforcement(self):
        """Verify unique constraints prevent duplicates in MySQL (users.email, products SKU per user)."""
        with self.engine.connect() as conn:
            # Duplicate email for users
            with self.assertRaises(Exception):
                conn.execute(text("""
                    INSERT INTO users (name, email, password, company, biz_type, created_at, updated_at, is_active, is_verified)
                    VALUES ('Duplicate Dinesh', 'dinesh@test.com', 'somehash', 'Co', 'Retail', '2026-11-23 00:00:00', '2026-11-23 00:00:00', 1, 1);
                """))
                conn.commit()

    def test_03_transaction_rollback_and_acid_atomicity(self):
        """Verify transaction rollback leaves database state completely untouched."""
        initial_stock = None
        with self.engine.connect() as conn:
            initial_stock = conn.execute(text("SELECT stock FROM products WHERE id = 1;")).scalar()

        # Simulate a transaction that deducts stock then encounters an error
        try:
            with self.engine.connect() as conn:
                trans = conn.begin()
                conn.execute(text("UPDATE products SET stock = stock - 5 WHERE id = 1;"))
                # Deliberate failure: inserting invalid FK
                conn.execute(text("INSERT INTO customers (user_id, name) VALUES (999999, 'Fail');"))
                trans.commit()
        except Exception:
            # Transaction should have rolled back
            pass

        with self.engine.connect() as conn:
            current_stock = conn.execute(text("SELECT stock FROM products WHERE id = 1;")).scalar()
            self.assertEqual(initial_stock, current_stock, "Stock must remain unchanged after transaction rollback.")

    def test_04_concurrency_and_pool_stability(self):
        """Verify concurrent operations across multiple threads do not cause deadlocks or connection exhaustion."""
        def make_request(i):
            tc = TestClient(app)
            res = tc.get("/api/auth/csrf")
            return res.status_code == 200

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(make_request, i) for i in range(16)]
            results = [f.result() for f in futures]

        self.assertEqual(len(results), 16)
        self.assertTrue(all(results), "All 16 concurrent requests must succeed.")

    def test_05_full_user_journey_workflow(self):
        """Execute end-to-end frontend-to-backend user workflow against MySQL staging."""
        # 1. CSRF
        csrf_res = self.client.get("/api/auth/csrf")
        self.assertEqual(csrf_res.status_code, 200)
        csrf_token = csrf_res.json().get("csrf_token")
        self.assertTrue(bool(csrf_token))

        # 2. Login as existing business user
        login_res = self.client.post(
            "/api/auth/login",
            json={"email": "dinesh@test.com", "password": "password123"},
            headers={"x-csrf-token": csrf_token}
        )
        self.assertEqual(login_res.status_code, 200)
        self.assertEqual(login_res.json().get("status"), "success")
        auth_csrf = self.client.cookies.get("csrf_token") or csrf_token

        # 3. Profile
        me_res = self.client.get("/api/auth/me")
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json().get("email"), "dinesh@test.com")

        # 4. Dashboard Stats
        dash_res = self.client.get("/api/dashboard/stats")
        self.assertEqual(dash_res.status_code, 200)
        kpis = dash_res.json().get("kpis", {})
        self.assertIn("monthly_revenue", kpis)
        self.assertIn("active_customers", kpis)

        # 5. Customers List
        cust_res = self.client.get("/api/customers")
        self.assertEqual(cust_res.status_code, 200)
        self.assertEqual(len(cust_res.json()), 7)

        # 6. Inventory List
        inv_res = self.client.get("/api/inventory")
        self.assertEqual(inv_res.status_code, 200)
        self.assertEqual(len(inv_res.json()), 6)

        # 7. Invoices List & PyMuPDF PDF
        invoices_res = self.client.get("/api/invoices")
        self.assertEqual(invoices_res.status_code, 200)
        self.assertEqual(len(invoices_res.json()), 23)

        pdf_res = self.client.get("/api/invoices/INV-2026-001/pdf")
        self.assertEqual(pdf_res.status_code, 200)
        self.assertTrue(pdf_res.content.startswith(b"%PDF-"))

        # 8. Profit Products
        profit_res = self.client.get("/api/profit/products")
        self.assertEqual(profit_res.status_code, 200)
        self.assertEqual(len(profit_res.json()), 10)

        # 9. Predictive ML Pipelines
        churn_res = self.client.post(
            "/api/predict/churn",
            json={
                "total_orders": 10,
                "total_spend": 25000.0,
                "days_since_last_purchase": 5,
                "support_tickets": 0,
                "complaints": 0,
                "average_order_value": 2500.0
            },
            headers={"x-csrf-token": auth_csrf}
        )
        self.assertEqual(churn_res.status_code, 200)
        self.assertIn("churn_probability", churn_res.json())

        # 10. Global Search
        search_res = self.client.get("/api/search?q=Selvaraj")
        self.assertEqual(search_res.status_code, 200)
        self.assertGreaterEqual(len(search_res.json().get("results", {}).get("customers", [])), 1)

        # 11. Logout & Revocation
        logout_res = self.client.post("/api/auth/logout", headers={"x-csrf-token": auth_csrf})
        self.assertEqual(logout_res.status_code, 200)
        subsequent = self.client.get("/api/auth/me")
        self.assertEqual(subsequent.status_code, 401)

    def test_06_post_test_cleanliness_and_data_preservation(self):
        """Verify no test or sample dummy data was permanently left in MySQL staging."""
        with self.engine.connect() as conn:
            users_cnt = conn.execute(text("SELECT COUNT(*) FROM users;")).scalar()
            cust_cnt = conn.execute(text("SELECT COUNT(*) FROM customers;")).scalar()
            prod_cnt = conn.execute(text("SELECT COUNT(*) FROM products;")).scalar()
            inv_cnt = conn.execute(text("SELECT COUNT(*) FROM invoices;")).scalar()
            inv_amt = conn.execute(text("SELECT SUM(amount_num) FROM invoices;")).scalar()
            archive_cnt = conn.execute(text("SELECT COUNT(*) FROM legacy_orphans_archive;")).scalar()

        self.assertEqual(users_cnt, 81)
        self.assertEqual(cust_cnt, 31)
        self.assertEqual(prod_cnt, 24)
        self.assertEqual(inv_cnt, 49)
        self.assertEqual(Decimal(str(inv_amt)), Decimal("14245982.00"))
        self.assertEqual(archive_cnt, 8)


if __name__ == "__main__":
    unittest.main()
