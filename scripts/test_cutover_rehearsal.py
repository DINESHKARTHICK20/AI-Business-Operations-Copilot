"""
Step 10: Cutover Rehearsal and Rollback Test Suite
Tests switching between SQLite and MySQL modes, verifies module compatibility,
tests database divergence handling, and confirms rollback safety.
"""
import os
import sys
import unittest
import sqlite3
from decimal import Decimal
from datetime import datetime

sys.path.insert(0, os.getcwd())

from backend.database import get_db, is_mysql_mode, mysql_engine, text
from backend.ai_backend import app
from starlette.testclient import TestClient


class TestCutoverRehearsal(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_01_sqlite_mode_baseline(self):
        """Verify baseline operations in SQLite mode (USE_MYSQL=false)."""
        os.environ["USE_MYSQL"] = "false"
        self.assertFalse(is_mysql_mode())

        conn = get_db(mode="sqlite")
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, email FROM users WHERE id = 1;")
            user = cur.fetchone()
            self.assertEqual(user["email"], "dinesh@test.com")
            
            # Check FK enforcement
            fk = cur.execute("PRAGMA foreign_keys;").fetchone()
            self.assertEqual(fk[0], 1)
        finally:
            conn.close()

    def test_02_mysql_mode_cutover_activation(self):
        """Verify application switching to MySQL mode (USE_MYSQL=true)."""
        os.environ["USE_MYSQL"] = "true"
        self.assertTrue(is_mysql_mode())

        conn = get_db(mode="mysql")
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, email FROM users WHERE id = ?", (1,))
            user = cur.fetchone()
            self.assertEqual(user["email"], "dinesh@test.com")
            
            # Verify customers in MySQL have integer churn scores
            cur.execute("SELECT churn FROM customers WHERE id = ?", (3,))
            c3 = cur.fetchone()
            self.assertEqual(c3["churn"], 78, "Customer 3 churn score must be preserved as integer 78")
            
            cur.execute("SELECT churn FROM customers WHERE id = ?", (4,))
            c4 = cur.fetchone()
            self.assertEqual(c4["churn"], 98, "Customer 4 churn score must be preserved as integer 98")
        finally:
            conn.close()

    def test_03_full_api_workflow_under_mysql_mode(self):
        """Verify FastAPI endpoints operate flawlessly in MySQL mode."""
        os.environ["USE_MYSQL"] = "true"
        
        # 1. CSRF
        csrf_res = self.client.get("/api/auth/csrf")
        self.assertEqual(csrf_res.status_code, 200)
        csrf_tok = csrf_res.json().get("csrf_token")
        
        # 2. Login
        login_res = self.client.post(
            "/api/auth/login",
            json={"email": "dinesh@test.com", "password": "password123"},
            headers={"x-csrf-token": csrf_tok}
        )
        self.assertEqual(login_res.status_code, 200)
        auth_csrf = self.client.cookies.get("csrf_token") or csrf_tok
        
        # 3. Dashboard stats
        dash_res = self.client.get("/api/dashboard/stats")
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn("monthly_revenue", dash_res.json().get("kpis", {}))
        
        # 4. Customers list
        cust_res = self.client.get("/api/customers")
        self.assertEqual(cust_res.status_code, 200)
        self.assertEqual(len(cust_res.json()), 7)
        
        # 5. Inventory list
        inv_res = self.client.get("/api/inventory")
        self.assertEqual(inv_res.status_code, 200)
        self.assertEqual(len(inv_res.json()), 6)
        
        # 6. Invoices list & PDF
        invoices_res = self.client.get("/api/invoices")
        self.assertEqual(invoices_res.status_code, 200)
        self.assertEqual(len(invoices_res.json()), 23)
        
        pdf_res = self.client.get("/api/invoices/INV-2026-001/pdf")
        self.assertEqual(pdf_res.status_code, 200)
        self.assertTrue(pdf_res.content.startswith(b"%PDF-"))
        
        # 7. Logout
        logout_res = self.client.post("/api/auth/logout", headers={"x-csrf-token": auth_csrf})
        self.assertEqual(logout_res.status_code, 200)

    def test_04_instant_rollback_to_sqlite(self):
        """Verify seamless instant rollback to SQLite by toggling USE_MYSQL=false."""
        os.environ["USE_MYSQL"] = "false"
        self.assertFalse(is_mysql_mode())

        # Test SQLite connection
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM users;")
            u_cnt = cur.fetchone()[0]
            self.assertEqual(u_cnt, 83)  # SQLite live has 83 users intact
            
            cur.execute("SELECT COUNT(*) FROM invoices;")
            inv_cnt = cur.fetchone()[0]
            self.assertEqual(inv_cnt, 49)
        finally:
            conn.close()

    def test_05_database_divergence_mitigation_rehearsal(self):
        """
        Simulate new write in MySQL, extract divergence delta, and verify
        that if a rollback occurs, data can be safely back-propagated to SQLite.
        """
        rehearsal_email = "divergence_test_client@rehearsal.bizops.local"
        
        # 1. Simulate new customer created in MySQL
        with mysql_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO customers (user_id, name, email, company, status, ltv, total_spend, orders, joined, churn)
                VALUES (1, 'Divergence Test Client', :email, 'Divergence Corp', 'Active', '₹50,000', 50000.00, 2, 'Nov 2026', 5);
            """), {"email": rehearsal_email})
            conn.commit()

        # 2. Delta capture: Query MySQL for new writes since cutover timestamp
        delta_records = []
        with mysql_engine.connect() as conn:
            delta_rows = conn.execute(
                text("SELECT * FROM customers WHERE email = :email;"),
                {"email": rehearsal_email}
            ).mappings().fetchall()
            delta_records = [dict(r) for r in delta_rows]

        self.assertEqual(len(delta_records), 1)
        self.assertEqual(delta_records[0]["name"], "Divergence Test Client")

        # 3. Simulate replaying delta to isolated SQLite copy
        isolated_sqlite = sqlite3.connect(":memory:")
        isolated_sqlite.execute("""
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                name TEXT,
                email TEXT,
                company TEXT,
                status TEXT,
                ltv TEXT,
                total_spend REAL,
                orders INTEGER,
                joined TEXT,
                churn INTEGER
            );
        """)
        r = delta_records[0]
        isolated_sqlite.execute("""
            INSERT INTO customers (user_id, name, email, company, status, ltv, total_spend, orders, joined, churn)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (r["user_id"], r["name"], r["email"], r["company"], r["status"], r["ltv"], float(r["total_spend"]), r["orders"], r["joined"], r["churn"]))
        
        replayed_cnt = isolated_sqlite.execute("SELECT COUNT(*) FROM customers WHERE email = ?", (rehearsal_email,)).fetchone()[0]
        isolated_sqlite.close()
        self.assertEqual(replayed_cnt, 1, "Divergence delta must be 100% replayable to SQLite")

        # 4. Clean up rehearsal write from MySQL staging
        with mysql_engine.connect() as conn:
            conn.execute(text("DELETE FROM customers WHERE email = :email;"), {"email": rehearsal_email})
            conn.commit()


if __name__ == "__main__":
    unittest.main()
