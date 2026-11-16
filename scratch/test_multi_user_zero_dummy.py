import sqlite3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from ai_backend import get_sales_overview, get_sales_forecast, get_dashboard_stats, compute_business_health

def run_tests():
    print("==================================================")
    print("RUNNING MULTI-USER & ZERO DUMMY DATA VERIFICATION")
    print("==================================================")

    # 1. Test User 1 (Populated Account)
    user_1 = {"id": 1, "name": "Dinesh", "email": "dinesh@example.com"}
    overview_1 = get_sales_overview(user=user_1)
    kpis_1 = overview_1["kpis"]
    print("\n--- User 1 (Populated Account) Sales Overview ---")
    print("KPIs:", kpis_1)
    print("Heatmap count:", len(overview_1["heatmap"]))
    print("Heatmap non-zero days:", sum(1 for d in overview_1["heatmap"] if d["sales"] > 0))
    print("Product categories:", overview_1["product_categories"])

    assert kpis_1["conversion_rate"] == "Not available", "Conversion rate must be 'Not available'"
    assert kpis_1["conversion_rate_change"] == "Not available"
    assert kpis_1["total_revenue"] in ["₹1.6L", "₹1,60,200"], f"Expected total revenue ₹1.6L or ₹1,60,200, got {kpis_1['total_revenue']}"
    assert kpis_1["total_orders"] == "2", f"Expected 2 orders, got {kpis_1['total_orders']}"
    assert kpis_1["avg_order_value"] == "₹80,100", f"Expected ₹80,100, got {kpis_1['avg_order_value']}"

    forecast_1 = get_sales_forecast(user=user_1)
    print("\n--- User 1 Sales Forecast ---")
    print("Forecast:", forecast_1)
    # User 1 has only 2 paid invoices (< 3 required for ML regression)
    assert forecast_1["has_forecast"] == False, "Forecast should be False when < 3 paid invoices"
    assert forecast_1["message"] == "Not enough sales data to generate a forecast."
    assert forecast_1["q3_forecast"] is None
    assert forecast_1["monthly_forecasts"] == []

    # 2. Test User 9999 (Completely Empty Account / New User)
    user_empty = {"id": 9999, "name": "New User", "email": "newuser@test.com"}
    overview_empty = get_sales_overview(user=user_empty)
    kpis_empty = overview_empty["kpis"]
    print("\n--- User 9999 (New / Empty Account) Sales Overview ---")
    print("KPIs:", kpis_empty)
    print("Product categories:", overview_empty["product_categories"])

    assert kpis_empty["total_revenue"] == "₹0", f"Expected ₹0 revenue, got {kpis_empty['total_revenue']}"
    assert kpis_empty["total_orders"] == "0", f"Expected 0 orders, got {kpis_empty['total_orders']}"
    assert kpis_empty["avg_order_value"] == "₹0", f"Expected ₹0 AOV, got {kpis_empty['avg_order_value']}"
    assert kpis_empty["conversion_rate"] == "Not available"
    assert kpis_empty["total_revenue_change"] == "Not enough data"
    assert kpis_empty["total_orders_change"] == "Not enough data"
    assert kpis_empty["avg_order_value_change"] == "Not enough data"
    assert overview_empty["product_categories"] == [], "Empty account must have empty product categories"
    assert all(d["sales"] == 0 and d["intensity"] == 0 for d in overview_empty["heatmap"]), "Empty account heatmap must be all 0s"

    forecast_empty = get_sales_forecast(user=user_empty)
    print("\n--- User 9999 Sales Forecast ---")
    print("Forecast:", forecast_empty)
    assert forecast_empty["has_forecast"] == False
    assert forecast_empty["message"] == "Not enough sales data to generate a forecast."
    assert forecast_empty["monthly_forecasts"] == []

    health_empty = compute_business_health(user_id=9999)
    print("\n--- User 9999 Business Health ---")
    print("Health:", health_empty["overall_score"], health_empty["health_level"])
    assert health_empty["overall_score"] == 0
    assert health_empty["health_level"] == "New Workspace"

    dashboard_empty = get_dashboard_stats(user=user_empty)
    print("\n--- User 9999 Dashboard Stats ---")
    print("Dashboard KPIs:", dashboard_empty["kpis"])
    assert dashboard_empty["kpis"]["today_revenue"] == "₹0"
    assert dashboard_empty["kpis"]["monthly_revenue"] == "₹0"
    assert dashboard_empty["kpis"]["active_customers"] == "0"
    assert dashboard_empty["kpis"]["pending_orders"] == "0"

    print("\n==================================================")
    print("ALL TESTS PASSED! ZERO DUMMY DATA & REAL MULTI-USER ISOLATION CONFIRMED!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()

def test_forecast_with_sufficient_data():
    print("\n--- User with >= 3 Paid Invoices Test ---")
    conn = sqlite3.connect('backend/ai_bizops.db')
    cursor = conn.cursor()
    # Create temp user 7777 with 4 paid invoices
    cursor.execute("DELETE FROM invoices WHERE user_id = 7777")
    sample_invoices = [
        ("INV-TEST-01", 7777, "Client A", "₹50,000", 50000.0, "2026-05-15", "2026-05-15", "Paid"),
        ("INV-TEST-02", 7777, "Client B", "₹65,000", 65000.0, "2026-06-15", "2026-06-15", "Paid"),
        ("INV-TEST-03", 7777, "Client C", "₹80,000", 80000.0, "2026-07-15", "2026-07-15", "Paid"),
        ("INV-TEST-04", 7777, "Client D", "₹95,000", 95000.0, "2026-08-15", "2026-08-15", "Paid"),
    ]
    cursor.executemany("""
    INSERT INTO invoices (id, user_id, client, amount, amount_num, due, issued, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_invoices)
    conn.commit()
    conn.close()

    try:
        user_7777 = {"id": 7777, "name": "Growth Co", "email": "growth@test.com"}
        fc = get_sales_forecast(user=user_7777)
        print("Forecast for 7777:", fc)
        assert fc["has_forecast"] == True
        assert len(fc["monthly_forecasts"]) == 3
        assert fc["q3_forecast"] is not None
        assert "L" in fc["q3_forecast"] or "₹" in fc["q3_forecast"]
        print("Forecast with >= 3 invoices verified successfully!")
    finally:
        conn = sqlite3.connect('backend/ai_bizops.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM invoices WHERE user_id = 7777")
        conn.commit()
        conn.close()

test_forecast_with_sufficient_data()
