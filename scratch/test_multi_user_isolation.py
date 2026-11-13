import sys
import os
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

print("[1] Importing FastAPI & TestClient...", flush=True)
from fastapi.testclient import TestClient
from ai_backend import app, get_db

client = TestClient(app)

print("[2] Logging in Account A (dinesh@test.com)...", flush=True)
res_login_a = client.post("/api/auth/login", json={"email": "dinesh@test.com", "password": "password123"})
print(f"  Account A status: {res_login_a.status_code}", flush=True)
assert res_login_a.status_code == 200, f"Login failed for Account A: {res_login_a.text}"

token_a = res_login_a.cookies.get("session_token")
headers_a = {"Cookie": f"session_token={token_a}"}

print("[3] Fetching Account A customers & stats...", flush=True)
res_cust_a = client.get("/api/customers", headers=headers_a)
assert res_cust_a.status_code == 200
print(f"  Dinesh Customers: {len(res_cust_a.json())}", flush=True)

res_stats_a = client.get("/api/dashboard/stats", headers=headers_a)
assert res_stats_a.status_code == 200
print(f"  Dinesh Stats: {res_stats_a.json()['kpis']['active_customers']} active customers", flush=True)

test_email_b = "test_tenant_b_isolated@bizops.local"
print(f"[4] Registering fresh Account B ({test_email_b})...", flush=True)

conn = get_db()
cursor = conn.cursor()
cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (test_email_b,))
existing_b = cursor.fetchone()
if existing_b:
    b_id = existing_b[0]
    cursor.execute("DELETE FROM user_sessions WHERE user_id = ?", (b_id,))
    cursor.execute("DELETE FROM customers WHERE user_id = ?", (b_id,))
    cursor.execute("DELETE FROM products WHERE user_id = ?", (b_id,))
    cursor.execute("DELETE FROM invoices WHERE user_id = ?", (b_id,))
    cursor.execute("DELETE FROM invoice_items WHERE user_id = ?", (b_id,))
    cursor.execute("DELETE FROM business_activities WHERE user_id = ?", (b_id,))
    cursor.execute("DELETE FROM notifications WHERE user_id = ?", (b_id,))
    cursor.execute("DELETE FROM users WHERE id = ?", (b_id,))
    conn.commit()
conn.close()

res_reg_b = client.post("/api/auth/register", json={
    "name": "Bob Founder",
    "email": test_email_b,
    "password": "SecurePassword123!",
    "company": "Bob Industries Ltd",
    "biz_type": "Logistics & Freight"
})
print(f"  Account B register status: {res_reg_b.status_code}", flush=True)
assert res_reg_b.status_code == 200, f"Register B failed: {res_reg_b.text}"
user_b_id = res_reg_b.json()["user"]["id"]

print("[5] Logging in Account B...", flush=True)
res_login_b = client.post("/api/auth/login", json={"email": test_email_b, "password": "SecurePassword123!"})
assert res_login_b.status_code == 200
token_b = res_login_b.cookies.get("session_token")
headers_b = {"Cookie": f"session_token={token_b}"}

print("[6] Checking Account B clean zero-data state...", flush=True)
res_cust_b = client.get("/api/customers", headers=headers_b)
assert len(res_cust_b.json()) == 0, f"Account B must have 0 customers, got {len(res_cust_b.json())}"

res_prod_b = client.get("/api/inventory", headers=headers_b)
assert len(res_prod_b.json()) == 0

res_inv_b = client.get("/api/invoices", headers=headers_b)
assert len(res_inv_b.json()) == 0

res_stats_b = client.get("/api/dashboard/stats", headers=headers_b)
kpis_b = res_stats_b.json()["kpis"]
print(f"  Account B KPIs: today={kpis_b['today_revenue']}, monthly={kpis_b['monthly_revenue']}, active_cust={kpis_b['active_customers']}, inv_health={kpis_b['inventory_health']}", flush=True)
assert kpis_b["today_revenue"] == "₹0"
assert kpis_b["monthly_revenue"] == "₹0"
assert kpis_b["active_customers"] == "0"
assert kpis_b["inventory_health"] == "0%"

print("[7] Creating Customer & Product & Invoice in Account B...", flush=True)
res_new_cust = client.post("/api/customers", headers=headers_b, json={
    "name": "Priya Sharma",
    "email": "priya@zenithlogistics.in",
    "company": "Zenith Freight Solutions",
    "status": "Active",
    "ltv": "₹0",
    "orders": 0,
    "total_spend": 0.0
})
assert res_new_cust.status_code == 200
cust_b_id = res_new_cust.json()["id"]

res_new_prod = client.post("/api/inventory", headers=headers_b, json={
    "name": "Fleet GPS Tracker X1",
    "sku": "FGT-100",
    "category": "Hardware",
    "stock": 40,
    "reorder": 10,
    "price": "₹8,500",
    "price_num": 8500.0,
    "status": "In Stock",
    "trend": "+5%"
})
assert res_new_prod.status_code == 200
prod_b_id = res_new_prod.json()["id"]

res_new_inv = client.post("/api/invoices", headers=headers_b, json={
    "client": "Zenith Freight Solutions",
    "due": "Oct 15, 2026",
    "status": "Paid",
    "tax": 18,
    "discount": 1000,
    "line_items": [{
        "product_id": prod_b_id,
        "quantity": 6,
        "unit_price": 8500.0,
        "product_name": "Fleet GPS Tracker X1"
    }]
})
assert res_new_inv.status_code == 200
created_inv_b = res_new_inv.json()
print(f"  Created invoice: {created_inv_b['id']}, total={created_inv_b['amount']}", flush=True)

# Verify product stock decreased in Account B
res_prod_after = client.get("/api/inventory", headers=headers_b)
matching_prod = next(p for p in res_prod_after.json() if p["id"] == prod_b_id)
print(f"  Stock after 6 units sold: {matching_prod['stock']} (Expected: 34)", flush=True)
assert matching_prod["stock"] == 34

# Verify customer orders increased
res_cust_after = client.get("/api/customers", headers=headers_b)
matching_cust = next(c for c in res_cust_after.json() if c["id"] == cust_b_id)
print(f"  Customer orders after invoice: {matching_cust['orders']} (Expected: 1)", flush=True)
assert matching_cust["orders"] == 1

print("[8] Testing IDOR Security: B tries accessing A's data...", flush=True)
assert client.put("/api/customers/1", headers=headers_b, json={"name": "Hacked"}).status_code == 404
assert client.delete("/api/customers/1", headers=headers_b).status_code == 404
assert client.get("/api/invoices/INV-2026-001", headers=headers_b).status_code == 404
assert client.delete("/api/invoices/INV-2026-001", headers=headers_b).status_code == 404
assert client.delete("/api/inventory/1", headers=headers_b).status_code == 404
print("  ✓ All IDOR attempts blocked (404 Not Found)", flush=True)

print("[9] Re-verifying Account A data isolation...", flush=True)
res_cust_a_again = client.get("/api/customers", headers=headers_a)
cust_names_a = [c["name"] for c in res_cust_a_again.json()]
assert "Priya Sharma" not in cust_names_a, "Account B data leaked into Account A!"
print("  ✓ Account A is strictly isolated from Account B!", flush=True)

print("\n" + "=" * 70, flush=True)
print("ALL TESTS PASSED SUCCESSFULLY! (100% VERIFIED)", flush=True)
print("=" * 70, flush=True)
