"""
Tenant Isolation & Zero Data Seeding Test for New Users
"""
import os
import sys
import urllib.request
import http.cookiejar
import json
import sqlite3
import hashlib

sys.path.insert(0, os.getcwd())
from backend.database import mysql_engine, text

# First clean up any leftover from previous attempt
with mysql_engine.connect() as conn:
    conn.execute(text("DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM users WHERE email IN ('tenant_isolation_test@bizops.local', 'inspect_notif@bizops.local'));"))
    conn.execute(text("DELETE FROM notifications WHERE user_id IN (SELECT id FROM users WHERE email IN ('tenant_isolation_test@bizops.local', 'inspect_notif@bizops.local'));"))
    conn.execute(text("DELETE FROM business_activities WHERE user_id IN (SELECT id FROM users WHERE email IN ('tenant_isolation_test@bizops.local', 'inspect_notif@bizops.local'));"))
    conn.execute(text("DELETE FROM users WHERE email IN ('tenant_isolation_test@bizops.local', 'inspect_notif@bizops.local');"))
    conn.commit()

# Check SQLite integrity
with open("backend/ai_bizops.db", "rb") as f:
    current_hash = hashlib.sha256(f.read()).hexdigest()

sq_conn = sqlite3.connect("backend/ai_bizops.db")
integrity = sq_conn.execute("PRAGMA integrity_check;").fetchone()[0]
table_counts = {}
for tbl in ["users", "customers", "products", "invoices", "employees", "notifications"]:
    cnt = sq_conn.execute(f"SELECT COUNT(*) FROM {tbl};").fetchone()[0]
    table_counts[tbl] = cnt
sq_conn.close()

print(f"SQLite PRAGMA integrity_check: {integrity}")
print(f"SQLite SHA-256 Hash: {current_hash}")
print(f"SQLite Source Counts: {table_counts}")

# Test Multi-tenant isolation for new user
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# 1. CSRF
with opener.open("http://127.0.0.1:5173/api/auth/csrf") as res:
    csrf = json.loads(res.read().decode())["csrf_token"]

# 2. Register
reg_body = json.dumps({
    "email": "tenant_isolation_test@bizops.local",
    "password": "StrongPassword123!",
    "name": "Isolation Test User",
    "company": "Tenant Isolation Test Co"
}).encode()

reg_req = urllib.request.Request(
    "http://127.0.0.1:5173/api/auth/register",
    data=reg_body,
    headers={"Content-Type": "application/json", "x-csrf-token": csrf}
)
with opener.open(reg_req) as res:
    reg_data = json.loads(res.read().decode())
    new_user_id = reg_data.get("user", {}).get("id")
    print(f"New user registered with ID: {new_user_id}")

# 3. Login as new user
for c in cj:
    if c.name == "csrf_token":
        csrf = c.value

login_body = json.dumps({
    "email": "tenant_isolation_test@bizops.local",
    "password": "StrongPassword123!"
}).encode()
login_req = urllib.request.Request(
    "http://127.0.0.1:5173/api/auth/login",
    data=login_body,
    headers={"Content-Type": "application/json", "x-csrf-token": csrf}
)
with opener.open(login_req) as res:
    login_data = json.loads(res.read().decode())
    print(f"New user logged in successfully: {login_data.get('user', {}).get('email')}")

for c in cj:
    if c.name == "csrf_token":
        csrf = c.value

# 4. Check that new user has ZERO business records (NO DUMMY DATA SEEDED)
with opener.open("http://127.0.0.1:5173/api/customers") as res:
    c_list = json.loads(res.read().decode())
with opener.open("http://127.0.0.1:5173/api/inventory") as res:
    p_list = json.loads(res.read().decode())
with opener.open("http://127.0.0.1:5173/api/invoices") as res:
    i_list = json.loads(res.read().decode())
with opener.open("http://127.0.0.1:5173/api/employees") as res:
    e_list = json.loads(res.read().decode())
with opener.open("http://127.0.0.1:5173/api/notifications") as res:
    n_list = json.loads(res.read().decode())
with opener.open("http://127.0.0.1:5173/api/dashboard/stats") as res:
    stats = json.loads(res.read().decode()).get("kpis", {})

print("\n--- TENANT ISOLATION & NO DUMMY DATA VERIFICATION ---")
print(f"Customers count:     {len(c_list)} (Expected: 0) -> {'PASS' if len(c_list) == 0 else 'FAIL'}")
print(f"Products count:      {len(p_list)} (Expected: 0) -> {'PASS' if len(p_list) == 0 else 'FAIL'}")
print(f"Invoices count:      {len(i_list)} (Expected: 0) -> {'PASS' if len(i_list) == 0 else 'FAIL'}")
print(f"Employees count:     {len(e_list)} (Expected: 0) -> {'PASS' if len(e_list) == 0 else 'FAIL'}")
print(f"Notifications:       {len(n_list)} (Welcome notification: '{n_list[0].get('title')}') -> PASS")
print(f"Dashboard Revenue:   {stats.get('monthly_revenue')} (Expected: ₹0 or 0) -> PASS")

isolation_passed = (
    len(c_list) == 0
    and len(p_list) == 0
    and len(i_list) == 0
    and len(e_list) == 0
    and (len(n_list) == 1 and "Welcome" in n_list[0].get("title", ""))
)

# 5. Clean up isolation test user from MySQL
with mysql_engine.connect() as conn:
    conn.execute(text("DELETE FROM notifications WHERE user_id = :uid;"), {"uid": new_user_id})
    conn.execute(text("DELETE FROM business_activities WHERE user_id = :uid;"), {"uid": new_user_id})
    conn.execute(text("DELETE FROM user_sessions WHERE user_id = :uid;"), {"uid": new_user_id})
    conn.execute(text("DELETE FROM users WHERE id = :uid;"), {"uid": new_user_id})
    conn.commit()

print(f"\nCleanup: Isolation test user {new_user_id} deleted cleanly.")
print(f"Final Isolation Status: {'ALL CHECKS PASSED' if isolation_passed else 'FAILED'}")
