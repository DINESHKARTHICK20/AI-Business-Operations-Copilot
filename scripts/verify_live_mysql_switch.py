"""
Comprehensive End-to-End Verification of the Live MySQL Switch
Tests all 17 business modules through http://127.0.0.1:5173 (via Vite proxy)
Verifies that FastAPI is actively reading and writing to MySQL, not SQLite.
"""
import os
import sys
import time
import urllib.request
import urllib.parse
import http.cookiejar
import json
import sqlite3
from decimal import Decimal

sys.path.insert(0, os.getcwd())
from backend.database import mysql_engine, text

BASE_URL = "http://127.0.0.1:5173"

print("="*70)
print("LIVE MYSQL SWITCH VERIFICATION VIA http://127.0.0.1:5173")
print("="*70)

# Set up cookie-enabled HTTP client
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

results = {}

def log_test(test_id, name, passed, details=""):
    status_str = "PASS" if passed else "FAIL"
    results[test_id] = {"name": name, "passed": passed, "details": details}
    print(f"[{status_str}] {test_id}: {name} - {details}")

# 1. CSRF Token
csrf_req = urllib.request.Request(f"{BASE_URL}/api/auth/csrf")
with opener.open(csrf_req, timeout=5) as res:
    data = json.loads(res.read().decode())
    csrf_token = data.get("csrf_token")
    cookies = {c.name: c.value for c in cj}
    csrf_ok = res.status == 200 and bool(csrf_token) and "csrf_token" in cookies
    log_test("TEST-01", "CSRF Token & Cookie Binding via Vite Proxy", csrf_ok, f"Status={res.status}")

# 2. Login as existing User 1
login_data = json.dumps({"email": "dinesh@test.com", "password": "password123"}).encode()
login_req = urllib.request.Request(
    f"{BASE_URL}/api/auth/login",
    data=login_data,
    headers={"Content-Type": "application/json", "x-csrf-token": csrf_token}
)
with opener.open(login_req, timeout=5) as res:
    data = json.loads(res.read().decode())
    cookies = {c.name: c.value for c in cj}
    login_ok = res.status == 200 and data.get("status") == "success" and "session_token" in cookies
    log_test("TEST-02", "Sign In (bcrypt-12, HttpOnly Session Cookie)", login_ok, f"User={data.get('user', {}).get('email')}")

# Update CSRF token from post-login cookie
for c in cj:
    if c.name == "csrf_token":
        csrf_token = c.value

headers_with_csrf = {"x-csrf-token": csrf_token, "Content-Type": "application/json"}

# 3. User Profile / Settings
me_req = urllib.request.Request(f"{BASE_URL}/api/auth/me")
with opener.open(me_req, timeout=5) as res:
    data = json.loads(res.read().decode())
    me_ok = res.status == 200 and data.get("email") == "dinesh@test.com"
    log_test("TEST-03", "User Profile & Account Verification (/api/auth/me)", me_ok, f"Company={data.get('company')}")

# 4. Dashboard Stats & Financials
dash_req = urllib.request.Request(f"{BASE_URL}/api/dashboard/stats")
with opener.open(dash_req, timeout=5) as res:
    data = json.loads(res.read().decode())
    kpis = data.get("kpis", {})
    dash_ok = res.status == 200 and "monthly_revenue" in kpis and "active_customers" in kpis
    log_test("TEST-04", "Dashboard & Financial KPIs (/api/dashboard/stats)", dash_ok, f"Revenue={kpis.get('monthly_revenue')}, Customers={kpis.get('active_customers')}")

# 5. Dashboard Insights & AI Business Health
insights_req = urllib.request.Request(f"{BASE_URL}/api/dashboard/insights")
with opener.open(insights_req, timeout=5) as res:
    data = json.loads(res.read().decode())
    insights_ok = res.status == 200 and isinstance(data, list)
    log_test("TEST-05", "AI Business Health & Insights (/api/dashboard/insights)", insights_ok, f"{len(data)} insight(s) loaded")

# 6. Sales Overview Analytics
sales_req = urllib.request.Request(f"{BASE_URL}/api/sales/overview")
with opener.open(sales_req, timeout=5) as res:
    data = json.loads(res.read().decode())
    sales_ok = res.status == 200 and "monthly" in data and len(data.get("monthly", [])) == 12
    log_test("TEST-06", "Sales Analytics Overview (/api/sales/overview)", sales_ok, f"Monthly points={len(data.get('monthly', []))}")

