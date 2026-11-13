import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from ai_backend import (
    get_db,
    CustomerCreate,
    ProductCreate,
    InvoiceCreate,
    InvoiceItemInput,
    InvoiceStatusUpdate,
    CopilotChatRequest,
    get_customers,
    create_customer,
    update_customer,
    delete_customer,
    predict_customer_churn_by_id,
    get_employees,
    create_employee,
    get_inventory,
    create_product,
    update_product,
    delete_product,
    get_invoices,
    get_invoice,
    create_invoice,
    update_invoice_status,
    delete_invoice,
    get_dashboard_stats,
    get_dashboard_insights,
    get_dashboard_activity,
    get_sales_overview,
    get_sales_forecast,
    compute_business_health,
    get_notifications,
    mark_all_notifications_read,
    get_action_center,
    copilot_chat,
    HTTPException
)

print("=" * 70)
print("TESTING MULTI-USER ISOLATION & DYNAMIC DATA DIRECTLY")
print("=" * 70)

# Setup User A (Dinesh, ID: 1) and User B (Test User, ID: 9999)
user_a = {"id": 1, "name": "Dinesh", "email": "dinesh@test.com", "company": "TechCorp India Pvt. Ltd"}
user_b = {"id": 9999, "name": "Bob Founder", "email": "bob@isolated.local", "company": "Bob Logistics Ltd"}

# Clean up any leftover data for User B
conn = get_db()
cursor = conn.cursor()
cursor.execute("DELETE FROM customers WHERE user_id = 9999")
cursor.execute("DELETE FROM products WHERE user_id = 9999")
cursor.execute("DELETE FROM invoices WHERE user_id = 9999")
cursor.execute("DELETE FROM invoice_items WHERE user_id = 9999")
cursor.execute("DELETE FROM employees WHERE user_id = 9999")
cursor.execute("DELETE FROM business_activities WHERE user_id = 9999")
cursor.execute("DELETE FROM notifications WHERE user_id = 9999")
conn.commit()
conn.close()

# -------------------------------------------------------------
# 1. VERIFY ACCOUNT A PRESERVED DATA
# -------------------------------------------------------------
print("\n[Step 1] Verifying Account A (Dinesh - ID 1) pre-existing data...")
cust_a = get_customers(user_a)
prod_a = get_inventory(user_a)
inv_a = get_invoices(user_a)
stats_a = get_dashboard_stats(user_a)

print(f"  ✓ Dinesh Customers: {len(cust_a)} (Expected >= 6)")
print(f"  ✓ Dinesh Products: {len(prod_a)} (Expected >= 5)")
print(f"  ✓ Dinesh Invoices: {len(inv_a)} (Expected >= 5)")
print(f"  ✓ Dinesh Stats: active_customers={stats_a['kpis']['active_customers']}, monthly_rev={stats_a['kpis']['monthly_revenue']}")

assert len(cust_a) >= 6, "Dinesh's customers lost!"
assert len(prod_a) >= 5, "Dinesh's products lost!"
assert len(inv_a) >= 5, "Dinesh's invoices lost!"

# -------------------------------------------------------------
# 2. VERIFY ACCOUNT B EMPTY WORKSPACE
# -------------------------------------------------------------
print("\n[Step 2] Verifying Account B (Bob - ID 9999) fresh workspace is completely clean...")
cust_b = get_customers(user_b)
prod_b = get_inventory(user_b)
inv_b = get_invoices(user_b)
emp_b = get_employees(user_b)
stats_b = get_dashboard_stats(user_b)
health_b = compute_business_health(user_b["id"])
sales_fc_b = get_sales_forecast(user_b)

print(f"  ✓ Bob Customers: {len(cust_b)} (Must be 0)")
print(f"  ✓ Bob Products: {len(prod_b)} (Must be 0)")
print(f"  ✓ Bob Invoices: {len(inv_b)} (Must be 0)")
print(f"  ✓ Bob Employees: {len(emp_b)} (Must be 0)")
print(f"  ✓ Bob Dashboard KPIs: today={stats_b['kpis']['today_revenue']}, monthly={stats_b['kpis']['monthly_revenue']}, active_cust={stats_b['kpis']['active_customers']}, inv_health={stats_b['kpis']['inventory_health']}")
print(f"  ✓ Bob Business Health: {health_b['overall_score']}/100, level='{health_b['health_level']}'")
print(f"  ✓ Bob Sales Forecast Insufficient Data: {sales_fc_b.get('insufficient_data')}")

assert len(cust_b) == 0, f"Account B should have 0 customers, got {len(cust_b)}"
assert len(prod_b) == 0, f"Account B should have 0 products, got {len(prod_b)}"
assert len(inv_b) == 0, f"Account B should have 0 invoices, got {len(inv_b)}"
assert stats_b['kpis']['today_revenue'] == "₹0"
assert stats_b['kpis']['monthly_revenue'] == "₹0"
assert stats_b['kpis']['active_customers'] == "0"
assert stats_b['kpis']['inventory_health'] == "0%"
assert health_b['overall_score'] == 0
assert sales_fc_b['insufficient_data'] is True

# -------------------------------------------------------------
# 3. ACCOUNT B CREATES DATA & ATOMIC INVOICE STOCK DECREMENT
# -------------------------------------------------------------
print("\n[Step 3] Account B creates customer, product, and invoice...")

