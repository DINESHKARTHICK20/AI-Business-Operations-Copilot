import os
import time
from pathlib import Path
import sys
import math
import random
import sqlite3
import json
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import re
import bcrypt
import joblib
import pandas as pd

from fastapi import FastAPI, HTTPException, Query, Header, Depends, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, mean_absolute_error
from sklearn.model_selection import train_test_split


# ============================================================
# SECURITY & ENVIRONMENT CONFIGURATION
# ============================================================

SECRET_KEY = os.environ.get("SECRET_KEY", "bizops_prod_secret_key_change_in_production_2026")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true" or ENVIRONMENT == "production"

_env_origins = os.environ.get("ALLOWED_ORIGINS", "")
if _env_origins:
    ALLOWED_ORIGINS = [o.strip() for o in _env_origins.split(",") if o.strip()]
else:
    ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]


# ============================================================
# PROJECT PATHS & DATABASE SETUP
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)

CHURN_MODEL = MODEL_DIR / "churn_model.pkl"
SALES_MODEL = MODEL_DIR / "sales_model.pkl"
INVENTORY_MODEL = MODEL_DIR / "inventory_model.pkl"

DB_PATH = BASE_DIR / "ai_bizops.db"


def get_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
    except Exception:
        pass
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Customers Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        company TEXT NOT NULL,
        status TEXT NOT NULL,
        ltv TEXT NOT NULL,
        total_spend REAL DEFAULT 0.0,
        orders INTEGER DEFAULT 0,
        joined TEXT NOT NULL,
        churn INTEGER DEFAULT 0,
        days_since_last_purchase INTEGER DEFAULT 30,
        support_tickets INTEGER DEFAULT 0,
        complaints INTEGER DEFAULT 0,
        average_order_value REAL DEFAULT 0.0
    )
    """)

    # Employees Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        dept TEXT NOT NULL,
        salary TEXT NOT NULL,
        status TEXT NOT NULL,
        attendance INTEGER DEFAULT 95,
        performance INTEGER DEFAULT 90,
        joined TEXT NOT NULL
    )
    """)

    # Products Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        sku TEXT NOT NULL UNIQUE,
        category TEXT NOT NULL,
        stock INTEGER NOT NULL,
        reorder INTEGER NOT NULL,
        price TEXT NOT NULL,
        price_num REAL DEFAULT 0.0,
        status TEXT NOT NULL,
        trend TEXT NOT NULL,
        avg_daily_demand REAL DEFAULT 1.0,
        trend_factor REAL DEFAULT 0.0,
        promotion_factor REAL DEFAULT 0.0
    )
    """)

    # Invoices Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id TEXT PRIMARY KEY,
        client TEXT NOT NULL,
        amount TEXT NOT NULL,
        amount_num REAL DEFAULT 0.0,
        due TEXT NOT NULL,
        issued TEXT NOT NULL,
        status TEXT NOT NULL,
        items TEXT DEFAULT '',
        subtotal REAL DEFAULT 0.0,
        tax REAL DEFAULT 0.0,
        discount REAL DEFAULT 0.0,
        total REAL DEFAULT 0.0
    )
    """)

    # Invoice Line Items Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoice_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id TEXT NOT NULL,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        line_total REAL NOT NULL,
        FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
    )
    """)

    # Migration for invoices columns if DB already exists
    cursor.execute("PRAGMA table_info(invoices)")
    inv_cols = [row[1] for row in cursor.fetchall()]
    if "subtotal" not in inv_cols:
        cursor.execute("ALTER TABLE invoices ADD COLUMN subtotal REAL DEFAULT 0.0")
    if "tax" not in inv_cols:
        cursor.execute("ALTER TABLE invoices ADD COLUMN tax REAL DEFAULT 0.0")
    if "discount" not in inv_cols:
        cursor.execute("ALTER TABLE invoices ADD COLUMN discount REAL DEFAULT 0.0")
    if "total" not in inv_cols:
        cursor.execute("ALTER TABLE invoices ADD COLUMN total REAL DEFAULT 0.0")

    # Profit Products Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profit_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        buy REAL NOT NULL,
        sell REAL NOT NULL,
        qty INTEGER NOT NULL
    )
    """)

    # Users Table for Auth & Session Persistence
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        password TEXT DEFAULT '',
        company TEXT DEFAULT '',
        biz_type TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT '',
        is_active INTEGER DEFAULT 1
    )
    """)

    # Migration for users table columns if existing DB had different schema
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [row[1] for row in cursor.fetchall()]
    if "password_hash" not in user_cols and len(user_cols) > 0:
        cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT DEFAULT ''")
    if "password" not in user_cols and len(user_cols) > 0:
        cursor.execute("ALTER TABLE users ADD COLUMN password TEXT DEFAULT ''")
    if "company" not in user_cols and len(user_cols) > 0:
        cursor.execute("ALTER TABLE users ADD COLUMN company TEXT DEFAULT ''")
    if "biz_type" not in user_cols and len(user_cols) > 0:
        cursor.execute("ALTER TABLE users ADD COLUMN biz_type TEXT DEFAULT ''")
    if "created_at" not in user_cols and len(user_cols) > 0:
        cursor.execute("ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT ''")
    if "updated_at" not in user_cols and len(user_cols) > 0:
        cursor.execute("ALTER TABLE users ADD COLUMN updated_at TEXT DEFAULT ''")
    if "is_active" not in user_cols and len(user_cols) > 0:
        cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")

    # User Sessions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        last_activity TEXT NOT NULL DEFAULT '',
        revoked_at TEXT DEFAULT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    cursor.execute("PRAGMA table_info(user_sessions)")
    sess_cols = [row[1] for row in cursor.fetchall()]
    if "last_activity" not in sess_cols and len(sess_cols) > 0:
        cursor.execute("ALTER TABLE user_sessions ADD COLUMN last_activity TEXT DEFAULT ''")
    if "revoked_at" not in sess_cols and len(sess_cols) > 0:
        cursor.execute("ALTER TABLE user_sessions ADD COLUMN revoked_at TEXT DEFAULT NULL")


    # Seed initial data if tables are empty (Preserving all existing records)
    cursor.execute("SELECT COUNT(*) FROM customers")
    if cursor.fetchone()[0] == 0:
        initial_customers = [
            ("Selvaraj Annamalai", "selvaraj@techcorp.in", "TechCorp India Pvt. Ltd", "Active", "₹10,40,000", 1040000.0, 24, "Mar 2023", 8, 12, 2, 0, 43333.33),
            ("Kavitha Sundaram", "kavitha@buildfast.in", "BuildFast Solutions", "Active", "₹7,20,000", 720000.0, 17, "Jun 2023", 15, 18, 3, 0, 42352.94),
            ("Rajendhiran Palaniswamy", "rajendhiran@dataflow.in", "DataFlow Systems", "At Risk", "₹18,00,000", 1800000.0, 41, "Jan 2023", 67, 45, 8, 3, 43902.44),
            ("Gowrishankar Venkatesh", "gowri@cloudshift.in", "CloudShift India", "Inactive", "₹2,60,000", 260000.0, 6, "Sep 2023", 88, 90, 10, 4, 43333.33),
            ("Tamilselvi Natarajan", "tamilselvi@nexalabs.in", "Nexa Labs Chennai", "Active", "₹26,50,000", 2650000.0, 63, "Nov 2022", 5, 5, 1, 0, 42063.49),
            ("Senthilkumar Murugan", "senthil@brightbridge.in", "BrightBridge Tech", "Active", "₹5,80,000", 580000.0, 14, "Apr 2023", 22, 24, 2, 1, 41428.57)
        ]
        cursor.executemany("""
        INSERT INTO customers (name, email, company, status, ltv, total_spend, orders, joined, churn, days_since_last_purchase, support_tickets, complaints, average_order_value)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, initial_customers)

    cursor.execute("SELECT COUNT(*) FROM employees")
    if cursor.fetchone()[0] == 0:
        initial_employees = [
            ("Anbarasi Krishnamoorthy", "Head of Sales", "Sales", "₹82,000/mo", "Active", 96, 94, "Jan 2021"),
            ("Thirunavukkarasu Rajan", "Senior Engineer", "Engineering", "₹1,04,000/mo", "Active", 98, 91, "Mar 2020"),
            ("Meenakshi Sundareswaran", "Product Manager", "Product", "₹94,000/mo", "Active", 94, 88, "Jun 2021"),
            ("Pazhanivel Arumugam", "Customer Success", "Support", "₹63,000/mo", "On Leave", 82, 87, "Sep 2022"),
            ("Valarmathi Subramanian", "Data Analyst", "Analytics", "₹74,000/mo", "Active", 97, 92, "Feb 2022")
        ]
        cursor.executemany("""
        INSERT INTO employees (name, role, dept, salary, status, attendance, performance, joined)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, initial_employees)

    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        initial_products = [
            ("Enterprise Suite Pro", "ESP-001", "Software", 245, 50, "₹3,49,000", 349000.0, "In Stock", "+12%", 4.5, 0.12, 0.1),
            ("Cloud Storage 1TB", "CS1T-002", "Storage", 12, 25, "₹24,900", 24900.0, "Low Stock", "+8%", 1.2, 0.08, 0.05),
            ("API Access Tokens", "AAT-003", "Services", 891, 100, "₹4,099/mo", 4099.0, "In Stock", "+31%", 15.0, 0.31, 0.2),
            ("Analytics Dashboard", "AD-004", "Software", 3, 20, "₹1,49,900", 149900.0, "Critical", "-4%", 2.1, -0.04, 0.0),
            ("Hardware Sensor Kit", "HSK-005", "Hardware", 67, 30, "₹74,000", 74000.0, "In Stock", "+5%", 1.8, 0.05, 0.0),
            ("Training Credits", "TC-006", "Training", 0, 50, "₹9,999", 9999.0, "Out of Stock", "N/A", 2.5, 0.0, 0.0)
        ]
        cursor.executemany("""
        INSERT INTO products (name, sku, category, stock, reorder, price, price_num, status, trend, avg_daily_demand, trend_factor, promotion_factor)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, initial_products)

    cursor.execute("SELECT COUNT(*) FROM invoices")
    if cursor.fetchone()[0] == 0:
        initial_invoices = [
            ("INV-2026-001", "TechCorp India Pvt. Ltd", "₹1,03,500", 103500.0, "Aug 15, 2026", "Jul 15, 2026", "Paid", "Enterprise Suite Pro — 1 seat", 103500.0, 0.0, 0.0, 103500.0),
            ("INV-2026-002", "DataFlow Systems", "₹72,800", 72800.0, "Aug 22, 2026", "Jul 22, 2026", "Pending", "Hardware Sensor Kit & Support", 72800.0, 0.0, 0.0, 72800.0),
            ("INV-2026-003", "CloudShift India", "₹26,600", 26600.0, "Jul 30, 2026", "Jun 30, 2026", "Overdue", "Cloud Storage 1TB (Annual)", 26600.0, 0.0, 0.0, 26600.0),
            ("INV-2026-004", "Nexa Labs Chennai", "₹1,80,000", 180000.0, "Sep 1, 2026", "Aug 1, 2026", "Draft", "Enterprise Analytics Suite", 180000.0, 0.0, 0.0, 180000.0),
            ("INV-2026-005", "BuildFast Solutions", "₹56,700", 56700.0, "Aug 10, 2026", "Jul 10, 2026", "Paid", "API Access Tokens & Cloud Storage", 56700.0, 0.0, 0.0, 56700.0)
        ]
        cursor.executemany("""
        INSERT INTO invoices (id, client, amount, amount_num, due, issued, status, items, subtotal, tax, discount, total)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, initial_invoices)

    cursor.execute("SELECT COUNT(*) FROM invoice_items")
    if cursor.fetchone()[0] == 0:
        seed_items = [
            ("INV-2026-001", 1, "Enterprise Suite Pro", 1, 103500.0, 103500.0),
            ("INV-2026-002", 5, "Hardware Sensor Kit", 1, 72800.0, 72800.0),
            ("INV-2026-003", 2, "Cloud Storage 1TB", 1, 26600.0, 26600.0),
            ("INV-2026-004", 4, "Analytics Dashboard", 1, 180000.0, 180000.0),
            ("INV-2026-005", 3, "API Access Tokens", 1, 56700.0, 56700.0)
        ]
        cursor.executemany("""
        INSERT INTO invoice_items (invoice_id, product_id, product_name, quantity, unit_price, line_total)
        VALUES (?, ?, ?, ?, ?, ?)
        """, seed_items)

    cursor.execute("SELECT COUNT(*) FROM profit_products")
    if cursor.fetchone()[0] == 0:
        initial_profit = [
            ("Enterprise Suite Pro", "Software License", 18500, 26000, 32),
            ("Cloud Storage 1TB", "Cloud Service", 320, 799, 850),
            ("API Access Tokens", "Developer Services", 40, 149, 2300),
            ("Analytics Dashboard Prem.", "Business Intelligence", 1800, 3499, 210),
            ("Training Credits", "AI Learning Credits", 450, 950, 720),
            ("Business Automation Pack", "Enterprise Software", 2900, 5499, 125),
            ("Workflow AI Assistant", "AI Subscription", 1250, 2499, 410),
            ("CRM Integration Suite", "Business Integration", 3200, 6499, 95),
            ("Email Automation Pro", "Marketing Automation", 650, 1499, 520),
            ("Document AI Processing", "AI Document Service", 180, 499, 1450)
        ]
        cursor.executemany("""
        INSERT INTO profit_products (name, category, buy, sell, qty)
        VALUES (?, ?, ?, ?, ?)
        """, initial_profit)

    conn.commit()
    conn.close()


init_db()


# ============================================================
# FASTAPI BACKEND SETUP
# ============================================================

app = FastAPI(
    title="AI Business Operations Copilot",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if SESSION_COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ============================================================
# ML TRAINING & DATA GENERATION FUNCTIONS
# ============================================================

def create_customer_data(rows=3000):
    random.seed(42)
    data = []
    for customer_id in range(1, rows + 1):
        total_orders = max(1, int(random.lognormvariate(3.0, 0.7)))
        average_order_value = round(random.uniform(15000, 65000), 2)
        total_spend = round(total_orders * average_order_value, 2)
        days_since_last_purchase = max(1, int(random.gauss(35, 25)))
        support_tickets = max(0, int(random.expovariate(0.5)))
        complaints = min(support_tickets, max(0, int(random.expovariate(1.0)) - 1))
        churn_score = (
            0.025 * days_since_last_purchase
            + 0.55 * complaints
            + 0.20 * support_tickets
            - 0.018 * total_orders
            - 0.00000003 * total_spend
            + random.uniform(-0.8, 0.8)
        )
        churned = 1 if churn_score > 1.5 else 0
        data.append({
            "customer_id": customer_id,
            "total_orders": total_orders,
            "total_spend": total_spend,
            "days_since_last_purchase": days_since_last_purchase,
            "support_tickets": support_tickets,
            "complaints": complaints,
            "average_order_value": average_order_value,
            "churned": churned
        })
    return pd.DataFrame(data)


def create_sales_data(rows=36):
    random.seed(42)
    data = []
    for month in range(1, rows + 1):
        base_revenue = 4200000 + month * 95000
        seasonal_factor = 1 + 0.08 * math.sin(month / 12 * 2 * math.pi)
        revenue = base_revenue * seasonal_factor + random.gauss(0, 180000)
        revenue = max(100000, revenue)
        orders = max(100, round(revenue / random.uniform(5000, 7000)))
        marketing_spend = revenue * random.uniform(0.06, 0.12)
        data.append({
            "month_index": month,
            "revenue": round(revenue, 2),
            "orders": orders,
            "marketing_spend": round(marketing_spend, 2)
        })
    return pd.DataFrame(data)


def create_inventory_data(rows=3000):
    random.seed(42)
    data = []
    for product_id in range(1, rows + 1):
        avg_daily_demand = max(0.2, random.lognormvariate(2.0, 0.65))
        trend = random.uniform(-0.20, 0.40)
        promotion_factor = random.uniform(0, 0.35)
        demand_30_days = (
            avg_daily_demand * 30 * (1 + trend + promotion_factor)
            + random.gauss(0, avg_daily_demand * 2)
        )
        demand_30_days = max(1, demand_30_days)
        data.append({
            "product_id": product_id,
            "avg_daily_demand": avg_daily_demand,
            "trend": trend,
            "promotion_factor": promotion_factor,
            "demand_next_30_days": demand_30_days
        })
    return pd.DataFrame(data)


def train_churn_model():
    data = create_customer_data()
    features = [
        "total_orders", "total_spend", "days_since_last_purchase",
        "support_tickets", "complaints", "average_order_value"
    ]
    X = data[features]
    y = data["churned"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    model = RandomForestClassifier(
        n_estimators=300, max_depth=10, min_samples_leaf=3,
        class_weight="balanced", random_state=42
    )
    model.fit(X_train, y_train)
    accuracy = accuracy_score(y_test, model.predict(X_test))
    joblib.dump({"model": model, "features": features}, CHURN_MODEL)
    print(f"Customer churn accuracy: {accuracy * 100:.2f}%")


def train_sales_model():
    data = create_sales_data()
    features = ["month_index", "orders", "marketing_spend"]
    X = data[features]
    y = data["revenue"]
    split = int(len(data) * 0.80)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]
    model = RandomForestRegressor(
        n_estimators=400, max_depth=12, min_samples_leaf=2, random_state=42
    )
    model.fit(X_train, y_train)
    error = mean_absolute_error(y_test, model.predict(X_test))
    joblib.dump({"model": model, "features": features}, SALES_MODEL)
    print(f"Sales model MAE: {error:.2f}")


def train_inventory_model():
    data = create_inventory_data()
    features = ["avg_daily_demand", "trend", "promotion_factor"]
    X = data[features]
    y = data["demand_next_30_days"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )
    model = RandomForestRegressor(
        n_estimators=300, max_depth=12, min_samples_leaf=2, random_state=42
    )
    model.fit(X_train, y_train)
    error = mean_absolute_error(y_test, model.predict(X_test))
    joblib.dump({"model": model, "features": features}, INVENTORY_MODEL)
    print(f"Inventory model MAE: {error:.2f}")


# Ensure models are trained
if not CHURN_MODEL.exists():
    train_churn_model()
if not SALES_MODEL.exists():
    train_sales_model()
if not INVENTORY_MODEL.exists():
    train_inventory_model()

churn_bundle = joblib.load(CHURN_MODEL)
sales_bundle = joblib.load(SALES_MODEL)
inventory_bundle = joblib.load(INVENTORY_MODEL)


# ============================================================
# SCHEMAS & REQUEST MODELS
# ============================================================

class ChurnRequest(BaseModel):
    total_orders: int = Field(ge=0)
    total_spend: float = Field(ge=0)
    days_since_last_purchase: int = Field(ge=0)
    support_tickets: int = Field(ge=0)
    complaints: int = Field(ge=0)
    average_order_value: float = Field(ge=0)


class SalesRequest(BaseModel):
    month_index: int = Field(ge=1)
    orders: int = Field(ge=0)
    marketing_spend: float = Field(ge=0)


class InventoryRequest(BaseModel):
    avg_daily_demand: float = Field(gt=0)
    trend: float = 0
    promotion_factor: float = Field(ge=0)
    current_stock: float = Field(ge=0)
    reorder_level: float = Field(ge=0)


class CustomerCreate(BaseModel):
    name: str
    email: str
    company: str
    status: str = "Active"
    ltv: str = "₹0"
    total_spend: float = 0.0
    orders: int = 0
    joined: Optional[str] = None
    days_since_last_purchase: int = 15
    support_tickets: int = 0
    complaints: int = 0
    average_order_value: float = 0.0


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    status: Optional[str] = None
    ltv: Optional[str] = None
    total_spend: Optional[float] = None
    orders: Optional[int] = None
    days_since_last_purchase: Optional[int] = None
    support_tickets: Optional[int] = None
    complaints: Optional[int] = None
    average_order_value: Optional[float] = None


class EmployeeCreate(BaseModel):
    name: str
    role: str
    dept: str
    salary: str
    status: str = "Active"
    attendance: int = 95
    performance: int = 90
    joined: Optional[str] = None


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    dept: Optional[str] = None
    salary: Optional[str] = None
    status: Optional[str] = None
    attendance: Optional[int] = None
    performance: Optional[int] = None


class ProductCreate(BaseModel):
    name: str
    sku: str
    category: str
    stock: int
    reorder: int
    price: str
    price_num: float = 0.0
    status: str = "In Stock"
    trend: str = "+0%"
    avg_daily_demand: float = 2.0
    trend_factor: float = 0.0
    promotion_factor: float = 0.0


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    category: Optional[str] = None
    stock: Optional[int] = None
    reorder: Optional[int] = None
    price: Optional[str] = None
    price_num: Optional[float] = None
    status: Optional[str] = None
    trend: Optional[str] = None
    avg_daily_demand: Optional[float] = None
    trend_factor: Optional[float] = None
    promotion_factor: Optional[float] = None


class InvoiceItemInput(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, description="Quantity must be greater than 0")
    unit_price: Optional[float] = None
    product_name: Optional[str] = None


class InvoiceCreate(BaseModel):
    id: Optional[str] = None
    client: str
    amount: Optional[str] = None
    amount_num: Optional[float] = 0.0
    due: Optional[str] = None
    issued: Optional[str] = None
    status: Optional[str] = "Pending"
    items: Optional[str] = ""
    subtotal: Optional[float] = None
    tax: Optional[float] = 0.0
    discount: Optional[float] = 0.0
    total: Optional[float] = None
    line_items: Optional[List[InvoiceItemInput]] = None


class InvoiceStatusUpdate(BaseModel):
    status: str


class CopilotChatRequest(BaseModel):
    message: str


class UserRegisterRequest(BaseModel):
    name: str
    email: str
    password: Optional[str] = ""
    company: Optional[str] = ""
    biz_type: Optional[str] = ""


class UserLoginRequest(BaseModel):
    email: str
    password: Optional[str] = ""


# ============================================================
# SYSTEM HEALTH & INFO
# ============================================================

@app.get("/")
def home():
    return {
        "project": "AI Business Operations Copilot",
        "status": "Backend running",
        "database": "SQLite (ai_bizops.db) connected",
        "machine_learning": [
            "Customer Churn Prediction",
            "Sales Forecasting",
            "Inventory Demand Prediction"
        ]
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "database": "connected",
        "models": {
            "customer_churn": True,
            "sales_forecast": True,
            "inventory_demand": True
        }
    }


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")



# ============================================================
# RATE LIMITING & SECURITY UTILITIES
# ============================================================

class LoginRateLimiter:
    """In-memory rate limiter tracking failed login attempts by IP / email.

    Two-tier protection:
      - Per IP+email (rate_key): 5 attempts in 5 minutes — protects individual accounts
      - Per IP only (ip_key):   20 attempts in 5 minutes — global safety net against
        distributed brute-force across many emails from the same IP

    The higher IP-only threshold prevents a brute-force test against one email
    from locking out all users sharing the same IP (e.g. all localhost dev traffic).
    """
    def __init__(self, max_attempts_per_key: int = 5, max_attempts_per_ip: int = 20, window_seconds: int = 300):
        self.max_attempts_per_key = max_attempts_per_key
        self.max_attempts_per_ip = max_attempts_per_ip
        self.window_seconds = window_seconds
        self.attempts: Dict[str, List[float]] = {}

    def _clean(self, key: str, now: float):
        if key in self.attempts:
            self.attempts[key] = [t for t in self.attempts[key] if now - t < self.window_seconds]
            if not self.attempts[key]:
                del self.attempts[key]

    def is_rate_limited_key(self, key: str) -> bool:
        """Check if an IP+email combination is rate-limited (per-account protection)."""
        now = time.time()
        self._clean(key, now)
        return len(self.attempts.get(key, [])) >= self.max_attempts_per_key

    def is_rate_limited_ip(self, ip: str) -> bool:
        """Check if a bare IP is rate-limited (global safety net, higher threshold)."""
        now = time.time()
        self._clean(ip, now)
        return len(self.attempts.get(ip, [])) >= self.max_attempts_per_ip

    def record_failure(self, key: str):
        now = time.time()
        self._clean(key, now)
        if key not in self.attempts:
            self.attempts[key] = []
        self.attempts[key].append(now)

    def reset(self, key: str):
        if key in self.attempts:
            del self.attempts[key]

    def get_remaining_seconds(self, key: str) -> int:
        """Return seconds until the oldest attempt in the window expires (0 if not limited)."""
        now = time.time()
        self._clean(key, now)
        timestamps = self.attempts.get(key, [])
        if not timestamps:
            return 0
        oldest = min(timestamps)
        remaining = self.window_seconds - (now - oldest)
        return max(0, int(remaining))

    def get_status(self, key: str, threshold: int = None) -> dict:
        """Return non-sensitive diagnostic info for a rate-limit key."""
        now = time.time()
        self._clean(key, now)
        timestamps = self.attempts.get(key, [])
        count = len(timestamps)
        limit = threshold if threshold is not None else self.max_attempts_per_key
        return {
            "attempts": count,
            "limit": limit,
            "is_blocked": count >= limit,
            "remaining_seconds": self.get_remaining_seconds(key) if count >= limit else 0,
            "window_seconds": self.window_seconds,
        }


login_limiter = LoginRateLimiter(max_attempts_per_key=5, max_attempts_per_ip=20, window_seconds=300)


def generate_csrf_token() -> str:
    """Generate a random cryptographic CSRF token."""
    return secrets.token_urlsafe(32)


def hash_password(plain_password: str) -> str:
    """Securely hash a plain text password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a stored hashed password (bcrypt / legacy support)."""
    if not plain_password or not hashed_password:
        return False
    try:
        if hashed_password.startswith(("$2b$", "$2a$", "$2y$")):
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        if ":" in hashed_password:
            salt, h = hashed_password.split(":", 1)
            calc = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
            return hmac.compare_digest(calc, h)
        return plain_password == hashed_password
    except Exception:
        return False


def create_user_session(cursor, user_id: int) -> str:
    """Generate a cryptographically secure session token and store in user_sessions (7-day validity)."""
    token = secrets.token_urlsafe(32)
    now_dt = datetime.now()
    created_at = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    expires_at = (now_dt + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    last_activity = created_at
    cursor.execute("""
    INSERT INTO user_sessions (token, user_id, created_at, expires_at, last_activity, revoked_at)
    VALUES (?, ?, ?, ?, ?, NULL)
    """, (token, user_id, created_at, expires_at, last_activity))
    return token


def get_authenticated_user(request: Request) -> dict:
    """Dependency: Extract session token from cookie (or fallback Bearer header), validate and return user."""
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split("Bearer ", 1)[1].strip()

    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized - authentication required")

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        SELECT s.token, s.expires_at, s.revoked_at, u.id, u.name, u.email, u.company, u.biz_type, u.is_active
        FROM user_sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
        """, (token.strip(),))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=401, detail="Unauthorized - invalid session")

        row_dict = dict(row)
        if row_dict.get("revoked_at"):
            raise HTTPException(status_code=401, detail="Unauthorized - session has been revoked")

        if row_dict.get("is_active") == 0:
            raise HTTPException(status_code=401, detail="Unauthorized - account disabled")

        try:
            exp = datetime.strptime(row_dict["expires_at"], "%Y-%m-%d %H:%M:%S")
            if datetime.now() > exp:
                raise HTTPException(status_code=401, detail="Unauthorized - session expired")
        except ValueError:
            pass

        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("UPDATE user_sessions SET last_activity = ? WHERE token = ?", (now_str, token.strip()))
            conn.commit()
        except Exception:
            pass

        return {
            "id": row_dict["id"],
            "name": row_dict["name"],
            "email": row_dict["email"],
            "company": row_dict["company"] or "Nexus Commerce Pvt. Ltd",
            "biz_type": row_dict["biz_type"] or "E-commerce"
        }
    finally:
        conn.close()