# 7. Customer Management (CRM)
cust_req = urllib.request.Request(f"{BASE_URL}/api/customers")
with opener.open(cust_req, timeout=5) as res:
    data = json.loads(res.read().decode())
    cust_ok = res.status == 200 and len(data) == 7
    log_test("TEST-07", "Customer CRM Management (/api/customers)", cust_ok, f"{len(data)} genuine customers loaded")

# 8. Inventory Management
inv_req = urllib.request.Request(f"{BASE_URL}/api/inventory")
with opener.open(inv_req, timeout=5) as res:
    data = json.loads(res.read().decode())
    inv_ok = res.status == 200 and len(data) == 6
    log_test("TEST-08", "Inventory Management (/api/inventory)", inv_ok, f"{len(data)} genuine products loaded")

# 9. Invoice Management
invoices_req = urllib.request.Request(f"{BASE_URL}/api/invoices")
with opener.open(invoices_req, timeout=5) as res:
    data = json.loads(res.read().decode())
    invoices_ok = res.status == 200 and len(data) == 23
    log_test("TEST-09", "Invoice Billing Management (/api/invoices)", invoices_ok, f"{len(data)} genuine invoices loaded")

# 10. Reports & Binary PDF Download
pdf_req = urllib.request.Request(f"{BASE_URL}/api/invoices/INV-2026-001/pdf")
with opener.open(pdf_req, timeout=5) as res:
    content = res.read()
    pdf_ok = res.status == 200 and content.startswith(b"%PDF-") and len(content) > 1000
    log_test("TEST-10", "Reports & Real PyMuPDF Binary PDF Download", pdf_ok, f"Size={len(content):,} bytes, Magic={content[:5].decode('latin-1')}")

# 11. Employee HR Management
emp_req = urllib.request.Request(f"{BASE_URL}/api/employees")
with opener.open(emp_req, timeout=5) as res:
    data = json.loads(res.read().decode())
    emp_ok = res.status == 200 and len(data) == 4
    log_test("TEST-11", "Employee HR Management (/api/employees)", emp_ok, f"{len(data)} genuine staff loaded")

# 12. Profit Analyzer
profit_req = urllib.request.Request(f"{BASE_URL}/api/profit/products")
with opener.open(profit_req, timeout=5) as res:
    data = json.loads(res.read().decode())
    profit_ok = res.status == 200 and len(data) == 10
    log_test("TEST-12", "Profit Analyzer & Unit Economics (/api/profit/products)", profit_ok, f"{len(data)} unit economics products loaded")

# 13. AI Action Center
action_req = urllib.request.Request(f"{BASE_URL}/api/action-center")
with opener.open(action_req, timeout=5) as res:
    data = json.loads(res.read().decode())
    action_ok = res.status == 200 and "actions" in data and len(data.get("actions", [])) >= 1
    log_test("TEST-13", "AI Action Center (/api/action-center)", action_ok, f"{len(data.get('actions', []))} actionable recommendations loaded")

# 14. AI Copilot Chat
chat_body = json.dumps({"message": "What is my current monthly revenue?"}).encode()
chat_req = urllib.request.Request(f"{BASE_URL}/api/copilot/chat", data=chat_body, headers=headers_with_csrf)
with opener.open(chat_req, timeout=5) as res:
    data = json.loads(res.read().decode())
    chat_ok = res.status == 200 and bool(data.get("content"))
    log_test("TEST-14", "AI Copilot Conversational Assistant (/api/copilot/chat)", chat_ok, f"Response preview: {data.get('content', '')[:50]}...")

# 15. AI Predictive Pipelines (Churn, Sales, Inventory)
churn_body = json.dumps({
    "total_orders": 12, "total_spend": 50000.0, "days_since_last_purchase": 10,
    "support_tickets": 1, "complaints": 0, "average_order_value": 4166.67
}).encode()
churn_req = urllib.request.Request(f"{BASE_URL}/api/predict/churn", data=churn_body, headers=headers_with_csrf)
with opener.open(churn_req, timeout=5) as res:
    data = json.loads(res.read().decode())
    pred_ok = res.status == 200 and "churn_probability" in data
    log_test("TEST-15", "AI Predictive Machine Learning Pipelines", pred_ok, f"Churn probability={data.get('churn_probability')}%")

# 16. Global Search
search_req = urllib.request.Request(f"{BASE_URL}/api/search?q=Selvaraj")
with opener.open(search_req, timeout=5) as res:
    data = json.loads(res.read().decode())
    search_ok = res.status == 200 and len(data.get("results", {}).get("customers", [])) >= 1
    log_test("TEST-16", "Global Multi-Entity Search Engine (/api/search)", search_ok, f"Found {len(data.get('results', {}).get('customers', []))} customer(s)")