# Create customer
new_cust = create_customer(CustomerCreate(
    name="Vikram Sethi",
    email="vikram@speedfreight.in",
    company="SpeedFreight Logistics Pvt Ltd",
    status="Active",
    ltv="₹0",
    orders=0,
    total_spend=0.0
), user_b)
print(f"  ✓ Created Customer: ID={new_cust['id']}, Name='{new_cust['name']}'")

# Create product with stock 50
new_prod = create_product(ProductCreate(
    name="Vehicle GPS Tracker Unit",
    sku="VGT-99",
    category="Hardware",
    stock=50,
    reorder=15,
    price="₹6,500",
    price_num=6500.0,
    status="In Stock",
    trend="+10%"
), user_b)
print(f"  ✓ Created Product: ID={new_prod['id']}, Stock={new_prod['stock']}")

# Create invoice for 8 units of Vehicle GPS Tracker Unit
print("  Creating invoice for 8 units (Expected: 50 - 8 = 42 stock remaining)...")
new_inv = create_invoice(InvoiceCreate(
    client="SpeedFreight Logistics Pvt Ltd",
    due="Oct 30, 2026",
    status="Paid",
    tax=18,
    discount=500,
    line_items=[
        InvoiceItemInput(product_id=new_prod["id"], quantity=8, unit_price=6500.0, product_name=new_prod["name"])
    ]
), user_b)
print(f"  ✓ Created Invoice: ID={new_inv['id']}, Total={new_inv['amount']}")

# Verify product stock decreased
prods_b_after = get_inventory(user_b)
prod_matching = next(p for p in prods_b_after if p["id"] == new_prod["id"])
print(f"  ✓ Product stock after invoice: {prod_matching['stock']} (Expected: 42)")
assert prod_matching["stock"] == 42, f"Stock decrement failed! Expected 42, got {prod_matching['stock']}"

# Verify customer order count increased
custs_b_after = get_customers(user_b)
cust_matching = next(c for c in custs_b_after if c["id"] == new_cust["id"])
print(f"  ✓ Customer orders after invoice: {cust_matching['orders']} (Expected: 1)")
assert cust_matching["orders"] == 1, f"Customer orders failed! Expected 1, got {cust_matching['orders']}"

# Verify Account B Dashboard now shows dynamic real stats
stats_b_after = get_dashboard_stats(user_b)
print(f"  ✓ Account B Dashboard after invoice: active_customers={stats_b_after['kpis']['active_customers']}, inv_health={stats_b_after['kpis']['inventory_health']}, monthly_rev={stats_b_after['kpis']['monthly_revenue']}")
assert stats_b_after['kpis']['active_customers'] == "1"
assert stats_b_after['kpis']['inventory_health'] == "100%"

# -------------------------------------------------------------
# 4. IDOR ATTACK PREVENTION TESTS
# -------------------------------------------------------------
print("\n[Step 4] Testing IDOR Security: Account B attempts access to Account A's records...")

# B attempts to access A's invoice (INV-2026-001)
try:
    get_invoice("INV-2026-001", user_b)
    assert False, "IDOR: Account B accessed Account A's invoice!"
except HTTPException as e:
    assert e.status_code == 404
    print("  ✓ GET /api/invoices/INV-2026-001 blocked with 404 Not Found")

# B attempts to delete A's invoice
try:
    delete_invoice("INV-2026-001", user_b)
    assert False, "IDOR: Account B deleted Account A's invoice!"
except HTTPException as e:
    assert e.status_code == 404
    print("  ✓ DELETE /api/invoices/INV-2026-001 blocked with 404 Not Found")

# B attempts to delete A's customer (ID: 1)
try:
    delete_customer(1, user_b)
    assert False, "IDOR: Account B deleted Account A's customer!"
except HTTPException as e:
    assert e.status_code == 404
    print("  ✓ DELETE /api/customers/1 blocked with 404 Not Found")

# B attempts to delete A's product (ID: 1)
try:
    delete_product(1, user_b)
    assert False, "IDOR: Account B deleted Account A's product!"
except HTTPException as e:
    assert e.status_code == 404
    print("  ✓ DELETE /api/inventory/1 blocked with 404 Not Found")

# -------------------------------------------------------------
# 5. RE-VERIFY ACCOUNT A (ZERO LEAKAGE)
# -------------------------------------------------------------
print("\n[Step 5] Re-verifying Account A data isolation...")
cust_a_final = get_customers(user_a)
prod_a_final = get_inventory(user_a)
inv_a_final = get_invoices(user_a)

cust_names_a = [c["name"] for c in cust_a_final]
prod_names_a = [p["name"] for p in prod_a_final]

assert "Vikram Sethi" not in cust_names_a, "Data Leakage: Bob's customer found in Dinesh's account!"
assert "Vehicle GPS Tracker Unit" not in prod_names_a, "Data Leakage: Bob's product found in Dinesh's account!"
print("  ✓ Account A completely isolated (zero data leakage from Account B)")

print("\n" + "=" * 70)
print("ALL MULTI-USER ISOLATION TESTS PASSED WITH 100% SUCCESS!")
print("=" * 70)