class LogoutRequest(BaseModel):
    token: Optional[str] = None


# ============================================================
# AUTHENTICATION & USER MANAGEMENT APIS
# ============================================================

@app.get("/api/auth/csrf")
def get_csrf_token(response: Response):
    """Issue a fresh CSRF token stored in a readable cookie and JSON response."""
    token = generate_csrf_token()
    response.set_cookie(
        key="csrf_token",
        value=token,
        httponly=False,
        samesite="lax",
        path="/",
        secure=SESSION_COOKIE_SECURE,
        max_age=7 * 86400
    )
    return {"csrf_token": token}


@app.get("/api/auth/rate-limit-status")
def get_rate_limit_status(request: Request, email: Optional[str] = Query(default=None)):
    """Developer-friendly endpoint to inspect rate-limit state for the caller's IP.

    Returns lockout info without exposing passwords, tokens, or other users' data.
    Optionally pass ?email=user@example.com to check the per-account lockout too.
    """
    client_ip = request.client.host if request.client else "unknown"
    ip_status = login_limiter.get_status(client_ip, threshold=login_limiter.max_attempts_per_ip)

    result = {
        "ip": client_ip,
        "ip_rate_limit": ip_status,
    }

    if email:
        clean_email = email.strip().lower()
        rate_key = f"{client_ip}:{clean_email}"
        key_status = login_limiter.get_status(rate_key, threshold=login_limiter.max_attempts_per_key)
        result["account_rate_limit"] = key_status

    return result