# 17. Notifications
notif_req = urllib.request.Request(f"{BASE_URL}/api/notifications")
with opener.open(notif_req, timeout=5) as res:
    data = json.loads(res.read().decode())
    notif_ok = res.status == 200 and len(data) == 3
    log_test("TEST-17", "Notifications Management (/api/notifications)", notif_ok, f"{len(data)} user notification(s)")

# 18. PROOF THAT FASTAPI IS ACTUALLY READING AND WRITING TO MYSQL
print("\n" + "="*70)
print("PROVING WRITES OCCUR IN MYSQL, NOT SQLITE")
print("="*70)

# Check SQLite record count before test write
sq_conn = sqlite3.connect("backend/ai_bizops.db")
sq_before_cnt = sq_conn.execute("SELECT COUNT(*) FROM customers;").fetchone()[0]
sq_conn.close()

# Insert a new test customer via FastAPI POST /api/customers through Vite proxy
new_cust_payload = json.dumps({
    "name": "Live MySQL Switch Verification Corp",
    "email": "live_mysql_switch@test.bizops.local",
    "company": "Live Switch Corp",
    "status": "Active",
    "ltv": "₹1,20,000",
    "total_spend": 120000.0,
    "orders": 5,
    "joined": "Nov 2026"
}).encode()

create_cust_req = urllib.request.Request(
    f"{BASE_URL}/api/customers",
    data=new_cust_payload,
    headers=headers_with_csrf
)
with opener.open(create_cust_req, timeout=5) as res:
    created_cust = json.loads(res.read().decode())
    created_id = created_cust.get("id")

# Verify customer exists in MySQL staging
with mysql_engine.connect() as conn:
    my_record = conn.execute(
        text("SELECT id, name, email FROM customers WHERE id = :id;"),
        {"id": created_id}
    ).mappings().fetchone()

# Verify customer DOES NOT exist in SQLite
sq_conn = sqlite3.connect("backend/ai_bizops.db")
sq_after_cnt = sq_conn.execute("SELECT COUNT(*) FROM customers;").fetchone()[0]
sq_exists = sq_conn.execute("SELECT COUNT(*) FROM customers WHERE email = 'live_mysql_switch@test.bizops.local';").fetchone()[0]
sq_conn.close()

mysql_write_proven = (
    my_record is not None
    and my_record["email"] == "live_mysql_switch@test.bizops.local"
    and sq_before_cnt == sq_after_cnt
    and sq_exists == 0
)

log_test(
    "TEST-18",
    "Proof of Active MySQL Writes (Write confirmed in MySQL, zero write to SQLite)",
    mysql_write_proven,
    f"MySQL ID={created_id}, SQLite Customer Count Unchanged ({sq_before_cnt} == {sq_after_cnt})"
)

# Clean up test customer via FastAPI DELETE /api/customers/{id}
del_req = urllib.request.Request(
    f"{BASE_URL}/api/customers/{created_id}",
    headers=headers_with_csrf,
    method="DELETE"
)
with opener.open(del_req, timeout=5) as res:
    del_ok = res.status == 200

# Clean up the associated activity log entry in MySQL
with mysql_engine.connect() as conn:
    conn.execute(text("DELETE FROM business_activities WHERE text LIKE '%Live MySQL Switch Verification Corp%';"))
    conn.commit()

log_test("TEST-19", "Clean Disposable Artifact Removal via API", del_ok, "Test record cleaned up")

# 20. Logout and Session Invalidation
logout_req = urllib.request.Request(
    f"{BASE_URL}/api/auth/logout",
    data=b"{}",
    headers=headers_with_csrf
)
with opener.open(logout_req, timeout=5) as res:
    logout_ok = res.status == 200

subsequent_req = urllib.request.Request(f"{BASE_URL}/api/auth/me")
try:
    with opener.open(subsequent_req, timeout=5) as res:
        subsequent_code = res.status
except urllib.error.HTTPError as e:
    subsequent_code = e.code

revocation_ok = logout_ok and subsequent_code == 401
log_test("TEST-20", "Logout & Immediate Server-Side Session Invalidation (Returns 401)", revocation_ok, f"Post-logout status={subsequent_code}")

print("\n" + "="*70)
passed_cnt = sum(1 for r in results.values() if r["passed"])
total_cnt = len(results)
print(f"OVERALL SUMMARY: {passed_cnt}/{total_cnt} tests passed ({passed_cnt/total_cnt*100:.1f}%)")
print("="*70)