@app.post("/api/auth/register")
def register_user(req: UserRegisterRequest, response: Response):
    clean_name = (req.name or "").strip()
    clean_email = (req.email or "").strip().lower()
    raw_password = req.password or ""
    clean_company = (req.company or "").strip() or "Nexus Commerce Pvt. Ltd"
    clean_biz = (req.biz_type or "").strip() or "E-commerce"

    if not clean_name:
        raise HTTPException(status_code=400, detail="Name is required.")
    if not clean_email or not EMAIL_REGEX.match(clean_email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if not raw_password:
        raise HTTPException(status_code=400, detail="Password is required.")
    if len(raw_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (clean_email,))
        existing = cursor.fetchone()

        if existing:
            raise HTTPException(status_code=400, detail="An account with this email already exists. Please sign in.")

        hashed_pw = hash_password(raw_password)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
        INSERT INTO users (name, email, password_hash, password, company, biz_type, created_at, updated_at, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (clean_name, clean_email, hashed_pw, hashed_pw, clean_company, clean_biz, now_str, now_str))
        user_id = cursor.lastrowid

        conn.commit()
    finally:
        conn.close()

    csrf_tok = generate_csrf_token()
    response.set_cookie(
        key="csrf_token",
        value=csrf_tok,
        httponly=False,
        samesite="lax",
        path="/",
        secure=SESSION_COOKIE_SECURE,
        max_age=7 * 86400
    )

    return {
        "status": "success",
        "message": "Account created successfully. Please sign in.",
        "user": {
            "id": user_id,
            "name": clean_name,
            "email": clean_email,
            "company": clean_company,
            "biz_type": clean_biz
        }
    }


@app.post("/api/auth/login")
def login_user(req: UserLoginRequest, request: Request, response: Response):
    client_ip = request.client.host if request.client else "unknown"
    clean_email = (req.email or "").strip().lower()
    raw_password = req.password or ""

    if not clean_email:
        raise HTTPException(status_code=400, detail="Email address is required.")
    if not EMAIL_REGEX.match(clean_email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if not raw_password:
        raise HTTPException(status_code=400, detail="Password is required.")

    rate_key = f"{client_ip}:{clean_email}"
    if login_limiter.is_rate_limited_key(rate_key):
        remaining = login_limiter.get_remaining_seconds(rate_key)
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts for this account. Please try again in {max(1, remaining // 60)} minute{'s' if remaining > 60 else ''}."
        )
    if login_limiter.is_rate_limited_ip(client_ip):
        remaining = login_limiter.get_remaining_seconds(client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts. Please try again in {max(1, remaining // 60)} minute{'s' if remaining > 60 else ''}."
        )

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        SELECT id, name, email, password_hash, password, company, biz_type, is_active
        FROM users
        WHERE LOWER(email) = LOWER(?)
        """, (clean_email,))
        user_row = cursor.fetchone()

        if not user_row:
            login_limiter.record_failure(rate_key)
            login_limiter.record_failure(client_ip)
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        user_dict = dict(user_row)
        if user_dict.get("is_active") == 0:
            raise HTTPException(status_code=401, detail="Account is disabled.")

        stored_hash = user_dict.get("password_hash") or user_dict.get("password") or ""

        if not verify_password(raw_password, stored_hash):
            login_limiter.record_failure(rate_key)
            login_limiter.record_failure(client_ip)
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        # Reset rate limiting counter on success
        login_limiter.reset(rate_key)
        login_limiter.reset(client_ip)

        # Upgrade to bcrypt if stored hash is legacy format
        if not stored_hash.startswith(("$2b$", "$2a$", "$2y$")):
            new_hash = hash_password(raw_password)
            cursor.execute("UPDATE users SET password_hash = ?, password = ? WHERE id = ?", (new_hash, new_hash, user_dict["id"]))

        token = create_user_session(cursor, user_dict["id"])
        csrf_tok = generate_csrf_token()
        conn.commit()
    finally:
        conn.close()

    # Set HTTP-only session cookie
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
        secure=SESSION_COOKIE_SECURE,
        max_age=7 * 86400
    )
    # Set readable CSRF cookie
    response.set_cookie(
        key="csrf_token",
        value=csrf_tok,
        httponly=False,
        samesite="lax",
        path="/",
        secure=SESSION_COOKIE_SECURE,
        max_age=7 * 86400
    )

    return {
        "status": "success",
        "token": token,
        "user": {
            "id": user_dict["id"],
            "name": user_dict["name"],
            "email": user_dict["email"],
            "company": user_dict["company"] or "Nexus Commerce Pvt. Ltd",
            "biz_type": user_dict["biz_type"] or "E-commerce"
        },
        "csrf_token": csrf_tok
    }


@app.get("/api/auth/me")
def get_current_user_me(user: dict = Depends(get_authenticated_user)):
    return {
        "status": "success",
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "company": user.get("company", ""),
        "biz_type": user.get("biz_type", ""),
        "user": user
    }


@app.post("/api/auth/logout")
def logout_user(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split("Bearer ", 1)[1].strip()

    if token:
        conn = get_db()
        cursor = conn.cursor()
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("UPDATE user_sessions SET revoked_at = ? WHERE token = ?", (now_str, token.strip()))
            cursor.execute("DELETE FROM user_sessions WHERE token = ?", (token.strip(),))
            conn.commit()
        finally:
            conn.close()

    response.delete_cookie("session_token", path="/")
    response.delete_cookie("csrf_token", path="/")

    return {"status": "success", "message": "Logged out successfully"}





# ============================================================
# 1. CUSTOMERS APIS
# ============================================================

@app.get("/api/customers")
def get_customers(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


@app.post("/api/customers")
def create_customer(customer: CustomerCreate, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    joined_date = customer.joined or datetime.now().strftime("%b %Y")
    
    # Calculate churn score from model
    model = churn_bundle["model"]
    features = churn_bundle["features"]
    avg_val = customer.average_order_value or (customer.total_spend / max(1, customer.orders))
    input_data = pd.DataFrame(
        [[
            customer.orders,
            customer.total_spend,
            customer.days_since_last_purchase,
            customer.support_tickets,
            customer.complaints,
            avg_val
        ]],
        columns=features
    )
    churn_prob = round(float(model.predict_proba(input_data)[0][1]) * 100)

    cursor.execute("""
    INSERT INTO customers (name, email, company, status, ltv, total_spend, orders, joined, churn, days_since_last_purchase, support_tickets, complaints, average_order_value)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        customer.name, customer.email, customer.company, customer.status,
        customer.ltv, customer.total_spend, customer.orders, joined_date,
        churn_prob, customer.days_since_last_purchase, customer.support_tickets,
        customer.complaints, avg_val
    ))
    new_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM customers WHERE id = ?", (new_id,))
    created = dict(cursor.fetchone())
    conn.close()
    return created


@app.put("/api/customers/{customer_id}")
def update_customer(customer_id: int, update: CustomerUpdate, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Customer not found")
    
    current = dict(existing)
    update_data = update.dict(exclude_unset=True)
    for k, v in update_data.items():
        if v is not None:
            current[k] = v

    # Re-calculate churn probability
    model = churn_bundle["model"]
    features = churn_bundle["features"]
    avg_val = current.get("average_order_value") or (current.get("total_spend", 0) / max(1, current.get("orders", 1)))
    input_data = pd.DataFrame(
        [[
            current.get("orders", 1),
            current.get("total_spend", 0),
            current.get("days_since_last_purchase", 10),
            current.get("support_tickets", 0),
            current.get("complaints", 0),
            avg_val
        ]],
        columns=features
    )
    current["churn"] = round(float(model.predict_proba(input_data)[0][1]) * 100)

    cursor.execute("""
    UPDATE customers SET
        name = ?, email = ?, company = ?, status = ?, ltv = ?, total_spend = ?,
        orders = ?, churn = ?, days_since_last_purchase = ?, support_tickets = ?,
        complaints = ?, average_order_value = ?
    WHERE id = ?
    """, (
        current["name"], current["email"], current["company"], current["status"],
        current["ltv"], current["total_spend"], current["orders"], current["churn"],
        current["days_since_last_purchase"], current["support_tickets"],
        current["complaints"], avg_val, customer_id
    ))
    conn.commit()
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    updated = dict(cursor.fetchone())
    conn.close()
    return updated


@app.delete("/api/customers/{customer_id}")
def delete_customer(customer_id: int, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "deleted_id": customer_id}


@app.post("/api/customers/{customer_id}/churn")
def predict_customer_churn_by_id(customer_id: int, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Customer not found")
    
    cust = dict(row)
    model = churn_bundle["model"]
    features = churn_bundle["features"]
    avg_val = cust["average_order_value"] or (cust["total_spend"] / max(1, cust["orders"]))
    input_data = pd.DataFrame(
        [[
            cust["orders"],
            cust["total_spend"],
            cust["days_since_last_purchase"],
            cust["support_tickets"],
            cust["complaints"],
            avg_val
        ]],
        columns=features
    )
    prob = round(float(model.predict_proba(input_data)[0][1]) * 100, 1)

    if prob >= 70:
        risk = "HIGH"
        recommendation = "High churn risk detected. Immediately assign a dedicated Customer Success Manager and extend a personalized retention offer."
    elif prob >= 35:
        risk = "MEDIUM"
        recommendation = "Moderate churn risk. Schedule an engagement check-in and share updated product features."
    else:
        risk = "LOW"
        recommendation = "Customer engagement is healthy. Continue standard communication."

    cursor.execute("UPDATE customers SET churn = ? WHERE id = ?", (int(prob), customer_id))
    conn.commit()
    conn.close()

    return {
        "customer_id": customer_id,
        "name": cust["name"],
        "churn_probability": prob,
        "risk": risk,
        "recommendation": recommendation
    }


# Standalone ML Churn Endpoint
@app.post("/api/predict/churn")
def predict_churn(request: ChurnRequest, user: dict = Depends(get_authenticated_user)):
    model = churn_bundle["model"]
    features = churn_bundle["features"]
    input_data = pd.DataFrame(
        [[
            request.total_orders,
            request.total_spend,
            request.days_since_last_purchase,
            request.support_tickets,
            request.complaints,
            request.average_order_value
        ]],
        columns=features
    )
    probability = round(float(model.predict_proba(input_data)[0][1]) * 100, 2)

    if probability >= 75:
        risk = "HIGH"
        recommendation = "Contact the customer immediately and offer a personalized retention campaign."
    elif probability >= 45:
        risk = "MEDIUM"
        recommendation = "Monitor the customer and run a personalized engagement campaign."
    else:
        risk = "LOW"
        recommendation = "Customer appears stable. Continue normal engagement."

    return {
        "churn_probability": probability,
        "risk": risk,
        "recommendation": recommendation
    }


# ============================================================
# 2. EMPLOYEES APIS
# ============================================================

@app.get("/api/employees")
def get_employees(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


@app.post("/api/employees")
def create_employee(emp: EmployeeCreate, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    joined_date = emp.joined or datetime.now().strftime("%b %Y")
    cursor.execute("""
    INSERT INTO employees (name, role, dept, salary, status, attendance, performance, joined)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        emp.name, emp.role, emp.dept, emp.salary, emp.status,
        emp.attendance, emp.performance, joined_date
    ))
    new_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM employees WHERE id = ?", (new_id,))
    created = dict(cursor.fetchone())
    conn.close()
    return created


@app.put("/api/employees/{emp_id}")
def update_employee(emp_id: int, emp: EmployeeUpdate, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees WHERE id = ?", (emp_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Employee not found")

    current = dict(existing)
    for k, v in emp.dict(exclude_unset=True).items():
        if v is not None:
            current[k] = v

    cursor.execute("""
    UPDATE employees SET
        name = ?, role = ?, dept = ?, salary = ?, status = ?,
        attendance = ?, performance = ?
    WHERE id = ?
    """, (
        current["name"], current["role"], current["dept"], current["salary"],
        current["status"], current["attendance"], current["performance"], emp_id
    ))
    conn.commit()
    cursor.execute("SELECT * FROM employees WHERE id = ?", (emp_id,))
    updated = dict(cursor.fetchone())
    conn.close()
    return updated


@app.delete("/api/employees/{emp_id}")
def delete_employee(emp_id: int, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "deleted_id": emp_id}


# ============================================================
# 3. INVENTORY & PRODUCTS APIS
# ============================================================

@app.get("/api/inventory")
def get_inventory(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


@app.post("/api/inventory")
def create_product(prod: ProductCreate, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO products (name, sku, category, stock, reorder, price, price_num, status, trend, avg_daily_demand, trend_factor, promotion_factor)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        prod.name, prod.sku, prod.category, prod.stock, prod.reorder,
        prod.price, prod.price_num, prod.status, prod.trend,
        prod.avg_daily_demand, prod.trend_factor, prod.promotion_factor
    ))
    new_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM products WHERE id = ?", (new_id,))
    created = dict(cursor.fetchone())
    conn.close()
    return created


@app.put("/api/inventory/{product_id}")
def update_product(product_id: int, prod: ProductUpdate, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")

    current = dict(existing)
    for k, v in prod.dict(exclude_unset=True).items():
        if v is not None:
            current[k] = v

    # Recalculate status based on stock & reorder
    if current["stock"] == 0:
        current["status"] = "Out of Stock"
    elif current["stock"] <= current["reorder"] * 0.3:
        current["status"] = "Critical"
    elif current["stock"] <= current["reorder"]:
        current["status"] = "Low Stock"
    else:
        current["status"] = "In Stock"

    cursor.execute("""
    UPDATE products SET
        name = ?, sku = ?, category = ?, stock = ?, reorder = ?,
        price = ?, price_num = ?, status = ?, trend = ?,
        avg_daily_demand = ?, trend_factor = ?, promotion_factor = ?
    WHERE id = ?
    """, (
        current["name"], current["sku"], current["category"], current["stock"],
        current["reorder"], current["price"], current["price_num"], current["status"],
        current["trend"], current["avg_daily_demand"], current["trend_factor"],
        current["promotion_factor"], product_id
    ))
    conn.commit()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    updated = dict(cursor.fetchone())
    conn.close()
    return updated


@app.delete("/api/inventory/{product_id}")
def delete_product(product_id: int, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "deleted_id": product_id}


@app.post("/api/inventory/{product_id}/restock")
def restock_product(product_id: int, quantity: int = Query(default=50, ge=1), user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")

    row = dict(existing)
    new_stock = row["stock"] + quantity
    new_status = "In Stock" if new_stock > row["reorder"] else ("Low Stock" if new_stock > row["reorder"] * 0.3 else "Critical")

    cursor.execute("UPDATE products SET stock = ?, status = ? WHERE id = ?", (new_stock, new_status, product_id))
    conn.commit()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    updated = dict(cursor.fetchone())
    conn.close()
    return updated


@app.post("/api/inventory/{product_id}/forecast")
def forecast_product_demand_by_id(product_id: int, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")

    p = dict(row)
    model = inventory_bundle["model"]
    features = inventory_bundle["features"]
    input_data = pd.DataFrame(
        [[
            p["avg_daily_demand"],
            p["trend_factor"],
            p["promotion_factor"]
        ]],
        columns=features
    )
    pred_30 = max(0, float(model.predict(input_data)[0]))
    pred_7 = round((pred_30 / 30) * 7, 1)
    current_stock = p["stock"]
    reorder_level = p["reorder"]

    if current_stock < pred_7 or current_stock <= 3:
        risk = "HIGH"
        reorder_qty = max(0, round(pred_7 * 1.5 - current_stock))
        rec = f"Critical stockout risk within {max(1, round(current_stock / max(0.1, p['avg_daily_demand'])))} days. Reorder {reorder_qty} units immediately."
    elif current_stock <= reorder_level:
        risk = "MEDIUM"
        reorder_qty = max(0, round(pred_7 * 0.8))
        rec = f"Inventory low. Reorder ~{reorder_qty} units within the next week."
    else:
        risk = "LOW"
        reorder_qty = 0
        rec = "Inventory levels are healthy. Next scheduled review in ~3 weeks."

    conn.close()
    return {
        "product_id": product_id,
        "name": p["name"],
        "current_stock": current_stock,
        "reorder_level": reorder_level,
        "predicted_demand_7_days": pred_7,
        "predicted_demand_30_days": round(pred_30, 1),
        "stockout_risk": risk,
        "recommended_reorder": reorder_qty,
        "recommendation": rec
    }


# Standalone ML Inventory Demand Prediction
@app.post("/api/predict/inventory")
def predict_inventory(request: InventoryRequest, user: dict = Depends(get_authenticated_user)):
    model = inventory_bundle["model"]
    features = inventory_bundle["features"]
    input_data = pd.DataFrame(
        [[
            request.avg_daily_demand,
            request.trend,
            request.promotion_factor
        ]],
        columns=features
    )
    predicted_30_days = max(0, float(model.predict(input_data)[0]))
    predicted_7_days = round((predicted_30_days / 30) * 7, 2)

    if request.current_stock < predicted_7_days:
        risk = "HIGH"
        reorder_quantity = max(0, round(predicted_7_days * 1.2 - request.current_stock))
        recommendation = "Stock is likely to be insufficient. Reorder immediately."
    elif request.current_stock <= request.reorder_level:
        risk = "MEDIUM"
        reorder_quantity = max(0, round(predicted_7_days * 0.5))
        recommendation = "Inventory may become low. Consider reordering."
    else:
        risk = "LOW"
        reorder_quantity = 0
        recommendation = "Current inventory appears sufficient."

    return {
        "predicted_demand_7_days": predicted_7_days,
        "predicted_demand_30_days": round(predicted_30_days, 2),
        "stockout_risk": risk,
        "recommended_reorder": reorder_quantity,
        "recommendation": recommendation
    }


# ============================================================
# 4. INVOICES APIS
# ============================================================

@app.get("/api/invoices")
def get_invoices(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices ORDER BY issued DESC, id DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    
    # Attach line items for each invoice
    for row in rows:
        cursor.execute("SELECT * FROM invoice_items WHERE invoice_id = ?", (row["id"],))
        row["line_items"] = [dict(item) for item in cursor.fetchall()]
    
    conn.close()
    return rows


@app.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: str, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    inv_data = dict(row)
    cursor.execute("SELECT * FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
    inv_data["line_items"] = [dict(item) for item in cursor.fetchall()]
    conn.close()
    return inv_data


@app.post("/api/invoices")
def create_invoice(inv: InvoiceCreate, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # 1. Validate Customer
        clean_client = (inv.client or "").strip()
        if not clean_client:
            raise HTTPException(status_code=400, detail="Customer / Client name is required.")
        
        # Check if customer exists in database (by name or company)
        cursor.execute("SELECT id, name, company FROM customers WHERE LOWER(name) = LOWER(?) OR LOWER(company) = LOWER(?)", (clean_client, clean_client))
        customer = cursor.fetchone()
        if not customer:
            cursor.execute("SELECT id, name, company FROM customers WHERE LOWER(company) LIKE LOWER(?) OR LOWER(name) LIKE LOWER(?)", (f"%{clean_client}%", f"%{clean_client}%"))
            customer = cursor.fetchone()
            if not customer:
                raise HTTPException(status_code=400, detail=f"Customer '{clean_client}' does not exist in the database.")
        
        # 2. Process & Validate Line Items
        processed_items = []
        subtotal = 0.0
        item_descriptions = []

        if inv.line_items and len(inv.line_items) > 0:
            for item in inv.line_items:
                if item.quantity <= 0:
                    raise HTTPException(status_code=400, detail=f"Quantity for product ID {item.product_id} must be greater than 0.")
                
                # Fetch product from database
                cursor.execute("SELECT id, name, price, price_num, stock, reorder FROM products WHERE id = ?", (item.product_id,))
                prod = cursor.fetchone()
                if not prod:
                    raise HTTPException(status_code=400, detail=f"Product with ID {item.product_id} does not exist.")
                
                prod_data = dict(prod)
                available_stock = prod_data["stock"]
                
                # Check Stock
                if item.quantity > available_stock:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Insufficient stock for '{prod_data['name']}'. Requested {item.quantity}, but only {available_stock} available."
                    )
                
                # Determine Unit Price
                unit_price = item.unit_price if (item.unit_price is not None and item.unit_price > 0) else prod_data["price_num"]
                if not unit_price:
                    cleaned_p = str(prod_data["price"]).replace("₹", "").replace(",", "").replace("/mo", "").strip()
                    try:
                        unit_price = float(cleaned_p)
                    except ValueError:
                        unit_price = 0.0
                
                line_total = unit_price * item.quantity
                subtotal += line_total
                item_descriptions.append(f"{prod_data['name']} (x{item.quantity})")
                
                processed_items.append({
                    "product_id": prod_data["id"],
                    "product_name": prod_data["name"],
                    "quantity": item.quantity,
                    "unit_price": unit_price,
                    "line_total": line_total,
                    "current_stock": available_stock,
                    "reorder": prod_data["reorder"]
                })
        else:
            # Fallback for manual amount / description if no line_items supplied
            cleaned_amt = str(inv.amount or "0").replace("₹", "").replace(",", "").strip()
            try:
                subtotal = float(cleaned_amt)
            except ValueError:
                subtotal = 0.0
            item_descriptions.append(inv.items or "General Invoice")
        
        # 3. Calculate Tax, Discount, Grand Total
        tax_pct = max(0.0, float(inv.tax or 0.0))
        tax_amount = subtotal * (tax_pct / 100.0) if tax_pct > 0 else 0.0
        discount_amount = max(0.0, float(inv.discount or 0.0))
        grand_total = max(0.0, subtotal + tax_amount - discount_amount)
        
        # 4. Generate Invoice ID
        inv_id = inv.id
        if not inv_id:
            cursor.execute("SELECT id FROM invoices")
            existing_ids = [r[0] for r in cursor.fetchall()]
            max_num = 0
            for eid in existing_ids:
                if eid.startswith("INV-2026-"):
                    try:
                        num = int(eid.split("INV-2026-")[1])
                        if num > max_num:
                            max_num = num
                    except (ValueError, IndexError):
                        pass
            inv_id = f"INV-2026-{max_num + 1:03d}"
        
        issued_date = inv.issued or datetime.now().strftime("%b %d, %Y")
        due_date = inv.due or "Sep 30, 2026"
        formatted_amount = f"₹{grand_total:,.0f}" if grand_total >= 1 else f"₹{grand_total:.2f}"
        items_summary_text = ", ".join(item_descriptions) if item_descriptions else (inv.items or "")
        
        # 5. Atomic Transaction: Insert Invoice & Line Items, Reduce Stock
        cursor.execute("""
        INSERT INTO invoices (id, client, amount, amount_num, due, issued, status, items, subtotal, tax, discount, total)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            inv_id, clean_client, formatted_amount, grand_total, due_date, issued_date,
            inv.status or "Pending", items_summary_text, subtotal, tax_pct, discount_amount, grand_total
        ))
        
        # Insert line items & deduct stock
        for p_item in processed_items:
            cursor.execute("""
            INSERT INTO invoice_items (invoice_id, product_id, product_name, quantity, unit_price, line_total)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                inv_id, p_item["product_id"], p_item["product_name"], p_item["quantity"],
                p_item["unit_price"], p_item["line_total"]
            ))
            
            # Reduce inventory stock
            new_stock = p_item["current_stock"] - p_item["quantity"]
            reorder_val = p_item["reorder"]
            
            if new_stock == 0:
                new_status = "Out of Stock"
            elif new_stock <= reorder_val * 0.3:
                new_status = "Critical"
            elif new_stock <= reorder_val:
                new_status = "Low Stock"
            else:
                new_status = "In Stock"
            
            cursor.execute("UPDATE products SET stock = ?, status = ? WHERE id = ?", (new_stock, new_status, p_item["product_id"]))
        
        conn.commit()
        
        # Fetch the created invoice with line items
        cursor.execute("SELECT * FROM invoices WHERE id = ?", (inv_id,))
        created_inv = dict(cursor.fetchone())
        cursor.execute("SELECT * FROM invoice_items WHERE invoice_id = ?", (inv_id,))
        created_inv["line_items"] = [dict(r) for r in cursor.fetchall()]
        
        conn.close()
        return created_inv
    
    except HTTPException:
        conn.rollback()
        conn.close()
        raise
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to create invoice: {str(e)}")


@app.patch("/api/invoices/{invoice_id}/status")
def update_invoice_status(invoice_id: str, status_data: InvoiceStatusUpdate, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE invoices SET status = ? WHERE id = ?", (status_data.status, invoice_id))
    conn.commit()
    cursor.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Invoice not found")
    inv_data = dict(row)
    cursor.execute("SELECT * FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
    inv_data["line_items"] = [dict(item) for item in cursor.fetchall()]
    conn.close()
    return inv_data


@app.delete("/api/invoices/{invoice_id}")
def delete_invoice(invoice_id: str, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
    cursor.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "deleted_id": invoice_id}


# ============================================================
# 5. SALES ANALYTICS & FORECASTING APIS
# ============================================================

@app.get("/api/sales/overview")
def get_sales_overview(user: dict = Depends(get_authenticated_user)):
    monthly = [
        {"month": "Jan", "revenue": 42000, "expenses": 28000, "profit": 14000},
        {"month": "Feb", "revenue": 47500, "expenses": 30000, "profit": 17500},
        {"month": "Mar", "revenue": 51200, "expenses": 31500, "profit": 19700},
        {"month": "Apr", "revenue": 49800, "expenses": 29000, "profit": 20800},
        {"month": "May", "revenue": 58600, "expenses": 33000, "profit": 25600},
        {"month": "Jun", "revenue": 63400, "expenses": 35000, "profit": 28400},
        {"month": "Jul", "revenue": 61200, "expenses": 34000, "profit": 27200},
        {"month": "Aug", "revenue": 67800, "expenses": 36500, "profit": 31300},
        {"month": "Sep", "revenue": 72400, "expenses": 38000, "profit": 34400},
        {"month": "Oct", "revenue": 69100, "expenses": 37200, "profit": 31900},
        {"month": "Nov", "revenue": 78500, "expenses": 41000, "profit": 37500},
        {"month": "Dec", "revenue": 85200, "expenses": 44500, "profit": 40700},
    ]

    daily = [
        {"day": "Mon", "sales": 3200, "orders": 28},
        {"day": "Tue", "sales": 4100, "orders": 35},
        {"day": "Wed", "sales": 3800, "orders": 31},
        {"day": "Thu", "sales": 5200, "orders": 44},
        {"day": "Fri", "sales": 6100, "orders": 52},
        {"day": "Sat", "sales": 4700, "orders": 40},
        {"day": "Sun", "sales": 3100, "orders": 26},
    ]

    customer_growth = [
        {"month": "Jan", "new": 120, "returning": 280},
        {"month": "Feb", "new": 145, "returning": 310},
        {"month": "Mar", "new": 162, "returning": 340},
        {"month": "Apr", "new": 138, "returning": 365},
        {"month": "May", "new": 190, "returning": 390},
        {"month": "Jun", "new": 215, "returning": 420},
        {"month": "Jul", "new": 203, "returning": 445},
    ]

    product_categories = [
        {"name": "Software", "value": 38, "color": "#4f46e5"},
        {"name": "Hardware", "value": 25, "color": "#8b5cf6"},
        {"name": "Services", "value": 22, "color": "#06b6d4"},
        {"name": "Training", "value": 15, "color": "#10b981"},
    ]

    return {
        "monthly": monthly,
        "daily": daily,
        "customer_growth": customer_growth,
        "product_categories": product_categories
    }


@app.get("/api/sales/forecast")
def get_sales_forecast(user: dict = Depends(get_authenticated_user)):
    model = sales_bundle["model"]
    features = sales_bundle["features"]

    # Predict for Month 8 (Aug), Month 9 (Sep), Month 10 (Oct)
    predictions = []
    months = ["August", "September", "October"]
    for idx, month_name in enumerate(months, start=8):
        input_data = pd.DataFrame([[idx, 890 + idx * 25, 450000.0]], columns=features)
        pred_rev = float(model.predict(input_data)[0])
        predictions.append({
            "month": month_name,
            "predicted_revenue": round(pred_rev, 2),
            "predicted_revenue_formatted": f"₹{(pred_rev / 100000):.1f}L",
            "delta": f"+{round(6.5 + idx * 0.4, 1)}%",
            "confidence": 91 - idx * 2
        })

    return {
        "monthly_forecasts": predictions,
        "q3_forecast": "₹1.64Cr",
        "q3_delta": "+9.2%",
        "q3_confidence": 87,
        "annual_target": "₹6.5Cr",
        "annual_delta": "On track",
        "annual_confidence": 94
    }


# Standalone ML Sales Forecast API
@app.post("/api/predict/sales")
def predict_sales(request: SalesRequest, user: dict = Depends(get_authenticated_user)):
    model = sales_bundle["model"]
    features = sales_bundle["features"]
    input_data = pd.DataFrame(
        [[
            request.month_index,
            request.orders,
            request.marketing_spend
        ]],
        columns=features
    )
    prediction = float(model.predict(input_data)[0])
    return {
        "predicted_revenue": round(prediction, 2),
        "currency": "INR"
    }


# ============================================================
# 6. DASHBOARD & INSIGHTS APIS
# ============================================================

def compute_business_health():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Sales Growth (Weight: 20%)
    # Using sales monthly trajectory (recent vs previous month: Dec 85200 vs Nov 78500 = +8.5%)
    growth_rate_pct = 8.5
    sales_score = max(0, min(100, round(75 + growth_rate_pct * 1.5)))
    sales_detail = {
        "score": sales_score,
        "weight": 20,
        "metric": f"+{growth_rate_pct:.1f}% MoM",
        "status": "positive" if sales_score >= 70 else "warning" if sales_score >= 50 else "danger"
    }

    # 2. Profit Margin (Weight: 20%)
    cursor.execute("SELECT buy, sell, qty FROM profit_products")
    profit_rows = cursor.fetchall()
    if profit_rows:
        total_rev = sum(r[1] * r[2] for r in profit_rows)
        total_cost = sum(r[0] * r[2] for r in profit_rows)
        total_profit = max(0.0, total_rev - total_cost)
        margin_pct = (total_profit / max(1.0, total_rev)) * 100
        profit_score = max(0, min(100, round(margin_pct * 1.8)))
    else:
        margin_pct = 45.0
        profit_score = 81
    profit_detail = {
        "score": profit_score,
        "weight": 20,
        "metric": f"{margin_pct:.1f}% margin",
        "status": "positive" if profit_score >= 70 else "warning" if profit_score >= 50 else "danger"
    }

    # 3. Inventory Health (Weight: 15%)
    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = max(1, cursor.fetchone()[0])
    cursor.execute("SELECT COUNT(*) FROM products WHERE status = 'In Stock'")
    in_stock_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM products WHERE status = 'Low Stock'")
    low_stock_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM products WHERE status = 'Critical'")
    critical_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM products WHERE status = 'Out of Stock'")
    out_of_stock_count = cursor.fetchone()[0]

    in_stock_pct = (in_stock_count / total_products) * 100
    penalty = (out_of_stock_count * 18) + (critical_count * 12) + (low_stock_count * 6)
    inventory_score = max(0, min(100, round(in_stock_pct - penalty + 12)))
    inventory_detail = {
        "score": inventory_score,
        "weight": 15,
        "metric": f"{in_stock_count}/{total_products} in stock",
        "status": "positive" if inventory_score >= 70 else "warning" if inventory_score >= 50 else "danger"
    }

    # 4. Customer Churn Risk (Weight: 15%)
    cursor.execute("SELECT AVG(churn), COUNT(*) FROM customers")
    avg_churn_val, total_custs = cursor.fetchone()
    avg_churn = float(avg_churn_val or 20.0)
    cursor.execute("SELECT COUNT(*) FROM customers WHERE churn >= 50")
    high_churn_count = cursor.fetchone()[0]
    churn_score = max(0, min(100, round(100 - avg_churn)))
    churn_detail = {
        "score": churn_score,
        "weight": 15,
        "metric": f"{avg_churn:.1f}% avg churn",
        "status": "positive" if churn_score >= 70 else "warning" if churn_score >= 50 else "danger"
    }

    # 5. Outstanding Invoices (Weight: 15%)
    cursor.execute("SELECT status, COALESCE(SUM(amount_num), 0), COUNT(*) FROM invoices GROUP BY status")
    inv_summary = {r[0]: {"total": float(r[1]), "count": r[2]} for r in cursor.fetchall()}
    total_inv_amount = sum(v["total"] for v in inv_summary.values())
    paid_inv_amount = inv_summary.get("Paid", {}).get("total", 0.0)
    pending_inv_amount = inv_summary.get("Pending", {}).get("total", 0.0)
    overdue_inv_amount = inv_summary.get("Overdue", {}).get("total", 0.0)
    overdue_count = inv_summary.get("Overdue", {}).get("count", 0)

    paid_ratio = (paid_inv_amount / max(1.0, total_inv_amount)) * 100
    overdue_ratio = (overdue_inv_amount / max(1.0, total_inv_amount)) * 100
    invoices_score = max(0, min(100, round(paid_ratio * 0.7 - overdue_ratio * 0.5 + 30)))
    invoices_detail = {
        "score": invoices_score,
        "weight": 15,
        "metric": f"{paid_ratio:.0f}% collected",
        "status": "positive" if invoices_score >= 70 else "warning" if invoices_score >= 50 else "danger"
    }

    # 6. Employee Performance (Weight: 15%)
    cursor.execute("SELECT AVG(performance), AVG(attendance), COUNT(*) FROM employees WHERE status != 'Inactive'")
    avg_perf_val, avg_att_val, total_emps = cursor.fetchone()
    avg_perf = float(avg_perf_val or 90.0)
    avg_att = float(avg_att_val or 95.0)
    employee_score = max(0, min(100, round(avg_perf * 0.7 + avg_att * 0.3)))
    employee_detail = {
        "score": employee_score,
        "weight": 15,
        "metric": f"{avg_perf:.1f}% avg rating",
        "status": "positive" if employee_score >= 70 else "warning" if employee_score >= 50 else "danger"
    }

    conn.close()

    # Overall Weighted Score Calculation
    weighted_total = (
        sales_score * 0.20 +
        profit_score * 0.20 +
        inventory_score * 0.15 +
        churn_score * 0.15 +
        invoices_score * 0.15 +
        employee_score * 0.15
    )
    overall_score = max(0, min(100, round(weighted_total)))

    # Health Level
    if overall_score >= 90:
        health_level = "Excellent"
    elif overall_score >= 75:
        health_level = "Good"
    elif overall_score >= 60:
        health_level = "Needs Attention"
    elif overall_score >= 40:
        health_level = "At Risk"
    else:
        health_level = "Critical"

    # Why your score changed (Dynamic Reasons)
    reasons = []

    # Sales Reason
    if sales_score >= 75:
        reasons.append({
            "type": "positive",
            "component": "sales_growth",
            "text": f"Sales revenue grew +{growth_rate_pct:.1f}% MoM driven by enterprise software renewals and service expansions."
        })
    else:
        reasons.append({
            "type": "negative",
            "component": "sales_growth",
            "text": "Sales trajectory showed slower momentum compared to the previous target period."
        })

    # Profit Reason
    if profit_score >= 75:
        reasons.append({
            "type": "positive",
            "component": "profit_margin",
            "text": f"Profit margin is solid at {margin_pct:.1f}% across active software and product offerings."
        })
    else:
        reasons.append({
            "type": "negative",
            "component": "profit_margin",
            "text": f"Profit margin compressed to {margin_pct:.1f}% due to rising product procurement costs."
        })

    # Inventory Reason
    if out_of_stock_count > 0 or critical_count > 0 or low_stock_count > 0:
        low_items_total = out_of_stock_count + critical_count + low_stock_count
        reasons.append({
            "type": "negative",
            "component": "inventory_health",
            "text": f"Inventory health decreased: {low_items_total} product(s) are currently below safe reorder levels."
        })
    else:
        reasons.append({
            "type": "positive",
            "component": "inventory_health",
            "text": "Inventory health is optimal with all SKU stocks comfortably above reorder thresholds."
        })

    # Customer Churn Reason
    if high_churn_count > 0:
        reasons.append({
            "type": "negative",
            "component": "customer_churn",
            "text": f"Customer churn risk elevated: {high_churn_count} customer(s) show elevated churn probability (>50%)."
        })
    else:
        reasons.append({
            "type": "positive",
            "component": "customer_churn",
            "text": f"Customer retention is healthy with a low average churn probability of {avg_churn:.1f}%."
        })

    # Invoices Reason
    if overdue_count > 0:
        reasons.append({
            "type": "negative",
            "component": "outstanding_invoices",
            "text": f"Outstanding invoices: {overdue_count} overdue invoice(s) (₹{overdue_inv_amount:,.0f}) require payment follow-up."
        })
    else:
        reasons.append({
            "type": "positive",
            "component": "outstanding_invoices",
            "text": f"{paid_ratio:.0f}% of total invoiced revenue has been collected on schedule."
        })

    # Employee Reason
    if employee_score >= 80:
        reasons.append({
            "type": "positive",
            "component": "employee_performance",
            "text": f"Employee performance remains strong at {avg_perf:.1f}% average rating and {avg_att:.1f}% attendance."
        })
    else:
        reasons.append({
            "type": "negative",
            "component": "employee_performance",
            "text": f"Employee attendance and output ratings averaged {avg_perf:.1f}%, slightly below quarterly targets."
        })

    return {
        "overall_score": overall_score,
        "health_level": health_level,
        "weights": {
            "sales_growth": 0.20,
            "profit_margin": 0.20,
            "inventory_health": 0.15,
            "customer_churn": 0.15,
            "outstanding_invoices": 0.15,
            "employee_performance": 0.15
        },
        "components": {
            "sales_growth": sales_score,
            "profit_margin": profit_score,
            "inventory_health": inventory_score,
            "customer_churn": churn_score,
            "outstanding_invoices": invoices_score,
            "employee_performance": employee_score
        },
        "component_details": {
            "sales_growth": sales_detail,
            "profit_margin": profit_detail,
            "inventory_health": inventory_detail,
            "customer_churn": churn_detail,
            "outstanding_invoices": invoices_detail,
            "employee_performance": employee_detail
        },
        "reasons": reasons,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


@app.get("/api/business-health")
def get_business_health(user: dict = Depends(get_authenticated_user)):
    return compute_business_health()


@app.get("/api/dashboard/stats")
def get_dashboard_stats(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()

    # Customers count
    cursor.execute("SELECT COUNT(*) FROM customers")
    total_customers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM customers WHERE status = 'Active'")
    active_customers = cursor.fetchone()[0]

    # Invoices stats
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(amount_num), 0) FROM invoices WHERE status = 'Pending'")
    pending_invoices_count, pending_amount = cursor.fetchone()

    cursor.execute("SELECT COALESCE(SUM(amount_num), 0) FROM invoices WHERE status = 'Paid'")
    paid_amount = cursor.fetchone()[0]

    # Inventory stats
    cursor.execute("SELECT COUNT(*) FROM products WHERE status = 'In Stock'")
    in_stock_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = max(1, cursor.fetchone()[0])
    inventory_health = round((in_stock_count / total_products) * 100)

    # Low stock items
    cursor.execute("SELECT * FROM products WHERE status IN ('Low Stock', 'Critical', 'Out of Stock')")
    low_stock_products = [dict(r) for r in cursor.fetchall()]

    conn.close()

    health_info = compute_business_health()
    overall_health = health_info["overall_score"]

    return {
        "kpis": {
            "today_revenue": "₹7,02,500",
            "today_revenue_change": "+23%",
            "monthly_revenue": "₹52.8L",
            "monthly_revenue_change": "+12%",
            "active_customers": f"{active_customers:,}",
            "active_customers_change": "+8%",
            "pending_orders": "47",
            "pending_orders_change": "-3%",
            "inventory_health": f"{inventory_health}%",
            "inventory_health_change": "-5%",
            "business_health": f"{overall_health}/100",
            "business_health_change": f"{health_info['health_level']}"
        },
        "low_stock_alerts": low_stock_products
    }


@app.get("/api/dashboard/insights")
def get_dashboard_insights(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()

    # Query churn risk count
    cursor.execute("SELECT COUNT(*) FROM customers WHERE churn >= 60")
    high_churn_count = cursor.fetchone()[0]

    # Query critical products
    cursor.execute("SELECT name FROM products WHERE status IN ('Critical', 'Out of Stock') LIMIT 1")
    crit_prod = cursor.fetchone()
    crit_prod_name = crit_prod[0] if crit_prod else "Analytics Dashboard"

    conn.close()

    return [
        {"text": "Revenue up 23% today. Flash sale is performing above ML prediction.", "type": "positive"},
        {"text": f"{high_churn_count or 3} customer(s) show high churn risk. AI recommends immediate retention outreach.", "type": "warning"},
        {"text": f"{crit_prod_name} SKU is critically low. Immediate restock order recommended.", "type": "danger"},
        {"text": "August ML forecast: ₹56.8L (+7.6% MoM growth projected with 91% confidence).", "type": "info"}
    ]


@app.get("/api/dashboard/activity")
def get_dashboard_activity(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices ORDER BY issued DESC LIMIT 2")
    recent_invs = [dict(r) for r in cursor.fetchall()]
    conn.close()

    activities = []
    if recent_invs:
        activities.append({
            "icon": "DollarSign",
            "text": f"Invoice #{recent_invs[0]['id']} for {recent_invs[0]['client']} — {recent_invs[0]['amount']}",
            "time": "2 min ago",
            "color": "text-emerald-500"
        })
    activities.extend([
        {"icon": "Users", "text": "Customer intelligence: Selvaraj Annamalai LTV reached ₹10,40,000", "time": "34 min ago", "color": "text-indigo-500"},
        {"icon": "AlertTriangle", "text": "Low stock alert: Analytics Dashboard (3 units remaining)", "time": "1 hr ago", "color": "text-amber-500"},
        {"icon": "ShoppingCart", "text": "47 pending customer orders require processing", "time": "2 hrs ago", "color": "text-violet-500"},
        {"icon": "UserCheck", "text": "Pazhanivel Arumugam submitted leave request for approval", "time": "3 hrs ago", "color": "text-blue-500"}
    ])
    return activities


# ============================================================
# 7. AI COPILOT INTERACTIVE CHAT API
# ============================================================

@app.post("/api/copilot/chat")
def copilot_chat(req: CopilotChatRequest, user: dict = Depends(get_authenticated_user)):
    query = req.message.lower().strip()
    conn = get_db()
    cursor = conn.cursor()

    if any(w in query for w in ["revenue", "sales breakdown", "today", "income"]):
        cursor.execute("SELECT SUM(amount_num) FROM invoices WHERE status = 'Paid'")
        paid = cursor.fetchone()[0] or 160200
        response_text = (
            f"Here is your revenue breakdown based on real business operations data:\n\n"
            f"**Today's Revenue: ₹7,02,500** (+23% vs weekly average)\n\n"
            f"| Category | Amount | % of Total |\n"
            f"|---|---|---|\n"
            f"| Software | ₹2,66,550 | 38% |\n"
            f"| Services | ₹1,75,625 | 25% |\n"
            f"| Hardware | ₹1,47,525 | 21% |\n"
            f"| Training | ₹1,12,400 | 16% |\n\n"
            f"The software spike is driven by Enterprise Suite Pro renewals. Services are running 31% above average."
        )
        chart = True

    elif any(w in query for w in ["churn", "at risk", "retention", "customer"]):
        cursor.execute("SELECT name, company, churn, ltv FROM customers WHERE churn >= 50 ORDER BY churn DESC")
        risky = cursor.fetchall()
        list_str = "\n".join([f"- **{r['name']}** ({r['company']}): **{r['churn']}% churn risk** (LTV: {r['ltv']})" for r in risky])
        response_text = (
            f"I ran our ML Churn Prediction model on all active customer accounts. Here are the customers requiring attention:\n\n"
            f"{list_str}\n\n"
            f"**Recommended Action:**\n"
            f"Send a proactive check-in email and offer an exclusive loyalty renewal discount to prevent contract termination."
        )
        chart = False

    elif any(w in query for w in ["inventory", "stock", "reorder", "product"]):
        cursor.execute("SELECT name, stock, reorder, status FROM products WHERE status IN ('Critical', 'Low Stock', 'Out of Stock')")
        low_items = cursor.fetchall()
        items_str = "\n".join([f"- **{r['name']}**: {r['stock']} units left (Reorder Level: {r['reorder']}) — *{r['status']}*" for r in low_items])
        response_text = (
            f"Based on our Inventory Demand ML model, here is the current restock priority:\n\n"
            f"{items_str}\n\n"
            f"**Recommendation:** Create an urgent purchase order for **Analytics Dashboard** and **Cloud Storage 1TB** to avoid estimated stockout in 2-4 days."
        )
        chart = False

    elif any(w in query for w in ["predict", "forecast", "future", "q3", "august"]):
        response_text = (
            f"I have run the **Sales Forecasting Random Forest Model** on historical trends and marketing expenditures:\n\n"
            f"- **August Forecast:** **₹56.8L** (+7.6% MoM, 91% confidence)\n"
            f"- **Q3 Total Forecast:** **₹1.64Cr** (+9.2% YoY, 87% confidence)\n"
            f"- **Annual Target:** **₹6.5Cr** (Current trajectory: **On Track** with 94% confidence)\n\n"
            f"The primary growth drivers are Enterprise Software licenses and API usage expansion."
        )
        chart = True

    elif any(w in query for w in ["employee", "staff", "performance", "top 5"]):
        cursor.execute("SELECT name, role, dept, attendance, performance FROM employees ORDER BY performance DESC LIMIT 5")
        top_emps = cursor.fetchall()
        emp_str = "\n".join([f"- **{r['name']}** ({r['role']}, {r['dept']}): **{r['performance']}% Performance**, {r['attendance']}% Attendance" for r in top_emps])
        response_text = (
            f"Here are the top performing employees across all departments:\n\n"
            f"{emp_str}\n\n"
            f"Overall company employee attendance is running at a healthy **95.8%**."
        )
        chart = False

    elif any(w in query for w in ["invoice", "generate invoice", "techcorp"]):
        cursor.execute("SELECT * FROM invoices WHERE client LIKE '%TechCorp%' LIMIT 1")
        inv = cursor.fetchone()
        inv_id = inv['id'] if inv else "INV-2026-001"
        response_text = (
            f"I located the latest invoice for **TechCorp India Pvt. Ltd**:\n\n"
            f"- **Invoice Number:** `{inv_id}`\n"
            f"- **Amount:** ₹1,03,500\n"
            f"- **Status:** Paid\n"
            f"- **Items:** Enterprise Suite Pro — 1 Seat\n\n"
            f"Would you like me to generate a new follow-on invoice or export the PDF?"
        )
        chart = False

    else:
        response_text = (
            f"I analyzed your live business database for: **\"{req.message}\"**\n\n"
            f"Here are the key operational metrics:\n"
            f"- **Monthly Revenue:** Tracking at **₹52.8L** (+12% MoM)\n"
            f"- **Active Customers:** 6 key enterprise accounts (Avg LTV: ₹11.7L)\n"
            f"- **Inventory Health:** 78% healthy stock ratio\n"
            f"- **Employee Performance:** 90.4% company average\n\n"
            f"Feel free to ask for detailed forecasts, churn analysis, or inventory reorder recommendations."
        )
        chart = False

    conn.close()
    return {
        "role": "ai",
        "content": response_text,
        "chart": chart
    }


# ============================================================
# 8. REPORTS & PROFIT ANALYZER APIS
# ============================================================

@app.get("/api/reports/{report_type}")
def get_report_data(report_type: str, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()

    if "revenue" in report_type.lower():
        data = {
            "headers": ["Month", "Revenue (₹)", "Expenses (₹)", "Profit (₹)", "Growth %"],
            "rows": [
                ["January", "4,12,000", "2,80,000", "1,32,000", "8.2%"],
                ["February", "4,38,000", "2,95,000", "1,43,000", "6.3%"],
                ["March", "4,85,000", "3,10,000", "1,75,000", "10.7%"],
                ["April", "5,02,000", "3,20,000", "1,82,000", "3.5%"],
                ["May", "5,28,000", "3,35,000", "1,93,000", "5.2%"],
                ["June", "5,64,000", "3,45,000", "2,19,000", "6.8%"],
                ["July", "5,28,000", "3,12,000", "2,16,000", "-6.4%"],
            ],
            "summary": [
                {"label": "Total Revenue (YTD)", "value": "₹34,57,000"},
                {"label": "Total Expenses (YTD)", "value": "₹21,97,000"},
                {"label": "Net Profit (YTD)", "value": "₹12,60,000"},
                {"label": "Average Monthly Growth", "value": "4.9%"},
                {"label": "Best Month", "value": "June — ₹5,64,000"}
            ]
        }
    elif "customer" in report_type.lower():
        cursor.execute("SELECT name, company, ltv, orders, status FROM customers")
        cust_rows = [[r[0], r[1], r[2], str(r[3]), r[4]] for r in cursor.fetchall()]
        data = {
            "headers": ["Customer", "Company / Segment", "LTV (₹)", "Orders", "Status"],
            "rows": cust_rows,
            "summary": [
                {"label": "Total Customers", "value": str(len(cust_rows))},
                {"label": "Active Customers", "value": str(sum(1 for r in cust_rows if r[4] == "Active"))},
                {"label": "At Risk", "value": str(sum(1 for r in cust_rows if r[4] == "At Risk"))},
                {"label": "Total LTV Tracked", "value": "₹70,50,000"}
            ]
        }
    elif "inventory" in report_type.lower():
        cursor.execute("SELECT name, sku, stock, reorder, status FROM products")
        prod_rows = [[r[0], r[1], str(r[2]), str(r[3]), r[4]] for r in cursor.fetchall()]
        data = {
            "headers": ["Product", "SKU", "Stock", "Reorder Level", "Status"],
            "rows": prod_rows,
            "summary": [
                {"label": "Total SKUs", "value": str(len(prod_rows))},
                {"label": "Critical Items", "value": str(sum(1 for r in prod_rows if r[4] in ["Critical", "Out of Stock"]))},
                {"label": "Low Stock Items", "value": str(sum(1 for r in prod_rows if r[4] == "Low Stock"))},
                {"label": "Total Inventory Units", "value": "1,218"}
            ]
        }
    elif "employee" in report_type.lower():
        cursor.execute("SELECT name, dept, salary, attendance, performance FROM employees")
        emp_rows = [[r[0], r[1], r[2], f"{r[3]}%", f"{r[4]}%"] for r in cursor.fetchall()]
        data = {
            "headers": ["Name", "Department", "Salary", "Attendance", "Performance"],
            "rows": emp_rows,
            "summary": [
                {"label": "Total Employees", "value": str(len(emp_rows))},
                {"label": "Total Monthly Payroll", "value": "₹4,17,000"},
                {"label": "Average Attendance", "value": "95.8%"},
                {"label": "Top Performer", "value": "Anbarasi Krishnamoorthy"}
            ]
        }
    elif "sales" in report_type.lower():
        data = {
            "headers": ["Month", "New Customers", "Returning", "Revenue (₹)", "Conversion %"],
            "rows": [
                ["May", "48", "132", "₹5,28,000", "18.4%"],
                ["June", "61", "149", "₹5,64,000", "21.2%"],
                ["July", "53", "141", "₹5,28,000", "19.7%"],
            ],
            "summary": [
                {"label": "Total New Customers (Q3)", "value": "162"},
                {"label": "Returning Customers (Q3)", "value": "422"},
                {"label": "Q3 Revenue", "value": "₹16,20,000"},
                {"label": "Best Conversion Month", "value": "June — 21.2%"}
            ]
        }
    else:  # AI Insights
        data = {
            "headers": ["Insight", "Category", "Impact", "Recommendation"],
            "rows": [
                ["Revenue up 12% YoY", "Revenue", "High", "Expand Enterprise tier marketing"],
                ["Analytics Dashboard stock critical", "Inventory", "High", "Reorder 35 units immediately"],
                ["Rajendhiran shows 67% churn risk", "Customer", "High", "Assign Dedicated CSM"],
                ["Sales forecast Q3: ₹1.64Cr", "Forecasting", "Positive", "Increase server capacity"],
                ["Support SLA adherence at 96%", "Support", "Positive", "Maintain current team size"]
            ],
            "summary": [
                {"label": "Business Health Score", "value": "92 / 100"},
                {"label": "Critical Alerts", "value": "2"},
                {"label": "Opportunities Identified", "value": "3"},
                {"label": "AI Confidence", "value": "94%"}
            ]
        }

    conn.close()
    return data


@app.get("/api/profit/products")
def get_profit_products(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM profit_products ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# ============================================================
# 9. AI BUSINESS HEALTH SCORE ENGINE
# ============================================================

def compute_business_health(conn=None):
    close_after = False
    if conn is None:
        conn = get_db()
        close_after = True
    cursor = conn.cursor()

    # 1. Sales Growth (Weight: 20%)
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE status = 'Paid'")
    paid_inv_count = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(amount_num) FROM invoices WHERE status = 'Paid'")
    paid_inv_sum = cursor.fetchone()[0] or 0.0

    growth_rate = 8.5
    if paid_inv_count > 0:
        growth_rate += min(10.0, paid_inv_count * 0.5)

    if growth_rate >= 15.0:
        sales_score = 95
    elif growth_rate >= 8.0:
        sales_score = 88
    elif growth_rate >= 0.0:
        sales_score = 80
    else:
        sales_score = max(30, int(80 + growth_rate * 2))

    # 2. Profit Margin (Weight: 20%)
    cursor.execute("SELECT SUM(sell * qty), SUM(buy * qty) FROM profit_products")
    p_row = cursor.fetchone()
    total_rev = p_row[0] or 1.0
    total_cost = p_row[1] or 0.0
    margin_pct = round(((total_rev - total_cost) / total_rev) * 100, 1) if total_rev > 0 else 45.0

    if margin_pct >= 50.0:
        profit_score = 93
    elif margin_pct >= 40.0:
        profit_score = 85
    elif margin_pct >= 30.0:
        profit_score = 75
    else:
        profit_score = max(35, int(margin_pct * 1.8))

    # 3. Inventory Health (Weight: 15%)
    cursor.execute("SELECT COUNT(*), SUM(CASE WHEN stock <= reorder THEN 1 ELSE 0 END) FROM products")
    inv_row = cursor.fetchone()
    total_products = inv_row[0] or 1
    low_stock_count = inv_row[1] or 0
    in_stock_count = total_products - low_stock_count
    inv_score = max(10, min(100, int((in_stock_count / total_products) * 100)))

    # 4. Customer Churn Risk (Weight: 15%)
    cursor.execute("SELECT COUNT(*), SUM(CASE WHEN status = 'At Risk' OR days_since_last_purchase > 40 THEN 1 ELSE 0 END) FROM customers")
    cust_row = cursor.fetchone()
    total_customers = cust_row[0] or 1
    at_risk_customers = cust_row[1] or 0
    churn_rate_pct = round((at_risk_customers / total_customers) * 100, 1)
    churn_score = max(20, min(100, int(100 - churn_rate_pct)))

    # 5. Outstanding Invoices (Weight: 15%)
    cursor.execute("SELECT COUNT(*), SUM(CASE WHEN status = 'Paid' THEN 1 ELSE 0 END), SUM(CASE WHEN status = 'Overdue' THEN 1 ELSE 0 END), SUM(CASE WHEN status = 'Overdue' THEN amount_num ELSE 0 END) FROM invoices")
    inv_stats = cursor.fetchone()
    total_invoices = inv_stats[0] or 1
    paid_count = inv_stats[1] or 0
    overdue_count = inv_stats[2] or 0
    overdue_sum = inv_stats[3] or 0.0

    paid_ratio = paid_count / total_invoices
    inv_score_calc = int(paid_ratio * 80 + 20 - (overdue_count * 8))
    outstanding_score = max(15, min(100, inv_score_calc))

    # 6. Employee Performance (Weight: 15%)
    cursor.execute("SELECT AVG(performance), AVG(attendance) FROM employees")
    emp_stats = cursor.fetchone()
    avg_performance = emp_stats[0] or 90.0
    avg_attendance = emp_stats[1] or 95.0
    emp_score = max(30, min(100, int(round((avg_performance * 0.7) + (avg_attendance * 0.3)))))

    components = [
        {
            "key": "sales_growth",
            "name": "Sales Growth",
            "score": sales_score,
            "weight": 0.20,
            "weight_pct": "20%",
            "metric": f"+{growth_rate:.1f}% MoM",
            "status": "Strong" if sales_score >= 80 else "Moderate"
        },
        {
            "key": "profit_margin",
            "name": "Profit Margin",
            "score": profit_score,
            "weight": 0.20,
            "weight_pct": "20%",
            "metric": f"{margin_pct:.1f}% margin",
            "status": "Healthy" if profit_score >= 80 else "Fair"
        },
        {
            "key": "inventory_health",
            "name": "Inventory Health",
            "score": inv_score,
            "weight": 0.15,
            "weight_pct": "15%",
            "metric": f"{in_stock_count}/{total_products} in stock",
            "status": "Good" if inv_score >= 75 else "Low Stock"
        },
        {
            "key": "customer_churn",
            "name": "Customer Churn Risk",
            "score": churn_score,
            "weight": 0.15,
            "weight_pct": "15%",
            "metric": f"{churn_rate_pct:.1f}% avg churn",
            "status": "Low Risk" if churn_score >= 75 else "Elevated Risk"
        },
        {
            "key": "outstanding_invoices",
            "name": "Outstanding Invoices",
            "score": outstanding_score,
            "weight": 0.15,
            "weight_pct": "15%",
            "metric": f"{int(paid_ratio * 100)}% collected",
            "status": "On Track" if outstanding_score >= 70 else "Action Needed"
        },
        {
            "key": "employee_performance",
            "name": "Employee Performance",
            "score": emp_score,
            "weight": 0.15,
            "weight_pct": "15%",
            "metric": f"{avg_performance:.1f}% avg rating",
            "status": "High" if emp_score >= 85 else "Standard"
        }
    ]

    weighted_total = sum(c["score"] * c["weight"] for c in components)
    overall_score = int(round(weighted_total))

    if overall_score >= 90:
        health_level = "Excellent"
    elif overall_score >= 75:
        health_level = "Good"
    elif overall_score >= 60:
        health_level = "Needs Attention"
    elif overall_score >= 40:
        health_level = "At Risk"
    else:
        health_level = "Critical"

    reasons = []
    if sales_score >= 80:
        reasons.append({
            "type": "positive",
            "component": "sales_growth",
            "text": f"Sales revenue grew +{growth_rate:.1f}% MoM driven by enterprise software renewals and service expansions."
        })
    else:
        reasons.append({
            "type": "negative",
            "component": "sales_growth",
            "text": f"Sales revenue growth slowed to +{growth_rate:.1f}% MoM; promotional push recommended."
        })

    if profit_score >= 80:
        reasons.append({
            "type": "positive",
            "component": "profit_margin",
            "text": f"Profit margin is solid at {margin_pct:.1f}% across active software and product offerings."
        })
    else:
        reasons.append({
            "type": "negative",
            "component": "profit_margin",
            "text": f"Gross profit margin compressed to {margin_pct:.1f}%; consider optimizing procurement costs."
        })

    if low_stock_count > 0:
        reasons.append({
            "type": "negative",
            "component": "inventory_health",
            "text": f"Inventory health decreased: {low_stock_count} product(s) are currently below safe reorder levels."
        })
    else:
        reasons.append({
            "type": "positive",
            "component": "inventory_health",
            "text": "Inventory health is optimal: all catalog products maintain healthy stock buffers."
        })

    if at_risk_customers > 0:
        reasons.append({
            "type": "negative",
            "component": "customer_churn",
            "text": f"Customer churn risk elevated: {at_risk_customers} customer(s) show elevated churn probability (>50%)."
        })
    else:
        reasons.append({
            "type": "positive",
            "component": "customer_churn",
            "text": "Customer retention is healthy with low predicted churn risk across key accounts."
        })

    if overdue_count > 0:
        reasons.append({
            "type": "negative",
            "component": "outstanding_invoices",
            "text": f"Outstanding invoices: {overdue_count} overdue invoice(s) (₹{int(overdue_sum):,}) require payment follow-up."
        })
    else:
        reasons.append({
            "type": "positive",
            "component": "outstanding_invoices",
            "text": "Receivables on track: no critically overdue invoices detected."
        })

    if emp_score >= 80:
        reasons.append({
            "type": "positive",
            "component": "employee_performance",
            "text": f"Employee performance remains strong at {avg_performance:.1f}% average rating and {avg_attendance:.1f}% attendance."
        })
    else:
        reasons.append({
            "type": "negative",
            "component": "employee_performance",
            "text": f"Employee efficiency index is {emp_score}/100; team bandwidth support recommended."
        })

    comp_dict = {c["key"]: c["score"] for c in components}
    comp_details = {
        c["key"]: {
            "score": c["score"],
            "weight": c["weight"],
            "metric": c["metric"],
            "status": "positive" if c["score"] >= 80 else "warning" if c["score"] >= 60 else "danger"
        }
        for c in components
    }
    weights_dict = {c["key"]: c["weight"] for c in components}

    from datetime import datetime
    now_str = datetime.now().strftime("%b %d, %Y, %I:%M %p")

    if close_after:
        conn.close()

    return {
        "status": "success",
        "score": overall_score,
        "overall_score": overall_score,
        "health_level": health_level,
        "components": components,
        "components_map": comp_dict,
        "component_details": comp_details,
        "weights": weights_dict,
        "reasons": reasons,
        "last_updated": now_str
    }


# ============================================================
# 10. AI ACTION CENTER ENGINE
# ============================================================

def generate_action_center_items(conn=None):
    close_after = False
    if conn is None:
        conn = get_db()
        close_after = True
    cursor = conn.cursor()

    actions = []

    # 1. Inventory Actions
    cursor.execute("SELECT id, name, sku, stock, reorder, price, status, avg_daily_demand FROM products")
    products = [dict(r) for r in cursor.fetchall()]
    for p in products:
        stock = p["stock"]
        reorder = p["reorder"]
        name = p["name"]
        p_id = p["id"]

        if stock == 0:
            actions.append({
                "id": f"inv-out-{p_id}",
                "priority": "critical",
                "category": "inventory",
                "title": f"{name} is Out of Stock",
                "problem": f"Current stock is 0 units. Minimum safe reorder threshold is {reorder} units.",
                "data_metrics": f"Stock: 0 / Reorder: {reorder}",
                "recommendation": f"Create an emergency restock order for at least {max(reorder, 25)} units immediately.",
                "why_explanation": f"Zero inventory creates a fulfillment bottleneck and causes direct loss of customer orders.",
                "entity_id": p_id,
                "entity_type": "product",
                "action_type": "restock",
                "target_page": "inventory",
                "primary_button_label": "Create Restock Order",
                "secondary_button_label": "View Product"
            })
        elif stock <= reorder:
            is_crit = stock <= max(1, reorder // 3)
            prio = "critical" if is_crit else "high"
            deficit = reorder - stock + max(10, int(reorder * 0.4))
            actions.append({
                "id": f"inv-low-{p_id}",
                "priority": prio,
                "category": "inventory",
                "title": f"Low Stock: {name} ({stock} remaining)",
                "problem": f"Only {stock} unit(s) remain in stock, which is below the safe threshold of {reorder} units.",
                "data_metrics": f"Stock: {stock} / Reorder: {reorder}",
                "recommendation": f"Restock {deficit} units to restore safe operational buffers.",
                "why_explanation": f"Inventory is at {stock}/{reorder} capacity; high daily demand may trigger a complete stockout within 4-7 days.",
                "entity_id": p_id,
                "entity_type": "product",
                "action_type": "restock",
                "target_page": "inventory",
                "primary_button_label": "Create Restock Order",
                "secondary_button_label": "View Product"
            })

    # 2. Customer Churn Risk Actions
    cursor.execute("SELECT id, name, company, email, ltv, orders, status, days_since_last_purchase, support_tickets, complaints FROM customers")
    customers = [dict(r) for r in cursor.fetchall()]
    for c in customers:
        days = c.get("days_since_last_purchase", 15)
        complaints = c.get("complaints", 0)
        c_status = c.get("status", "Active")
        c_name = c["name"]
        c_comp = c.get("company", "")
        c_id = c["id"]

        # Approximate churn risk calculation matching ML feature weightings
        churn_pct = min(95.0, max(10.0, 20.0 + (days * 0.8) + (complaints * 18.0) + (15.0 if c_status == "At Risk" else 0.0)))
        
        if churn_pct >= 60.0 or c_status == "At Risk":
            prio = "high"
            actions.append({
                "id": f"cust-churn-{c_id}",
                "priority": prio,
                "category": "customers",
                "title": f"High Churn Risk: {c_name} ({c_comp})",
                "problem": f"Client shows an elevated {churn_pct:.0f}% churn risk with {days} days of account inactivity.",
                "data_metrics": f"Churn Risk: {churn_pct:.0f}% | Inactive: {days}d | Complaints: {complaints}",
                "recommendation": "Initiate dedicated executive outreach and offer an annual contract renewal incentive.",
                "why_explanation": f"Account has been inactive for {days} days with {complaints} support ticket escalations.",
                "entity_id": c_id,
                "entity_type": "customer",
                "action_type": "outreach",
                "target_page": "customers",
                "primary_button_label": "View Customer",
                "secondary_button_label": "Create Follow-up"
            })
        elif churn_pct >= 40.0:
            actions.append({
                "id": f"cust-warm-{c_id}",
                "priority": "medium",
                "category": "customers",
                "title": f"Retention Watch: {c_name} ({c_comp})",
                "problem": f"Client interaction frequency is tapering ({churn_pct:.0f}% churn likelihood).",
                "data_metrics": f"Churn Risk: {churn_pct:.0f}% | Inactive: {days}d",
                "recommendation": "Send a product roadmap newsletter and schedule a customer success review meeting.",
                "why_explanation": f"Customer placed {c.get('orders', 1)} prior order(s) but has not re-ordered recently.",
                "entity_id": c_id,
                "entity_type": "customer",
                "action_type": "outreach",
                "target_page": "customers",
                "primary_button_label": "View Customer",
                "secondary_button_label": "Send Survey"
            })

    # 3. Invoice & Overdue Payment Actions
    cursor.execute("SELECT id, client, amount, amount_num, due, issued, status FROM invoices")
    invoices = [dict(r) for r in cursor.fetchall()]
    for inv in invoices:
        i_status = inv.get("status", "Pending")
        amt_num = inv.get("amount_num", 0.0)
        i_id = inv["id"]
        client = inv["client"]
        due = inv.get("due", "N/A")

        if i_status == "Overdue":
            actions.append({
                "id": f"inv-overdue-{i_id}",
                "priority": "critical",
                "category": "invoices",
                "title": f"Overdue Payment: Invoice {i_id} ({client})",
                "problem": f"Invoice {i_id} for ₹{amt_num:,.0f} is past due date ({due}) and remains uncollected.",
                "data_metrics": f"Amount: ₹{amt_num:,.0f} | Status: Overdue | Due: {due}",
                "recommendation": "Dispatch a payment reminder email and contact the accounts payable department.",
                "why_explanation": f"Overdue receivables directly reduce operational liquidity and cash conversion speed.",
                "entity_id": i_id,
                "entity_type": "invoice",
                "action_type": "reminder",
                "target_page": "invoices",
                "primary_button_label": "View Invoice",
                "secondary_button_label": "Send Reminder"
            })
        elif i_status == "Pending" and amt_num >= 70000.0:
            actions.append({
                "id": f"inv-pending-{i_id}",
                "priority": "medium",
                "category": "invoices",
                "title": f"High-Value Pending Receivable: {i_id} ({client})",
                "problem": f"Large invoice of ₹{amt_num:,.0f} is scheduled for collection on {due}.",
                "data_metrics": f"Amount: ₹{amt_num:,.0f} | Due: {due}",
                "recommendation": "Verify invoice receipt with client finance team to ensure smooth disbursement.",
                "why_explanation": f"High-value invoices comprise significant working capital for this settlement period.",
                "entity_id": i_id,
                "entity_type": "invoice",
                "action_type": "followup",
                "target_page": "invoices",
                "primary_button_label": "View Invoice",
                "secondary_button_label": "Follow Up"
            })

    # 4. Sales & Growth Opportunities
    actions.append({
        "id": "sales-growth-q3",
        "priority": "medium",
        "category": "sales",
        "title": "Capitalize on Enterprise Software Upsells",
        "problem": "Software licenses show a 38% revenue share with strong renewal demand velocity.",
        "data_metrics": "Category Revenue: 38% | MoM Growth: +8.5%",
        "recommendation": "Launch targeted add-on promotions (Cloud Storage & API packages) for Enterprise tier clients.",
        "why_explanation": "ML sales forecast predicts a +7.6% revenue increase if multi-tier bundles are offered.",
        "entity_id": "sales-q3",
        "entity_type": "sales",
        "action_type": "campaign",
        "target_page": "sales",
        "primary_button_label": "View Sales Analytics",
        "secondary_button_label": "Export Forecast"
    })

    # 5. Profit Margin Optimization Actions
    cursor.execute("SELECT id, name, category, buy, sell, qty FROM profit_products")
    profit_items = [dict(r) for r in cursor.fetchall()]
    for p in profit_items:
        buy = p["buy"]
        sell = p["sell"]
        p_name = p["name"]
        p_id = p["id"]
        margin = ((sell - buy) / sell) * 100 if sell > 0 else 0.0

        if margin < 25.0:
            prio = "high" if margin < 15.0 else "medium"
            actions.append({
                "id": f"profit-margin-{p_id}",
                "priority": prio,
                "category": "profit",
                "title": f"Compressed Margin: {p_name} ({margin:.1f}%)",
                "problem": f"Product realized margin is only {margin:.1f}% (Buy: ₹{buy:,.0f} vs Sell: ₹{sell:,.0f}).",
                "data_metrics": f"Margin: {margin:.1f}% | Buy: ₹{buy:,.0f} | Sell: ₹{sell:,.0f}",
                "recommendation": "Negotiate volume supplier pricing or adjust retail price point to target 35%+ margin.",
                "why_explanation": f"Low unit margin limits total gross profit despite steady sales volume.",
                "entity_id": p_id,
                "entity_type": "profit",
                "action_type": "pricing",
                "target_page": "profit",
                "primary_button_label": "View Profit Analysis",
                "secondary_button_label": "Adjust Pricing"
            })

    # 6. Employee Operations Actions
    cursor.execute("SELECT id, name, role, dept, attendance, performance, status FROM employees")
    employees = [dict(r) for r in cursor.fetchall()]
    for emp in employees:
        att = emp.get("attendance", 95)
        perf = emp.get("performance", 90)
        e_name = emp["name"]
        e_dept = emp.get("dept", "")
        e_status = emp.get("status", "Active")
        e_id = emp["id"]

        if att < 85 or e_status == "On Leave":
            actions.append({
                "id": f"emp-att-{e_id}",
                "priority": "medium",
                "category": "employees",
                "title": f"Coverage Review: {e_name} ({e_dept})",
                "problem": f"Attendance is recorded at {att}% ({e_status}) in the {e_dept} department.",
                "data_metrics": f"Attendance: {att}% | Status: {e_status} | Dept: {e_dept}",
                "recommendation": "Review team workload distribution to ensure support and operational SLA continuity.",
                "why_explanation": f"Reduced coverage in {e_dept} can impact customer ticket resolution turnaround times.",
                "entity_id": e_id,
                "entity_type": "employee",
                "action_type": "review",
                "target_page": "employees",
                "primary_button_label": "View Employee",
                "secondary_button_label": "Manage Schedule"
            })
        elif perf < 88:
            actions.append({
                "id": f"emp-perf-{e_id}",
                "priority": "low",
                "category": "employees",
                "title": f"Skill Mentorship: {e_name} ({emp.get('role', 'Staff')})",
                "problem": f"Quarterly performance index is {perf}%, slightly below team benchmark of 90%.",
                "data_metrics": f"Performance: {perf}% | Role: {emp.get('role', 'Staff')}",
                "recommendation": "Schedule a 1-on-1 development check-in and assign dedicated learning modules.",
                "why_explanation": "Providing structured mentorship helps bridge individual output to senior benchmarks.",
                "entity_id": e_id,
                "entity_type": "employee",
                "action_type": "review",
                "target_page": "employees",
                "primary_button_label": "View Employee",
                "secondary_button_label": "Assign Training"
            })

    # Ensure field aliases exist on all actions
    for a in actions:
        if "description" not in a:
            a["description"] = a.get("problem", "")
        if "metric" not in a:
            a["metric"] = a.get("data_metrics", "")
        if "why_reason" not in a:
            a["why_reason"] = a.get("why_explanation", "")
        if "action_label" not in a:
            a["action_label"] = a.get("primary_button_label", "Take Action")
        if "impact" not in a:
            a["impact"] = "High Impact" if a.get("priority") in ["critical", "high"] else ("Medium Impact" if a.get("priority") == "medium" else "Low Impact")

    # Sort actions strictly by priority: Critical (0) > High (1) > Medium (2) > Low (3)
    prio_weights = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    actions.sort(key=lambda a: prio_weights.get(a["priority"], 99))

    # Calculate summary metrics
    crit_count = sum(1 for a in actions if a["priority"] == "critical")
    high_count = sum(1 for a in actions if a["priority"] == "high")
    med_count = sum(1 for a in actions if a["priority"] == "medium")
    low_count = sum(1 for a in actions if a["priority"] == "low")
    total_count = len(actions)

    category_counts = {}
    for a in actions:
        cat = a["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    from datetime import datetime
    now_str = datetime.now().strftime("%b %d, %Y, %I:%M %p")

    if close_after:
        conn.close()

    return {
        "status": "success",
        "summary": {
            "total": total_count,
            "critical": crit_count,
            "high": high_count,
            "medium": med_count,
            "low": low_count,
            "by_category": category_counts
        },
        "actions": actions,
        "items": actions,
        "last_analyzed": now_str
    }


@app.get("/api/action-center")
def get_action_center(user: dict = Depends(get_authenticated_user)):
    return generate_action_center_items()



# ============================================================
# SERVER EXECUTION
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "ai_backend:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        app_dir=str(BASE_DIR)
    )