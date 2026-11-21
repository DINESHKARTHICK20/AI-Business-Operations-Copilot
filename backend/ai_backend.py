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
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI, HTTPException, Query, Header, Depends, Request, Response
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score, mean_absolute_error, mean_squared_error, r2_score,
    precision_score, recall_score, f1_score, roc_auc_score
)
from sklearn.model_selection import train_test_split
import pymupdf
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("bizops.auth")


# ============================================================
# SECURITY & ENVIRONMENT CONFIGURATION
# ============================================================

SECRET_KEY = os.environ.get("SECRET_KEY", "bizops_prod_secret_key_change_in_production_2026")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true" or IS_PRODUCTION

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

PROJECT_ROOT = BASE_DIR.parent
DIST_DIR = PROJECT_ROOT / "dist"
DIST_ASSETS_DIR = DIST_DIR / "assets"
DIST_INDEX_FILE = DIST_DIR / "index.html"

MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)

CHURN_MODEL = MODEL_DIR / "churn_model.pkl"
SALES_MODEL = MODEL_DIR / "sales_model.pkl"
INVENTORY_MODEL = MODEL_DIR / "inventory_model.pkl"

DB_PATH = Path(os.environ.get("DB_PATH", str(BASE_DIR / "ai_bizops.db")))


def get_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        fk_check = conn.execute("PRAGMA foreign_keys;").fetchone()
        if not fk_check or fk_check[0] != 1:
            conn.close()
            logger.critical("FATAL: SQLite foreign_keys constraint enforcement failed to activate.")
            raise RuntimeError("Database connection initialization failed: foreign_keys enforcement could not be enabled.")
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        logger.critical("Database connection initialization error: %s", e)
        raise
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
    except Exception as e:
        logger.warning("Could not set WAL or synchronous pragmas during init_db: %s", e)

    # Customers Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER DEFAULT 1,
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
        user_id INTEGER DEFAULT 1,
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
        user_id INTEGER DEFAULT 1,
        name TEXT NOT NULL,
        sku TEXT NOT NULL,
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
        user_id INTEGER DEFAULT 1,
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
        user_id INTEGER DEFAULT 1,
        invoice_id TEXT NOT NULL,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        line_total REAL NOT NULL,
        FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
    )
    """)

    # Profit Products Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profit_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER DEFAULT 1,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        buy REAL NOT NULL,
        sell REAL NOT NULL,
        qty INTEGER NOT NULL
    )
    """)

    # Business Activities Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS business_activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        icon TEXT DEFAULT 'Activity',
        text TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        color TEXT DEFAULT 'text-indigo-500',
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # Notifications Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        desc TEXT NOT NULL,
        read INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # Expenses Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        description TEXT,
        date TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # Safe multi-tenant migrations: ensure user_id column exists on all tenant tables
    for tbl in ["customers", "employees", "products", "invoices", "invoice_items", "profit_products"]:
        cursor.execute(f"PRAGMA table_info({tbl})")
        t_cols = [r[1] for r in cursor.fetchall()]
        if "user_id" not in t_cols and len(t_cols) > 0:
            cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN user_id INTEGER DEFAULT 1")
            cursor.execute(f"UPDATE {tbl} SET user_id = 1 WHERE user_id IS NULL")

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

    # Create indexes for multi-tenant isolation performance
    indexes = [
        ("idx_customers_user_id", "customers(user_id)"),
        ("idx_employees_user_id", "employees(user_id)"),
        ("idx_products_user_id", "products(user_id)"),
        ("idx_invoices_user_id", "invoices(user_id)"),
        ("idx_invoice_items_user_id", "invoice_items(user_id)"),
        ("idx_profit_user_id", "profit_products(user_id)"),
        ("idx_activities_user_id", "business_activities(user_id)"),
        ("idx_notifications_user_id", "notifications(user_id)"),
        ("idx_expenses_user_id", "expenses(user_id)")
    ]
    for idx_name, idx_target in indexes:
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_target}")

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
    if "is_verified" not in user_cols and len(user_cols) > 0:
        cursor.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 1")

    # Drop obsolete pending_registrations table (OTP verification removed)
    try:
        cursor.execute("DROP TABLE IF EXISTS pending_registrations")
    except Exception:
        pass

    # Sync password_hash from legacy password column if password_hash is empty
    try:
        cursor.execute("UPDATE users SET password_hash = password WHERE (password_hash IS NULL OR password_hash = '') AND password != ''")
    except Exception:
        pass

    # User Sessions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        last_activity TEXT NOT NULL DEFAULT '',
        revoked_at TEXT DEFAULT NULL,
        csrf_token TEXT DEFAULT '',
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    cursor.execute("PRAGMA table_info(user_sessions)")
    sess_cols = [row[1] for row in cursor.fetchall()]
    if "last_activity" not in sess_cols and len(sess_cols) > 0:
        cursor.execute("ALTER TABLE user_sessions ADD COLUMN last_activity TEXT DEFAULT ''")
    if "revoked_at" not in sess_cols and len(sess_cols) > 0:
        cursor.execute("ALTER TABLE user_sessions ADD COLUMN revoked_at TEXT DEFAULT NULL")
    if "csrf_token" not in sess_cols and len(sess_cols) > 0:
        cursor.execute("ALTER TABLE user_sessions ADD COLUMN csrf_token TEXT DEFAULT ''")

    # Ensure index on user_sessions expires_at and user_id for fast lookup & pruning
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at)")

    # Prune orphaned legacy sessions
    try:
        cursor.execute("DELETE FROM user_sessions WHERE user_id NOT IN (SELECT id FROM users)")
    except Exception:
        pass

    # Prune expired sessions at startup to keep the table lean
    try:
        now_startup = __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("DELETE FROM user_sessions WHERE expires_at < ?", (now_startup,))
        pruned = cursor.rowcount
        if pruned > 0:
            print(f"[startup] Pruned {pruned} expired session(s) from user_sessions")
    except Exception:
        pass


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


def log_activity(conn, user_id: int, icon: str, text: str, category: str = "general", color: str = "text-indigo-500"):
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
        INSERT INTO business_activities (user_id, icon, text, category, color, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, icon, text, category, color, now_str))
        conn.commit()
    except Exception as e:
        logger.warning("Failed to log activity for user %s: %s", user_id, e)


def add_notification(conn, user_id: int, notif_type: str, title: str, desc: str):
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
        INSERT INTO notifications (user_id, type, title, desc, read, created_at)
        VALUES (?, ?, ?, ?, 0, ?)
        """, (user_id, notif_type, title, desc, now_str))
        conn.commit()
    except Exception as e:
        logger.warning("Failed to add notification for user %s: %s", user_id, e)


# ============================================================
# FASTAPI BACKEND SETUP
# ============================================================

# Configure API documentation URLs: disabled in production for security (SEC-03)
docs_url = None if IS_PRODUCTION else "/docs"
redoc_url = None if IS_PRODUCTION else "/redoc"
openapi_url = None if IS_PRODUCTION else "/openapi.json"

app = FastAPI(
    title="AI Business Operations Copilot",
    version="1.0.0",
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url
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
    try:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if SESSION_COOKIE_SECURE:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
    except Exception as exc:
        logger.error(
            "Unhandled server exception on %s %s: %s",
            request.method,
            request.url.path,
            exc,
            exc_info=True
        )
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "An unexpected server error occurred. Please try again.",
                "detail": "An unexpected server error occurred. Please try again."
            }
        )


@app.exception_handler(Exception)
async def global_unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled server exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "An unexpected server error occurred. Please try again later.",
            "detail": "An unexpected server error occurred. Please try again later."
        }
    )


# Static Assets Mount for Built Frontend (Vite)
DIST_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(DIST_ASSETS_DIR)), name="static_assets")


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


def create_sales_data(rows=120):
    random.seed(42)
    data = []
    for month in range(1, rows + 1):
        base_revenue = 4000000 + month * 50000
        seasonal_factor = 1 + 0.10 * math.sin(month / 12 * 2 * math.pi)
        revenue = max(500000, base_revenue * seasonal_factor + random.gauss(0, 100000))
        orders = max(50, round(revenue / random.uniform(5200, 6200)))
        marketing_spend = round(revenue * random.uniform(0.07, 0.11), 2)
        data.append({
            "month_index": month,
            "revenue": round(revenue, 2),
            "orders": orders,
            "marketing_spend": marketing_spend
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
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    acc = round(float(accuracy_score(y_test, y_pred)), 4)
    prec = round(float(precision_score(y_test, y_pred, zero_division=0)), 4)
    rec = round(float(recall_score(y_test, y_pred, zero_division=0)), 4)
    f1 = round(float(f1_score(y_test, y_pred, zero_division=0)), 4)
    auc = round(float(roc_auc_score(y_test, y_proba)), 4)

    metrics = {
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1_score": f1,
        "roc_auc": auc,
        "test_samples": len(y_test),
        "train_samples": len(X_train),
        "model_type": "RandomForestClassifier(n_estimators=300, max_depth=10)"
    }
    joblib.dump({"model": model, "features": features, "metrics": metrics}, CHURN_MODEL)
    logger.info("Trained Churn Model: Accuracy=%.2f%% F1=%.4f ROC-AUC=%.4f", acc * 100, f1, auc)


def train_sales_model():
    data = create_sales_data(rows=120)
    features = ["month_index", "orders", "marketing_spend"]
    X = data[features]
    y = data["revenue"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )
    model = RandomForestRegressor(
        n_estimators=250, max_depth=12, min_samples_leaf=2, random_state=42
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    mae = round(float(mean_absolute_error(y_test, y_pred)), 2)
    rmse = round(float(math.sqrt(mean_squared_error(y_test, y_pred))), 2)
    r2 = round(float(r2_score(y_test, y_pred)), 4)

    metrics = {
        "mae": mae,
        "rmse": rmse,
        "r2_score": r2,
        "test_samples": len(y_test),
        "train_samples": len(X_train),
        "model_type": "RandomForestRegressor(n_estimators=250, max_depth=12)"
    }
    joblib.dump({"model": model, "features": features, "metrics": metrics}, SALES_MODEL)
    logger.info("Trained Sales Model: MAE=%.2f RMSE=%.2f R2=%.4f", mae, rmse, r2)


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
    y_pred = model.predict(X_test)
    mae = round(float(mean_absolute_error(y_test, y_pred)), 2)
    rmse = round(float(math.sqrt(mean_squared_error(y_test, y_pred))), 2)
    r2 = round(float(r2_score(y_test, y_pred)), 4)

    metrics = {
        "mae": mae,
        "rmse": rmse,
        "r2_score": r2,
        "test_samples": len(y_test),
        "train_samples": len(X_train),
        "model_type": "RandomForestRegressor(n_estimators=300, max_depth=12)"
    }
    joblib.dump({"model": model, "features": features, "metrics": metrics}, INVENTORY_MODEL)
    logger.info("Trained Inventory Model: MAE=%.2f RMSE=%.2f R2=%.4f", mae, rmse, r2)


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

if "metrics" not in churn_bundle:
    train_churn_model()
    churn_bundle = joblib.load(CHURN_MODEL)
if "metrics" not in sales_bundle:
    train_sales_model()
    sales_bundle = joblib.load(SALES_MODEL)
if "metrics" not in inventory_bundle:
    train_inventory_model()
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
    if DIST_INDEX_FILE.exists():
        return FileResponse(str(DIST_INDEX_FILE))
    return {
        "project": "AI Business Operations Copilot",
        "status": "Backend running",
        "database": "SQLite (ai_bizops.db) connected",
        "machine_learning": [
            "Customer Churn Prediction",
            "Sales Forecasting",
            "Inventory Demand Prediction"
        ],
        "notice": "Frontend build (dist/index.html) not found. Run 'npm run build' to generate static assets."
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


class SignupRateLimiter:
    """In-memory rate limiter tracking signup attempts per IP to prevent registration flooding."""
    def __init__(self, max_attempts_per_ip: int = 15, window_seconds: int = 300):
        self.max_attempts_per_ip = max_attempts_per_ip
        self.window_seconds = window_seconds
        self.attempts: Dict[str, List[float]] = {}

    def _clean(self, ip: str, now: float):
        if ip in self.attempts:
            self.attempts[ip] = [t for t in self.attempts[ip] if now - t < self.window_seconds]
            if not self.attempts[ip]:
                del self.attempts[ip]

    def is_rate_limited(self, ip: str) -> bool:
        now = time.time()
        self._clean(ip, now)
        return len(self.attempts.get(ip, [])) >= self.max_attempts_per_ip

    def record_attempt(self, ip: str):
        now = time.time()
        self._clean(ip, now)
        if ip not in self.attempts:
            self.attempts[ip] = []
        self.attempts[ip].append(now)

    def get_remaining_seconds(self, ip: str) -> int:
        now = time.time()
        self._clean(ip, now)
        timestamps = self.attempts.get(ip, [])
        if not timestamps:
            return 0
        oldest = min(timestamps)
        remaining = self.window_seconds - (now - oldest)
        return max(0, int(remaining))


signup_limiter = SignupRateLimiter(max_attempts_per_ip=15, window_seconds=300)


def generate_session_csrf_token(session_token: str) -> str:
    """Derive a cryptographically secure, unguessable CSRF token bound to the authenticated session."""
    if not session_token:
        return ""
    return hmac.new(
        SECRET_KEY.encode("utf-8"),
        f"bizops_csrf_session:{session_token}".encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def generate_preauth_csrf_token() -> str:
    """Generate a random cryptographic CSRF token for pre-authenticated sessions."""
    return secrets.token_urlsafe(32)


def generate_csrf_token(session_token: Optional[str] = None) -> str:
    """Generate a session-bound or pre-auth CSRF token."""
    if session_token:
        return generate_session_csrf_token(session_token)
    return generate_preauth_csrf_token()


# ============================================================
# STRONG PASSWORD POLICY & VALIDATION (SEC-04)
# ============================================================

COMMON_WEAK_PASSWORDS = {
    # Numerical sequences
    "123456", "1234567", "12345678", "123456789", "1234567890", "123456789012", "012345678901",
    "111111", "111111111111", "000000000000", "987654321098", "654321",
    # Classic weak passwords
    "password", "password123", "password1234", "password12345", "password123456",
    "password!@#$", "p@ssword1234", "p@ssw0rd1234", "admin1234567", "administrator",
    "qwerty", "qwerty123456", "qwertyuiopas", "asdfghjklzxc", "zxcvbnmasdfg",
    "welcome12345", "welcome123456", "welcome2026!", "letmein12345", "iloveyou1234",
    "changeme1234", "default12345", "business1234", "company12345", "secret123456",
    "trustnoone12", "dragon123456", "monkey123456", "football1234", "baseball1234",
    "master123456", "access123456", "superman1234", "sunshine1234", "princess1234"
}

COMMON_ROOTS = [
    "password", "123456", "qwerty", "admin", "welcome", "letmein", "changeme",
    "default", "iloveyou", "secret", "master", "access", "testing"
]


def validate_strong_password(
    password: str,
    email: Optional[str] = None,
    name: Optional[str] = None
) -> None:
    """Validates password strength according to SEC-04 production requirements and NIST guidelines.
    Enforces minimum 12 characters, rejects common/compromised passwords, eliminates obvious user
    account patterns, and accommodates long passphrases without arbitrary complexity barriers.
    """
    if not password:
        raise HTTPException(status_code=400, detail="Password is required.")

    # 1. Minimum Length Requirement (>= 12 characters)
    if len(password) < 12:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 12 characters long."
        )

    # 2. Maximum reasonable length to protect against DoS
    if len(password) > 512:
        raise HTTPException(
            status_code=400,
            detail="Password cannot exceed 512 characters."
        )

    pwd_lower = password.strip().lower()

    # 3. Reject Known Common / Compromised Passwords
    if pwd_lower in COMMON_WEAK_PASSWORDS:
        raise HTTPException(
            status_code=400,
            detail="Password is too common or easily guessed. Please choose a more secure password."
        )

    # Check for root word with trivial numeric/symbol extensions
    for root in COMMON_ROOTS:
        for suffix in ["", "1", "12", "123", "1234", "12345", "123456", "!", "123!", "2026", "2026!"]:
            if pwd_lower == root + suffix:
                raise HTTPException(
                    status_code=400,
                    detail="Password is based on a common easily guessed phrase. Please choose a stronger password."
                )

    # 4. Reject Single-Character Repetition and Simple Repetitive Sequences
    if len(set(password)) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Password cannot consist of a single repeated character."
        )

    if len(set(password)) <= 2 and len(password) >= 12:
        raise HTTPException(
            status_code=400,
            detail="Password contains too much repetition. Please choose a more varied password or passphrase."
        )

    # 5. Prevent Obvious Account-Specific Information (Email / Name)
    if name:
        clean_name = name.strip().lower()
        for token in re.split(r"\s+", clean_name):
            if len(token) >= 4 and token in pwd_lower:
                raise HTTPException(
                    status_code=400,
                    detail="Password must not contain your name."
                )

    if email:
        clean_email = email.strip().lower()
        local_part = clean_email.split("@")[0] if "@" in clean_email else clean_email
        if len(local_part) >= 3 and local_part in pwd_lower:
            raise HTTPException(
                status_code=400,
                detail="Password must not contain your email address or username."
            )
        # Check sub-tokens of email (e.g. john.doe -> john, doe)
        for token in re.split(r"[\._\-\+0-9]+", local_part):
            if len(token) >= 4 and token in pwd_lower:
                raise HTTPException(
                    status_code=400,
                    detail="Password must not contain parts of your email address."
                )


def hash_password(plain_password: str) -> str:
    """Securely hash a plain text password using bcrypt.
    Safely handles passwords/passphrases of any length without crashing on bcrypt's 72-byte limit.
    """
    salt = bcrypt.gensalt(rounds=12)
    pw_bytes = plain_password.encode("utf-8")
    if len(pw_bytes) > 72:
        # Pre-hash long passphrases with SHA-256 (32 bytes) to safely fit bcrypt's 72-byte limit
        pw_bytes = hashlib.sha256(pw_bytes).digest()
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a stored hashed password (bcrypt / legacy support).
    Supports standard passwords, pre-hashed long passphrases, and 72-byte truncated passphrases.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        if hashed_password.startswith(("$2b$", "$2a$", "$2y$")):
            pw_bytes = plain_password.encode("utf-8")
            hashed_bytes = hashed_password.encode("utf-8")
            # 1. Standard check for passwords <= 72 bytes
            if len(pw_bytes) <= 72:
                if bcrypt.checkpw(pw_bytes, hashed_bytes):
                    return True
            # 2. SHA-256 pre-hashed check for long passphrases (> 72 bytes)
            prehashed = hashlib.sha256(pw_bytes).digest()
            if bcrypt.checkpw(prehashed, hashed_bytes):
                return True
            # 3. Truncated 72-byte fallback if previously hashed via truncation
            if len(pw_bytes) > 72:
                if bcrypt.checkpw(pw_bytes[:72], hashed_bytes):
                    return True
            return False

        if ":" in hashed_password:
            salt, h = hashed_password.split(":", 1)
            calc = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
            return hmac.compare_digest(calc, h)
        return plain_password == hashed_password
    except Exception:
        return False


def create_user_session(cursor, user_id: int) -> str:
    """Generate a cryptographically secure session token and store in user_sessions (7-day validity)."""
    now_dt = datetime.now()
    created_at = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    expires_at = (now_dt + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    last_activity = created_at

    token = secrets.token_urlsafe(32)
    csrf_tok = generate_session_csrf_token(token)
    cursor.execute("""
    INSERT INTO user_sessions (token, user_id, created_at, expires_at, last_activity, revoked_at, csrf_token)
    VALUES (?, ?, ?, ?, ?, NULL, ?)
    """, (token, user_id, created_at, expires_at, last_activity, csrf_tok))
    return token


def get_authenticated_user(request: Request) -> dict:
    """Dependency: Extract session token from cookie (or fallback Bearer header), validate and return user.
    Enforces strict CSRF token validation on all state-changing requests authenticated via cookies.
    """
    cookie_token = request.cookies.get("session_token")
    auth_via_cookie = bool(cookie_token)
    token = cookie_token

    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split("Bearer ", 1)[1].strip()
            auth_via_cookie = False

    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized - authentication required")

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        SELECT s.token, s.expires_at, s.revoked_at, s.last_activity, s.csrf_token, u.id, u.name, u.email, u.company, u.biz_type, u.is_active
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

        # Secure CSRF token bound to this specific session
        expected_csrf = row_dict.get("csrf_token") or generate_session_csrf_token(token.strip())

        # Enforce CSRF protection on state-changing requests authenticated through cookies
        if auth_via_cookie and request.method in ("POST", "PUT", "DELETE", "PATCH"):
            csrf_header = request.headers.get("X-CSRF-Token") or request.headers.get("X-XSRF-Token")
            if not csrf_header or not csrf_header.strip():
                logger.warning(
                    "CSRF validation failed: missing X-CSRF-Token header on %s %s (user_id=%s)",
                    request.method, request.url.path, row_dict["id"]
                )
                raise HTTPException(
                    status_code=403,
                    detail="CSRF token missing. A valid X-CSRF-Token request header is required for cookie-authenticated state-changing requests."
                )

            if not hmac.compare_digest(csrf_header.strip(), expected_csrf):
                logger.warning(
                    "CSRF validation failed: mismatched X-CSRF-Token header on %s %s (user_id=%s)",
                    request.method, request.url.path, row_dict["id"]
                )
                raise HTTPException(
                    status_code=403,
                    detail="Invalid or mismatched CSRF token. Request rejected."
                )

        # Throttle last_activity updates to at most once every 5 minutes to avoid SQLite write lock contention
        try:
            last_act_str = row_dict.get("last_activity") or ""
            should_update = True
            if last_act_str:
                try:
                    last_act_dt = datetime.strptime(last_act_str, "%Y-%m-%d %H:%M:%S")
                    if (datetime.now() - last_act_dt).total_seconds() < 300:
                        should_update = False
                except ValueError:
                    pass

            if should_update:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("UPDATE user_sessions SET last_activity = ? WHERE token = ?", (now_str, token.strip()))
                conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

        return {
            "id": row_dict["id"],
            "name": row_dict["name"],
            "email": row_dict["email"],
            "company": row_dict["company"] or "",
            "biz_type": row_dict["biz_type"] or "E-commerce",
            "session_token": token.strip(),
            "csrf_token": expected_csrf,
            "auth_via_cookie": auth_via_cookie
        }
    finally:
        try:
            conn.close()
        except Exception:
            pass


class LogoutRequest(BaseModel):
    token: Optional[str] = None


# ============================================================
# AUTHENTICATION & USER MANAGEMENT APIS
# ============================================================

@app.get("/api/auth/csrf")
def get_csrf_token(request: Request, response: Response):
    """Issue a fresh CSRF token stored in a readable cookie and JSON response."""
    session_token = request.cookies.get("session_token")
    if session_token:
        token = generate_session_csrf_token(session_token.strip())
    else:
        token = generate_preauth_csrf_token()

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
@app.post("/api/auth/register/")
@app.post("/api/auth/signup")
@app.post("/api/auth/signup/")
def register_user(req: UserRegisterRequest, request: Request, response: Response):
    """
    Registers a new user account directly into SQLite without email OTP verification.
    Validates name, email, and password (>= 6 chars).
    Ensures email uniqueness, securely hashes the password with bcrypt,
    and initializes a clean private business workspace.
    """
    client_ip = request.client.host if request.client else "unknown"
    if signup_limiter.is_rate_limited(client_ip):
        wait_sec = signup_limiter.get_remaining_seconds(client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"Too many registration attempts. Please try again in {max(1, wait_sec)} seconds."
        )

    clean_name = (req.name or "").strip()
    clean_email = (req.email or "").strip().lower()
    raw_password = req.password or ""
    clean_company = (req.company or "").strip() or f"{clean_name}'s Business"
    clean_biz = (req.biz_type or "").strip() or "General Business"

    if not clean_name:
        raise HTTPException(status_code=400, detail="Name is required.")
    if not clean_email or not EMAIL_REGEX.match(clean_email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    
    signup_limiter.record_attempt(client_ip)

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (clean_email,))
        existing = cursor.fetchone()

        if existing:
            raise HTTPException(status_code=400, detail="An account with this email already exists. Please sign in.")

        # Enforce SEC-04 strong password validation (length >= 12, common password blacklist, email/name pattern check)
        validate_strong_password(raw_password, email=clean_email, name=clean_name)

        hashed_pw = hash_password(raw_password)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
        INSERT INTO users (name, email, password_hash, password, company, biz_type, created_at, updated_at, is_active, is_verified)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1)
        """, (clean_name, clean_email, hashed_pw, hashed_pw, clean_company, clean_biz, now_str, now_str))
        user_id = cursor.lastrowid

        # Log initial welcome activity and notification for the new account's independent workspace
        log_activity(conn, user_id, "UserCheck", "Business workspace initialized.", "setup", "text-indigo-500")
        add_notification(conn, user_id, "ai", "Welcome to AI BizOps!", "Your private business workspace is ready. Add customers and products to begin.")

        conn.commit()
    except HTTPException:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    except sqlite3.IntegrityError:
        try:
            conn.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="An account with this email already exists. Please sign in.")
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error("Unexpected error during registration for %s: %s", clean_email, e, exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while creating your account. Please try again.")
    finally:
        try:
            conn.close()
        except Exception:
            pass

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
        "message": "Account created successfully.",
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

    # Retry loop with backoff for SQLite transient busy / lock conditions
    max_retries = 3
    for attempt in range(max_retries):
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

            if not stored_hash:
                logger.warning(
                    "Login attempt for account %s has no password hash stored. "
                    "This account cannot be authenticated until a password is set.",
                    clean_email
                )

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
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "UPDATE users SET password_hash = ?, password = ?, updated_at = ? WHERE id = ?",
                    (new_hash, new_hash, now_str, user_dict["id"])
                )

            token = create_user_session(cursor, user_dict["id"])
            csrf_tok = generate_session_csrf_token(token)
            conn.commit()

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

            logger.info("User login successful: id=%s email=%s", user_dict["id"], clean_email)

            return {
                "status": "success",
                "message": "Signed in successfully.",
                "user": {
                    "id": user_dict["id"],
                    "name": user_dict["name"],
                    "email": user_dict["email"],
                    "company": user_dict["company"] or "",
                    "biz_type": user_dict["biz_type"] or "E-commerce"
                },
                "csrf_token": csrf_tok
            }

        except HTTPException:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        except sqlite3.OperationalError as oe:
            try:
                conn.rollback()
            except Exception:
                pass
            is_locked = "locked" in str(oe).lower() or "busy" in str(oe).lower()
            if is_locked and attempt < max_retries - 1:
                logger.warning(
                    "Database busy during login for %s (attempt %d/%d). Retrying...",
                    clean_email, attempt + 1, max_retries
                )
                time.sleep(0.05 * (2 ** attempt))
                continue
            logger.error("Database operational error during login for %s: %s", clean_email, oe, exc_info=True)
            raise HTTPException(
                status_code=503,
                detail="Database is momentarily busy. Please try again in a few seconds."
            )
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error("Unexpected error during login for %s: %s", clean_email, e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="An unexpected error occurred while processing your sign-in. Please try again."
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass


@app.get("/api/auth/me")
def get_current_user_me(response: Response, user: dict = Depends(get_authenticated_user)):
    csrf_tok = user.get("csrf_token") or (generate_session_csrf_token(user.get("session_token", "")) if user.get("session_token") else "")
    if csrf_tok:
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
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "company": user.get("company", ""),
        "biz_type": user.get("biz_type", ""),
        "csrf_token": csrf_tok,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "company": user.get("company", ""),
            "biz_type": user.get("biz_type", "")
        }
    }


@app.post("/api/auth/logout")
def logout_user(request: Request, response: Response):
    cookie_token = request.cookies.get("session_token")
    auth_via_cookie = bool(cookie_token)
    token = cookie_token
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split("Bearer ", 1)[1].strip()

    if token:
        # Validate CSRF token if request is authenticated through cookies
        if auth_via_cookie:
            csrf_header = request.headers.get("X-CSRF-Token") or request.headers.get("X-XSRF-Token")
            if not csrf_header or not csrf_header.strip():
                raise HTTPException(
                    status_code=403,
                    detail="CSRF token missing. A valid X-CSRF-Token request header is required for logout."
                )
            expected_csrf = generate_session_csrf_token(token.strip())
            if not hmac.compare_digest(csrf_header.strip(), expected_csrf):
                raise HTTPException(
                    status_code=403,
                    detail="Invalid or mismatched CSRF token. Logout rejected."
                )

        conn = get_db()
        cursor = conn.cursor()
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("UPDATE user_sessions SET revoked_at = ? WHERE token = ?", (now_str, token.strip()))
            cursor.execute("DELETE FROM user_sessions WHERE token = ?", (token.strip(),))
            conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.warning("Error during logout session deletion: %s", e)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    response.delete_cookie(
        key="session_token",
        path="/",
        httponly=True,
        samesite="lax",
        secure=SESSION_COOKIE_SECURE
    )
    response.delete_cookie(
        key="csrf_token",
        path="/",
        httponly=False,
        samesite="lax",
        secure=SESSION_COOKIE_SECURE
    )

    return {"status": "success", "message": "Logged out successfully"}





# ============================================================
# 1. CUSTOMERS APIS (MULTI-TENANT)
# ============================================================

@app.get("/api/customers")
def get_customers(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM customers WHERE user_id = ? ORDER BY id ASC", (user["id"],))
        rows = [dict(r) for r in cursor.fetchall()]
        return rows
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.post("/api/customers")
def create_customer(customer: CustomerCreate, user: dict = Depends(get_authenticated_user)):
    if not customer.name or not customer.name.strip():
        raise HTTPException(status_code=400, detail="Customer name is required.")
    if not customer.email or not customer.email.strip() or "@" not in customer.email:
        raise HTTPException(status_code=400, detail="A valid customer email address is required.")
    if not customer.company or not customer.company.strip():
        raise HTTPException(status_code=400, detail="Customer company name is required.")

    conn = get_db()
    cursor = conn.cursor()
    try:
        joined_date = customer.joined or datetime.now().strftime("%b %Y")

        # Calculate churn score from model
        churn_prob = 0
        try:
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
        except Exception:
            churn_prob = 15

        cursor.execute("""
        INSERT INTO customers (
            user_id, name, email, company, status, ltv, total_spend, orders, joined,
            churn, days_since_last_purchase, support_tickets, complaints, average_order_value
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user["id"], customer.name, customer.email, customer.company, customer.status,
            customer.ltv, customer.total_spend, customer.orders, joined_date,
            churn_prob, customer.days_since_last_purchase, customer.support_tickets,
            customer.complaints, customer.average_order_value or 0.0
        ))
        new_id = cursor.lastrowid

        log_activity(conn, user["id"], "Users", f"Added customer: {customer.name} ({customer.company})", "customer", "text-blue-500")

        conn.commit()
        cursor.execute("SELECT * FROM customers WHERE id = ? AND user_id = ?", (new_id, user["id"]))
        created = dict(cursor.fetchone())
        return created
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.put("/api/customers/{customer_id}")
def update_customer(customer_id: int, update: CustomerUpdate, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE id = ? AND user_id = ?", (customer_id, user["id"]))
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
    try:
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
    except Exception:
        pass

    cursor.execute("""
    UPDATE customers SET
        name = ?, email = ?, company = ?, status = ?, ltv = ?, total_spend = ?,
        orders = ?, churn = ?, days_since_last_purchase = ?, support_tickets = ?,
        complaints = ?, average_order_value = ?
    WHERE id = ? AND user_id = ?
    """, (
        current["name"], current["email"], current["company"], current["status"],
        current["ltv"], current["total_spend"], current["orders"], current["churn"],
        current["days_since_last_purchase"], current["support_tickets"],
        current["complaints"], current.get("average_order_value", 0.0), customer_id, user["id"]
    ))
    conn.commit()
    cursor.execute("SELECT * FROM customers WHERE id = ? AND user_id = ?", (customer_id, user["id"]))
    updated = dict(cursor.fetchone())
    conn.close()
    return updated


@app.delete("/api/customers/{customer_id}")
def delete_customer(customer_id: int, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM customers WHERE id = ? AND user_id = ?", (customer_id, user["id"]))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Customer not found")

    cursor.execute("DELETE FROM customers WHERE id = ? AND user_id = ?", (customer_id, user["id"]))
    log_activity(conn, user["id"], "UserX", f"Removed customer: {existing['name']}", "customer", "text-rose-500")
    conn.commit()
    conn.close()
    return {"status": "success", "deleted_id": customer_id}


@app.post("/api/customers/{customer_id}/churn")
def predict_customer_churn_by_id(customer_id: int, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE id = ? AND user_id = ?", (customer_id, user["id"]))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Customer not found")

    cust = dict(row)
    try:
        orders = int(cust.get("orders") or 0)
    except (ValueError, TypeError):
        orders = 0

    raw_spend = cust.get("total_spend")
    if raw_spend is None or raw_spend == 0 or raw_spend == 0.0 or raw_spend == "0":
        raw_ltv = cust.get("ltv")
        if raw_ltv:
            clean_ltv = re.sub(r"[^\d.]", "", str(raw_ltv))
            total_spend = float(clean_ltv) if clean_ltv else 0.0
        else:
            total_spend = 0.0
    else:
        try:
            if isinstance(raw_spend, str):
                clean_spend = re.sub(r"[^\d.]", "", raw_spend)
                total_spend = float(clean_spend) if clean_spend else 0.0
            else:
                total_spend = float(raw_spend)
        except (ValueError, TypeError):
            total_spend = 0.0

    # Handle insufficient historical data
    if orders <= 0 and total_spend <= 0:
        conn.close()
        return {
            "customer_id": customer_id,
            "name": cust["name"],
            "has_prediction": False,
            "risk": "UNKNOWN",
            "churn_probability": None,
            "message": "Not enough data for prediction (new customer with no transaction history)",
            "recommendation": "Customer has no historical transactions. Engage customer to initiate first order.",
            "model_metrics": churn_bundle.get("metrics")
        }

    model = churn_bundle["model"]
    features = churn_bundle["features"]
    try:
        avg_val = float(cust.get("average_order_value") or 0.0)
    except (ValueError, TypeError):
        avg_val = 0.0
    if avg_val <= 0 and orders > 0:
        avg_val = total_spend / orders

    try:
        days_since = int(cust.get("days_since_last_purchase") or 15)
    except (ValueError, TypeError):
        days_since = 15

    try:
        support_tickets = int(cust.get("support_tickets") or 0)
    except (ValueError, TypeError):
        support_tickets = 0

    try:
        complaints = int(cust.get("complaints") or 0)
    except (ValueError, TypeError):
        complaints = 0

    input_data = pd.DataFrame(
        [[
            orders,
            total_spend,
            days_since,
            support_tickets,
            complaints,
            avg_val
        ]],
        columns=features
    )
    prob = round(float(model.predict_proba(input_data)[0][1]) * 100, 1)

    if prob >= 70:
        risk = "HIGH"
        recommendation = "High churn risk detected. Assign a dedicated Customer Success Manager and extend a personalized retention offer."
    elif prob >= 35:
        risk = "MEDIUM"
        recommendation = "Moderate churn risk. Schedule an engagement check-in and share updated offerings."
    else:
        risk = "LOW"
        recommendation = "Customer engagement is healthy. Continue standard communication."

    cursor.execute("UPDATE customers SET churn = ? WHERE id = ? AND user_id = ?", (int(prob), customer_id, user["id"]))
    conn.commit()
    conn.close()

    return {
        "customer_id": customer_id,
        "name": cust["name"],
        "has_prediction": True,
        "churn_probability": prob,
        "risk": risk,
        "recommendation": recommendation,
        "model_metrics": churn_bundle.get("metrics")
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
# 2. EMPLOYEES APIS (MULTI-TENANT)
# ============================================================

@app.get("/api/employees")
def get_employees(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM employees WHERE user_id = ? ORDER BY id ASC", (user["id"],))
        rows = [dict(r) for r in cursor.fetchall()]
        return rows
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.post("/api/employees")
def create_employee(emp: EmployeeCreate, user: dict = Depends(get_authenticated_user)):
    if not emp.name or not emp.name.strip():
        raise HTTPException(status_code=400, detail="Employee name is required.")
    if not emp.role or not emp.role.strip():
        raise HTTPException(status_code=400, detail="Employee role is required.")
    if emp.attendance is not None and (emp.attendance < 0 or emp.attendance > 100):
        raise HTTPException(status_code=400, detail="Attendance must be between 0 and 100%.")
    if emp.performance is not None and (emp.performance < 0 or emp.performance > 100):
        raise HTTPException(status_code=400, detail="Performance must be between 0 and 100%.")
    conn = get_db()
    cursor = conn.cursor()
    try:
        joined_date = emp.joined or datetime.now().strftime("%b %Y")
        cursor.execute("""
        INSERT INTO employees (user_id, name, role, dept, salary, status, attendance, performance, joined)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user["id"], emp.name, emp.role, emp.dept, emp.salary, emp.status,
            emp.attendance, emp.performance, joined_date
        ))
        new_id = cursor.lastrowid
        log_activity(conn, user["id"], "UserCheck", f"Onboarded employee: {emp.name} ({emp.role})", "employee", "text-purple-500")
        conn.commit()
        cursor.execute("SELECT * FROM employees WHERE id = ? AND user_id = ?", (new_id, user["id"]))
        created = dict(cursor.fetchone())
        return created
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.put("/api/employees/{emp_id}")
def update_employee(emp_id: int, emp: EmployeeUpdate, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees WHERE id = ? AND user_id = ?", (emp_id, user["id"]))
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
    WHERE id = ? AND user_id = ?
    """, (
        current["name"], current["role"], current["dept"], current["salary"],
        current["status"], current["attendance"], current["performance"], emp_id, user["id"]
    ))
    conn.commit()
    cursor.execute("SELECT * FROM employees WHERE id = ? AND user_id = ?", (emp_id, user["id"]))
    updated = dict(cursor.fetchone())
    conn.close()
    return updated


@app.delete("/api/employees/{emp_id}")
def delete_employee(emp_id: int, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM employees WHERE id = ? AND user_id = ?", (emp_id, user["id"]))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Employee not found")

    cursor.execute("DELETE FROM employees WHERE id = ? AND user_id = ?", (emp_id, user["id"]))
    log_activity(conn, user["id"], "UserMinus", f"Removed employee record: {existing['name']}", "employee", "text-rose-500")
    conn.commit()
    conn.close()
    return {"status": "success", "deleted_id": emp_id}


# ============================================================
# 3. INVENTORY & PRODUCTS APIS (MULTI-TENANT)
# ============================================================

@app.get("/api/inventory")
def get_inventory(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM products WHERE user_id = ? ORDER BY id ASC", (user["id"],))
        rows = [dict(r) for r in cursor.fetchall()]
        return rows
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.post("/api/inventory")
def create_product(prod: ProductCreate, user: dict = Depends(get_authenticated_user)):
    if not prod.name or not prod.name.strip():
        raise HTTPException(status_code=400, detail="Product name is required.")
    if not prod.sku or not prod.sku.strip():
        raise HTTPException(status_code=400, detail="Product SKU is required.")
    if prod.stock < 0:
        raise HTTPException(status_code=400, detail="Product stock cannot be negative.")
    if prod.reorder < 0:
        raise HTTPException(status_code=400, detail="Product reorder level cannot be negative.")

    clean_sku = prod.sku.strip()
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM products WHERE LOWER(sku) = LOWER(?)", (clean_sku,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=f"A product with SKU '{clean_sku}' already exists.")

        cursor.execute("""
        INSERT INTO products (
            user_id, name, sku, category, stock, reorder, price, price_num,
            status, trend, avg_daily_demand, trend_factor, promotion_factor
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user["id"], prod.name.strip(), clean_sku, prod.category, prod.stock, prod.reorder,
            prod.price, prod.price_num, prod.status, prod.trend,
            prod.avg_daily_demand, prod.trend_factor, prod.promotion_factor
        ))
        new_id = cursor.lastrowid
        log_activity(conn, user["id"], "Package", f"Cataloged product: {prod.name} ({clean_sku})", "inventory", "text-emerald-500")
        conn.commit()
        cursor.execute("SELECT * FROM products WHERE id = ? AND user_id = ?", (new_id, user["id"]))
        created = dict(cursor.fetchone())
        return created
    except sqlite3.IntegrityError:
        try:
            conn.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"A product with SKU '{clean_sku}' already exists.")
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.put("/api/inventory/{product_id}")
def update_product(product_id: int, prod: ProductUpdate, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ? AND user_id = ?", (product_id, user["id"]))
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
    WHERE id = ? AND user_id = ?
    """, (
        current["name"], current["sku"], current["category"], current["stock"],
        current["reorder"], current["price"], current["price_num"], current["status"],
        current["trend"], current["avg_daily_demand"], current["trend_factor"],
        current["promotion_factor"], product_id, user["id"]
    ))
    conn.commit()
    cursor.execute("SELECT * FROM products WHERE id = ? AND user_id = ?", (product_id, user["id"]))
    updated = dict(cursor.fetchone())
    conn.close()
    return updated


@app.delete("/api/inventory/{product_id}")
def delete_product(product_id: int, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM products WHERE id = ? AND user_id = ?", (product_id, user["id"]))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")

    cursor.execute("DELETE FROM products WHERE id = ? AND user_id = ?", (product_id, user["id"]))
    log_activity(conn, user["id"], "Trash2", f"Deleted product: {existing['name']}", "inventory", "text-rose-500")
    conn.commit()
    conn.close()
    return {"status": "success", "deleted_id": product_id}


@app.post("/api/inventory/{product_id}/restock")
def restock_product(product_id: int, quantity: int = Query(default=50, ge=1), user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ? AND user_id = ?", (product_id, user["id"]))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")

    row = dict(existing)
    new_stock = row["stock"] + quantity
    new_status = "In Stock" if new_stock > row["reorder"] else ("Low Stock" if new_stock > row["reorder"] * 0.3 else "Critical")

    cursor.execute("UPDATE products SET stock = ?, status = ? WHERE id = ? AND user_id = ?", (new_stock, new_status, product_id, user["id"]))
    log_activity(conn, user["id"], "RefreshCw", f"Restocked {quantity} units for {row['name']} (new stock: {new_stock})", "inventory", "text-teal-500")
    conn.commit()
    cursor.execute("SELECT * FROM products WHERE id = ? AND user_id = ?", (product_id, user["id"]))
    updated = dict(cursor.fetchone())
    conn.close()
    return updated


@app.post("/api/inventory/{product_id}/forecast")
def forecast_product_demand_by_id(product_id: int, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ? AND user_id = ?", (product_id, user["id"]))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")

    p = dict(row)
    daily_demand = float(p.get("avg_daily_demand") or 0.0)
    stock = int(p.get("stock") or 0)

    # Handle insufficient historical sales velocity
    if daily_demand <= 0 and stock <= 0:
        conn.close()
        return {
            "product_id": product_id,
            "name": p["name"],
            "has_prediction": False,
            "message": "Not enough data for prediction (no sales velocity recorded for this product)",
            "stockout_risk": "UNKNOWN",
            "predicted_demand_7_days": None,
            "predicted_demand_30_days": None,
            "recommended_reorder": 0,
            "recommendation": "Record catalog sales to calibrate product turnover and demand forecasting.",
            "model_metrics": inventory_bundle.get("metrics")
        }

    model = inventory_bundle["model"]
    features = inventory_bundle["features"]
    input_data = pd.DataFrame(
        [[
            max(0.1, daily_demand),
            float(p.get("trend_factor") or 0.05),
            float(p.get("promotion_factor") or 0.0)
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
        "has_prediction": True,
        "current_stock": current_stock,
        "reorder_level": reorder_level,
        "predicted_demand_7_days": pred_7,
        "predicted_demand_30_days": round(pred_30, 1),
        "stockout_risk": risk,
        "recommended_reorder": reorder_qty,
        "recommendation": rec,
        "model_metrics": inventory_bundle.get("metrics")
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
# 4. INVOICES APIS (MULTI-TENANT & ATOMIC STOCK DEDUCTION)
# ============================================================

@app.get("/api/invoices")
def get_invoices(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices WHERE user_id = ? ORDER BY issued DESC, id DESC", (user["id"],))
    rows = [dict(r) for r in cursor.fetchall()]

    for row in rows:
        cursor.execute("SELECT * FROM invoice_items WHERE invoice_id = ? AND user_id = ?", (row["id"], user["id"]))
        row["line_items"] = [dict(item) for item in cursor.fetchall()]

    conn.close()
    return rows


@app.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: str, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices WHERE id = ? AND user_id = ?", (invoice_id, user["id"]))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Invoice not found")

    inv_data = dict(row)
    cursor.execute("SELECT * FROM invoice_items WHERE invoice_id = ? AND user_id = ?", (invoice_id, user["id"]))
    inv_data["line_items"] = [dict(item) for item in cursor.fetchall()]
    conn.close()
    return inv_data


def generate_invoice_pdf_bytes(inv: dict, line_items: list, customer: dict = None) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595.3, height=841.9)  # Standard A4 (points)

    PRIMARY = (0.20, 0.28, 0.60)       # Indigo
    DARK_TEXT = (0.09, 0.12, 0.18)     # Slate 900
    MUTED_TEXT = (0.45, 0.50, 0.58)    # Slate 500
    BORDER_COLOR = (0.88, 0.90, 0.94)  # Slate 200
    BG_LIGHT = (0.97, 0.98, 1.00)      # Soft Indigo tint

    # 1. Top Decorative Brand Banner
    page.draw_rect(pymupdf.Rect(40, 40, 555.3, 115), color=None, fill=BG_LIGHT)
    page.draw_line(pymupdf.Point(40, 115), pymupdf.Point(555.3, 115), color=PRIMARY, width=2.0)

    # Brand / Company
    page.insert_text((55, 68), "AI BUSINESS OPERATIONS COPILOT", fontsize=15, fontname="hebo", color=PRIMARY)
    page.insert_text((55, 84), "Enterprise Cloud, AI & Business Automation Suite", fontsize=9, fontname="helv", color=MUTED_TEXT)
    page.insert_text((55, 98), "GSTIN: 06AAACB1234D1Z9  |  billing@bizops.in  |  Tel: +91 124 456 7890", fontsize=8, fontname="helv", color=MUTED_TEXT)

    # Invoice Title & ID
    page.insert_text((410, 68), "TAX INVOICE", fontsize=16, fontname="hebo", color=PRIMARY)
    page.insert_text((410, 84), f"Invoice #: {inv.get('id', 'N/A')}", fontsize=10, fontname="hebo", color=DARK_TEXT)

    # Status Badge
    raw_status = (inv.get("status") or "PENDING").upper()
    status_color = (0.05, 0.55, 0.35) if raw_status == "PAID" else (0.85, 0.45, 0.05) if raw_status == "PENDING" else (0.85, 0.15, 0.20)
    page.draw_rect(pymupdf.Rect(410, 90, 480, 106), color=status_color, fill=None, width=1.0)
    page.insert_text((420, 102), raw_status, fontsize=8, fontname="hebo", color=status_color)

    # 2. Details Section (Billed To & Meta)
    page.insert_text((55, 140), "BILLED TO (CUSTOMER)", fontsize=9, fontname="hebo", color=MUTED_TEXT)
    client_name = inv.get("client") or "Valued Customer"
    page.insert_text((55, 156), client_name, fontsize=12, fontname="hebo", color=DARK_TEXT)

    curr_y = 172
    if customer:
        if customer.get("company") and customer.get("company") != client_name:
            page.insert_text((55, curr_y), str(customer.get("company")), fontsize=9, fontname="helv", color=MUTED_TEXT)
            curr_y += 14
        if customer.get("email"):
            page.insert_text((55, curr_y), f"Email: {customer.get('email')}", fontsize=9, fontname="helv", color=MUTED_TEXT)
            curr_y += 14
        if customer.get("phone"):
            page.insert_text((55, curr_y), f"Phone: {customer.get('phone')}", fontsize=9, fontname="helv", color=MUTED_TEXT)
            curr_y += 14

    # Meta Details (Right)
    page.insert_text((370, 140), "INVOICE DETAILS", fontsize=9, fontname="hebo", color=MUTED_TEXT)
    page.insert_text((370, 156), f"Issue Date:  {inv.get('issued') or 'N/A'}", fontsize=9, fontname="helv", color=DARK_TEXT)
    page.insert_text((370, 170), f"Due Date:    {inv.get('due') or 'N/A'}", fontsize=9, fontname="helv", color=DARK_TEXT)
    page.insert_text((370, 184), "Currency:    INR (Indian Rupees)", fontsize=9, fontname="helv", color=DARK_TEXT)

    # 3. Line Items Table
    table_top = max(215, curr_y + 20)
    page.draw_rect(pymupdf.Rect(40, table_top, 555.3, table_top + 24), color=None, fill=(0.94, 0.95, 0.98))
    page.draw_line(pymupdf.Point(40, table_top + 24), pymupdf.Point(555.3, table_top + 24), color=PRIMARY, width=1.0)

    page.insert_text((55, table_top + 16), "#", fontsize=9, fontname="hebo", color=PRIMARY)
    page.insert_text((85, table_top + 16), "ITEM DESCRIPTION", fontsize=9, fontname="hebo", color=PRIMARY)
    page.insert_text((330, table_top + 16), "QTY", fontsize=9, fontname="hebo", color=PRIMARY)
    page.insert_text((385, table_top + 16), "UNIT PRICE (INR)", fontsize=9, fontname="hebo", color=PRIMARY)
    page.insert_text((475, table_top + 16), "TOTAL (INR)", fontsize=9, fontname="hebo", color=PRIMARY)

    row_y = table_top + 24
    items_to_render = line_items if line_items else [
        {"product_name": inv.get("items") or "Business Operations Services", "quantity": 1, "unit_price": inv.get("amount_num") or 0.0, "line_total": inv.get("amount_num") or 0.0}
    ]

    for idx, item in enumerate(items_to_render, start=1):
        bg = (0.99, 0.99, 1.0) if idx % 2 == 0 else (1.0, 1.0, 1.0)
        page.draw_rect(pymupdf.Rect(40, row_y, 555.3, row_y + 24), color=None, fill=bg)
        page.draw_line(pymupdf.Point(40, row_y + 24), pymupdf.Point(555.3, row_y + 24), color=BORDER_COLOR, width=0.5)

        name = str(item.get("product_name") or "Product/Service")[:38]
        qty = str(item.get("quantity") or 1)
        unit = float(item.get("unit_price") or 0.0)
        tot = float(item.get("line_total") or (unit * float(qty)))

        page.insert_text((55, row_y + 16), str(idx), fontsize=9, fontname="helv", color=MUTED_TEXT)
        page.insert_text((85, row_y + 16), name, fontsize=9, fontname="helv", color=DARK_TEXT)
        page.insert_text((335, row_y + 16), qty, fontsize=9, fontname="helv", color=DARK_TEXT)
        page.insert_text((385, row_y + 16), f"INR {unit:,.2f}", fontsize=9, fontname="helv", color=DARK_TEXT)
        page.insert_text((475, row_y + 16), f"INR {tot:,.2f}", fontsize=9, fontname="hebo", color=DARK_TEXT)

        row_y += 24

    # 4. Totals Box
    totals_top = row_y + 20
    box_left = 330
    box_right = 555.3

    subtotal = float(inv.get("subtotal") or 0.0)
    if subtotal <= 0:
        subtotal = sum(float(it.get("line_total") or 0.0) for it in items_to_render)
    if subtotal <= 0:
        subtotal = float(inv.get("amount_num") or 0.0)

    tax_rate = float(inv.get("tax") or 18.0)
    tax_val = round(subtotal * (tax_rate / 100.0), 2)
    discount_val = float(inv.get("discount") or 0.0)
    grand_total = float(inv.get("amount_num") or (subtotal + tax_val - discount_val))

    page.draw_rect(pymupdf.Rect(box_left, totals_top, box_right, totals_top + 80), color=BORDER_COLOR, fill=(0.98, 0.99, 1.0))
    page.insert_text((box_left + 15, totals_top + 18), "Subtotal:", fontsize=9, fontname="helv", color=MUTED_TEXT)
    page.insert_text((box_right - 105, totals_top + 18), f"INR {subtotal:,.2f}", fontsize=9, fontname="helv", color=DARK_TEXT)

    page.insert_text((box_left + 15, totals_top + 34), f"GST / Tax ({tax_rate:.0f}%):", fontsize=9, fontname="helv", color=MUTED_TEXT)
    page.insert_text((box_right - 105, totals_top + 34), f"+ INR {tax_val:,.2f}", fontsize=9, fontname="helv", color=DARK_TEXT)

    if discount_val > 0:
        page.insert_text((box_left + 15, totals_top + 50), "Discount:", fontsize=9, fontname="helv", color=(0.85, 0.2, 0.2))
        page.insert_text((box_right - 105, totals_top + 50), f"- INR {discount_val:,.2f}", fontsize=9, fontname="helv", color=(0.85, 0.2, 0.2))

    page.draw_line(pymupdf.Point(box_left, totals_top + 56), pymupdf.Point(box_right, totals_top + 56), color=BORDER_COLOR, width=1.0)
    page.insert_text((box_left + 15, totals_top + 73), "Grand Total:", fontsize=11, fontname="hebo", color=PRIMARY)
    page.insert_text((box_right - 115, totals_top + 73), f"INR {grand_total:,.2f}", fontsize=11, fontname="hebo", color=PRIMARY)

    # 5. Terms & Footer
    page.draw_line(pymupdf.Point(40, 770), pymupdf.Point(555.3, 770), color=BORDER_COLOR, width=0.5)
    page.insert_text((55, 785), "Payment Terms: Due within 30 days of issue date. Remit via NEFT/RTGS to HDFC Bank A/c 50200012345678 (IFSC: HDFC0001234).", fontsize=7.5, fontname="helv", color=MUTED_TEXT)
    page.insert_text((55, 798), "Notice: This is a computer-generated tax invoice and requires no physical signature.", fontsize=7.5, fontname="helv", color=MUTED_TEXT)
    page.insert_text((55, 811), "Generated by AI Business Operations Copilot  |  Official Document", fontsize=7.5, fontname="helv", color=MUTED_TEXT)

    return doc.tobytes()


@app.get("/api/invoices/{invoice_id}/pdf")
def get_invoice_pdf(invoice_id: str, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices WHERE id = ? AND user_id = ?", (invoice_id, user["id"]))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Invoice not found or access denied")

    inv_data = dict(row)
    cursor.execute("SELECT * FROM invoice_items WHERE invoice_id = ? AND user_id = ?", (invoice_id, user["id"]))
    line_items = [dict(it) for it in cursor.fetchall()]

    cursor.execute("SELECT * FROM customers WHERE name = ? AND user_id = ?", (inv_data.get("client"), user["id"]))
    cust_row = cursor.fetchone()
    customer = dict(cust_row) if cust_row else None
    conn.close()

    try:
        pdf_bytes = generate_invoice_pdf_bytes(inv_data, line_items, customer)
    except Exception as e:
        logger.error("PDF generation failed for invoice %s: %s", invoice_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate invoice PDF document.")

    clean_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', invoice_id)
    filename = f"Invoice_{clean_id}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf"
        }
    )


@app.get("/api/search")
def global_search(q: str = Query(default="", min_length=0), user: dict = Depends(get_authenticated_user)):
    clean_q = q.strip()
    if not clean_q or len(clean_q) < 1:
        return {"query": "", "total": 0, "results": {"customers": [], "products": [], "invoices": [], "employees": []}}

    term = f"%{clean_q}%"
    conn = get_db()
    cursor = conn.cursor()

    # 1. Customers
    cursor.execute("""
        SELECT id, name, email, company, status, ltv, total_spend, orders, churn
        FROM customers
        WHERE user_id = ? AND (name LIKE ? OR email LIKE ? OR company LIKE ? OR status LIKE ?)
        LIMIT 10
    """, (user["id"], term, term, term, term))
    customers = [dict(r) for r in cursor.fetchall()]

    # 2. Products
    cursor.execute("""
        SELECT id, name, sku, category, stock, price, reorder
        FROM products
        WHERE user_id = ? AND (name LIKE ? OR sku LIKE ? OR category LIKE ?)
        LIMIT 10
    """, (user["id"], term, term, term))
    products = [dict(r) for r in cursor.fetchall()]

    # 3. Invoices
    cursor.execute("""
        SELECT id, client, amount, amount_num, due, issued, status, items
        FROM invoices
        WHERE user_id = ? AND (id LIKE ? OR client LIKE ? OR status LIKE ? OR items LIKE ?)
        LIMIT 10
    """, (user["id"], term, term, term, term))
    invoices = [dict(r) for r in cursor.fetchall()]

    # 4. Employees
    cursor.execute("""
        SELECT id, name, role, dept, salary, status
        FROM employees
        WHERE user_id = ? AND (name LIKE ? OR role LIKE ? OR dept LIKE ? OR status LIKE ?)
        LIMIT 10
    """, (user["id"], term, term, term, term))
    employees = [dict(r) for r in cursor.fetchall()]

    conn.close()

    total = len(customers) + len(products) + len(invoices) + len(employees)
    return {
        "query": clean_q,
        "total": total,
        "results": {
            "customers": customers,
            "products": products,
            "invoices": invoices,
            "employees": employees
        }
    }


@app.post("/api/invoices")
def create_invoice(inv: InvoiceCreate, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 1. Validate Customer ownership
        clean_client = (inv.client or "").strip()
        if not clean_client:
            raise HTTPException(status_code=400, detail="Customer / Client name is required.")

        cursor.execute("""
        SELECT id, name, company, orders, total_spend
        FROM customers
        WHERE user_id = ? AND (LOWER(name) = LOWER(?) OR LOWER(company) = LOWER(?))
        """, (user["id"], clean_client, clean_client))
        customer = cursor.fetchone()
        if not customer:
            cursor.execute("""
            SELECT id, name, company, orders, total_spend
            FROM customers
            WHERE user_id = ? AND (LOWER(company) LIKE LOWER(?) OR LOWER(name) LIKE LOWER(?))
            """, (user["id"], f"%{clean_client}%", f"%{clean_client}%"))
            customer = cursor.fetchone()
            if not customer:
                raise HTTPException(status_code=400, detail=f"Customer '{clean_client}' does not exist in your customers list.")

        cust_data = dict(customer)

        # 2. Process & Validate Line Items
        processed_items = []
        subtotal = 0.0
        item_descriptions = []

        if inv.line_items and len(inv.line_items) > 0:
            for item in inv.line_items:
                if item.quantity <= 0:
                    raise HTTPException(status_code=400, detail=f"Quantity for product ID {item.product_id} must be greater than 0.")

                cursor.execute("""
                SELECT id, name, price, price_num, stock, reorder
                FROM products
                WHERE id = ? AND user_id = ?
                """, (item.product_id, user["id"]))
                prod = cursor.fetchone()
                if not prod:
                    raise HTTPException(status_code=400, detail=f"Product with ID {item.product_id} does not exist in your inventory.")

                prod_data = dict(prod)
                available_stock = prod_data["stock"]

                if item.quantity > available_stock:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Insufficient stock for '{prod_data['name']}'. Requested {item.quantity}, but only {available_stock} available."
                    )

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

        # 4. Generate Tenant-Isolated Invoice ID
        inv_id = inv.id
        if not inv_id:
            cursor.execute("SELECT id FROM invoices WHERE user_id = ?", (user["id"],))
            existing_ids = [r[0] for r in cursor.fetchall()]
            max_num = 0
            prefix_pattern = f"INV-{user['id']}-"
            for eid in existing_ids:
                if eid.startswith(prefix_pattern):
                    try:
                        num = int(eid.split(prefix_pattern)[1])
                        if num > max_num:
                            max_num = num
                    except (ValueError, IndexError):
                        pass
                elif eid.startswith("INV-2026-") and user["id"] == 1:
                    try:
                        num = int(eid.split("INV-2026-")[1])
                        if num > max_num:
                            max_num = num
                    except (ValueError, IndexError):
                        pass
            inv_id = f"INV-{user['id']}-{max_num + 1:03d}"

        issued_date = inv.issued or datetime.now().strftime("%b %d, %Y")
        due_date = inv.due or (datetime.now() + timedelta(days=30)).strftime("%b %d, %Y")
        formatted_amount = f"₹{grand_total:,.0f}" if grand_total >= 1 else f"₹{grand_total:.2f}"
        items_summary_text = ", ".join(item_descriptions) if item_descriptions else (inv.items or "")

        # 5. Atomic Transaction: Insert Invoice & Line Items, Reduce Stock, Update Customer
        cursor.execute("""
        INSERT INTO invoices (
            id, user_id, client, amount, amount_num, due, issued, status,
            items, subtotal, tax, discount, total
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            inv_id, user["id"], clean_client, formatted_amount, grand_total, due_date, issued_date,
            inv.status or "Pending", items_summary_text, subtotal, tax_pct, discount_amount, grand_total
        ))

        # Insert line items & deduct stock atomically
        for p_item in processed_items:
            cursor.execute("""
            INSERT INTO invoice_items (user_id, invoice_id, product_id, product_name, quantity, unit_price, line_total)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user["id"], inv_id, p_item["product_id"], p_item["product_name"],
                p_item["quantity"], p_item["unit_price"], p_item["line_total"]
            ))

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

            cursor.execute("""
            UPDATE products SET stock = ?, status = ? WHERE id = ? AND user_id = ?
            """, (new_stock, new_status, p_item["product_id"], user["id"]))

            if new_stock <= reorder_val:
                add_notification(
                    conn, user["id"], "inventory",
                    f"Low stock: {p_item['product_name']}",
                    f"Stock reduced to {new_stock} unit(s) after invoice #{inv_id}."
                )

        # Update customer orders and spend
        cursor.execute("""
        UPDATE customers SET
            orders = orders + 1,
            total_spend = total_spend + ?,
            days_since_last_purchase = 0
        WHERE id = ? AND user_id = ?
        """, (grand_total, cust_data["id"], user["id"]))

        # Log business activity
        log_activity(
            conn, user["id"], "DollarSign",
            f"Created invoice #{inv_id} for {clean_client} — {formatted_amount}",
            "invoice", "text-emerald-500"
        )

        conn.commit()

        cursor.execute("SELECT * FROM invoices WHERE id = ? AND user_id = ?", (inv_id, user["id"]))
        created_inv = dict(cursor.fetchone())
        cursor.execute("SELECT * FROM invoice_items WHERE invoice_id = ? AND user_id = ?", (inv_id, user["id"]))
        created_inv["line_items"] = [dict(r) for r in cursor.fetchall()]

        conn.close()
        return created_inv

    except HTTPException:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        raise
    except sqlite3.IntegrityError as ie:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        logger.error("Database integrity error during invoice creation: %s", ie)
        raise HTTPException(status_code=400, detail="Database integrity constraint violation.")
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        logger.error("Invoice creation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create invoice. Please try again.")


@app.patch("/api/invoices/{invoice_id}/status")
def update_invoice_status(invoice_id: str, status_data: InvoiceStatusUpdate, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, client, amount FROM invoices WHERE id = ? AND user_id = ?", (invoice_id, user["id"]))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Invoice not found")

    cursor.execute("UPDATE invoices SET status = ? WHERE id = ? AND user_id = ?", (status_data.status, invoice_id, user["id"]))
    log_activity(conn, user["id"], "FileText", f"Invoice #{invoice_id} status updated to {status_data.status}", "invoice", "text-indigo-500")
    conn.commit()

    cursor.execute("SELECT * FROM invoices WHERE id = ? AND user_id = ?", (invoice_id, user["id"]))
    inv_data = dict(cursor.fetchone())
    cursor.execute("SELECT * FROM invoice_items WHERE invoice_id = ? AND user_id = ?", (invoice_id, user["id"]))
    inv_data["line_items"] = [dict(item) for item in cursor.fetchall()]
    conn.close()
    return inv_data


@app.delete("/api/invoices/{invoice_id}")
def delete_invoice(invoice_id: str, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM invoices WHERE id = ? AND user_id = ?", (invoice_id, user["id"]))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Invoice not found")

    cursor.execute("DELETE FROM invoice_items WHERE invoice_id = ? AND user_id = ?", (invoice_id, user["id"]))
    cursor.execute("DELETE FROM invoices WHERE id = ? AND user_id = ?", (invoice_id, user["id"]))
    log_activity(conn, user["id"], "Trash2", f"Deleted invoice #{invoice_id}", "invoice", "text-rose-500")
    conn.commit()
    conn.close()
    return {"status": "success", "deleted_id": invoice_id}


# ============================================================
# 5. NOTIFICATIONS APIS (MULTI-TENANT)
# ============================================================

@app.get("/api/notifications")
def get_notifications(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        SELECT id, type, title, desc, read, created_at
        FROM notifications
        WHERE user_id = ?
        ORDER BY id DESC LIMIT 50
        """, (user["id"],))
        rows = []
        for r in cursor.fetchall():
            rd = dict(r)
            rd["read"] = bool(rd["read"])
            rows.append(rd)
        return rows
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.post("/api/notifications/read-all")
def mark_all_notifications_read(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE notifications SET read = 1 WHERE user_id = ?", (user["id"],))
        conn.commit()
        return {"status": "success", "message": "All notifications marked as read."}
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.post("/api/notifications/{notif_id}/read")
def mark_notification_read(notif_id: int, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?", (notif_id, user["id"]))
        conn.commit()
        return {"status": "success", "id": notif_id}
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.delete("/api/notifications/{notif_id}")
def delete_notification(notif_id: int, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM notifications WHERE id = ? AND user_id = ?", (notif_id, user["id"]))
        conn.commit()
        return {"status": "success", "deleted_id": notif_id}
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.delete("/api/notifications")
def clear_all_notifications(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM notifications WHERE user_id = ?", (user["id"],))
        conn.commit()
        return {"status": "success", "message": "All notifications cleared."}
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# 6. SALES ANALYTICS & FORECASTING APIS (REAL DB METRICS)
# ============================================================

@app.get("/api/sales/overview")
def get_sales_overview(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()

    # Query user's real invoices
    cursor.execute("""
    SELECT id, issued, amount_num, status
    FROM invoices
    WHERE user_id = ?
    ORDER BY id ASC
    """, (user["id"],))
    invoices = cursor.fetchall()

    # Query user's real expenses
    cursor.execute("""
    SELECT date, amount FROM expenses WHERE user_id = ?
    """, (user["id"],))
    expenses_rows = cursor.fetchall()

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly_rev = {m: 0.0 for m in month_names}
    monthly_exp = {m: 0.0 for m in month_names}

    paid_invoices = [inv for inv in invoices if inv["status"] == "Paid"]
    total_revenue_num = sum(inv["amount_num"] or 0.0 for inv in paid_invoices)
    total_orders_count = len(paid_invoices)
    avg_order_value_num = (total_revenue_num / total_orders_count) if total_orders_count > 0 else 0.0

    # Parse invoice dates robustly
    def parse_inv_date(d_str):
        if not d_str:
            return None
        for fmt in ("%b %d, %Y", "%Y-%m-%d", "%b %d %Y", "%d/%m/%Y", "%m/%d/%Y", "%B %d, %Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(d_str.strip(), fmt)
            except ValueError:
                pass
        return None

    # Track revenue by month
    for inv in invoices:
        if inv["status"] == "Paid":
            dt = parse_inv_date(inv["issued"])
            amt = inv["amount_num"] or 0.0
            if dt:
                m_label = month_names[dt.month - 1]
                monthly_rev[m_label] += amt
            else:
                issued = inv["issued"] or ""
                for m in month_names:
                    if m.lower() in issued.lower():
                        monthly_rev[m] += amt
                        break

    # Track real expenses by month from expenses table
    for exp in expenses_rows:
        dt = parse_inv_date(exp["date"])
        amt = exp["amount"] or 0.0
        if dt:
            m_label = month_names[dt.month - 1]
            monthly_exp[m_label] += amt
        else:
            date_str = exp["date"] or ""
            for m in month_names:
                if m.lower() in date_str.lower():
                    monthly_exp[m] += amt
                    break

    monthly = []
    for m in month_names:
        rev = round(monthly_rev[m], 2)
        exp = round(monthly_exp[m], 2)
        profit = round(rev - exp, 2)
        monthly.append({"month": m, "revenue": rev, "expenses": exp, "profit": profit})

    # Day of week sales from real paid invoices
    daily_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    daily_sales = {d: {"sales": 0.0, "orders": 0} for d in daily_names}
    for inv in paid_invoices:
        dt = parse_inv_date(inv["issued"])
        if dt:
            day_name = daily_names[dt.weekday()]
            daily_sales[day_name]["sales"] += (inv["amount_num"] or 0.0)
            daily_sales[day_name]["orders"] += 1

    daily = [
        {"day": d, "sales": round(daily_sales[d]["sales"], 2), "orders": daily_sales[d]["orders"]}
        for d in daily_names
    ]

    # Daily Sales Heatmap (last 28 calendar days up to today)
    today = datetime.now().date()
    sales_by_date = {}
    orders_by_date = {}
    for inv in paid_invoices:
        dt = parse_inv_date(inv["issued"])
        if dt:
            d_key = dt.date()
            sales_by_date[d_key] = sales_by_date.get(d_key, 0.0) + (inv["amount_num"] or 0.0)
            orders_by_date[d_key] = orders_by_date.get(d_key, 0) + 1

    max_day_sales = max(sales_by_date.values()) if sales_by_date else 0.0
    day_abbrs = ["M", "T", "W", "T", "F", "S", "S"]
    heatmap = []
    for i in range(28):
        day_date = today - timedelta(days=27 - i)
        s = sales_by_date.get(day_date, 0.0)
        o = orders_by_date.get(day_date, 0)
        intensity = round(s / max_day_sales, 2) if max_day_sales > 0 else 0.0
        heatmap.append({
            "date": day_date.strftime("%Y-%m-%d"),
            "day_label": day_abbrs[day_date.weekday()],
            "sales": round(s, 2),
            "orders": o,
            "intensity": intensity
        })

    # Customer growth from user's customers table
    cursor.execute("SELECT joined, COUNT(*) as cnt FROM customers WHERE user_id = ? GROUP BY joined", (user["id"],))
    cust_rows = cursor.fetchall()
    customer_growth = []
    if cust_rows:
        for r in cust_rows:
            customer_growth.append({
                "month": r["joined"] or "Recent",
                "new": r["cnt"],
                "returning": 0
            })

    # Product Performance: aggregated sales by product from invoice_items joined to invoices for this user
    cursor.execute("""
    SELECT ii.product_name, SUM(ii.line_total) as total_val, SUM(ii.quantity) as total_qty
    FROM invoice_items ii
    JOIN invoices i ON ii.invoice_id = i.id
    WHERE i.user_id = ? AND i.status = 'Paid'
    GROUP BY ii.product_name
    ORDER BY total_val DESC
    """, (user["id"],))
    item_rows = cursor.fetchall()
    if not item_rows:
        cursor.execute("""
        SELECT ii.product_name, SUM(ii.line_total) as total_val, SUM(ii.quantity) as total_qty
        FROM invoice_items ii
        JOIN invoices i ON ii.invoice_id = i.id
        WHERE i.user_id = ?
        GROUP BY ii.product_name
        ORDER BY total_val DESC
        """, (user["id"],))
        item_rows = cursor.fetchall()

    palette = ["#4f46e5", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ec4899", "#ef4444"]
    product_categories = []
    total_cat_val = sum(r["total_val"] or 0.0 for r in item_rows)
    for i, r in enumerate(item_rows):
        val = r["total_val"] or 0.0
        pct = round((val / total_cat_val) * 100) if total_cat_val > 0 else 0
        product_categories.append({
            "name": r["product_name"],
            "value": pct,
            "color": palette[i % len(palette)]
        })

    # Growth Percentages: Compared against real comparable previous 30-day period
    period1_start = today - timedelta(days=30)
    period2_start = today - timedelta(days=60)
    p1_rev, p2_rev = 0.0, 0.0
    p1_orders, p2_orders = 0, 0

    for inv in paid_invoices:
        dt = parse_inv_date(inv["issued"])
        if dt:
            inv_d = dt.date()
            if period1_start <= inv_d <= today:
                p1_rev += (inv["amount_num"] or 0.0)
                p1_orders += 1
            elif period2_start <= inv_d < period1_start:
                p2_rev += (inv["amount_num"] or 0.0)
                p2_orders += 1

    if p2_rev > 0:
        rev_pct = round(((p1_rev - p2_rev) / p2_rev) * 100, 1)
        rev_change = f"{'+' if rev_pct >= 0 else ''}{rev_pct}%"
    else:
        rev_change = "Not enough data"

    if p2_orders > 0:
        ord_pct = round(((p1_orders - p2_orders) / p2_orders) * 100, 1)
        ord_change = f"{'+' if ord_pct >= 0 else ''}{ord_pct}%"
    else:
        ord_change = "Not enough data"

    p1_aov = (p1_rev / p1_orders) if p1_orders > 0 else 0.0
    p2_aov = (p2_rev / p2_orders) if p2_orders > 0 else 0.0
    if p2_aov > 0:
        aov_pct = round(((p1_aov - p2_aov) / p2_aov) * 100, 1)
        aov_change = f"{'+' if aov_pct >= 0 else ''}{aov_pct}%"
    else:
        aov_change = "Not enough data"

    # Format KPI displays
    if total_revenue_num >= 10000000:
        fmt_rev = f"₹{(total_revenue_num / 10000000):.2f}Cr"
    elif total_revenue_num >= 100000:
        fmt_rev = f"₹{(total_revenue_num / 100000):.1f}L"
    else:
        fmt_rev = f"₹{total_revenue_num:,.0f}" if total_revenue_num > 0 else "₹0"

    fmt_orders = f"{total_orders_count:,}"
    fmt_aov = f"₹{avg_order_value_num:,.0f}" if avg_order_value_num > 0 else "₹0"

    kpis = {
        "total_revenue": fmt_rev,
        "total_revenue_change": rev_change,
        "total_orders": fmt_orders,
        "total_orders_change": ord_change,
        "avg_order_value": fmt_aov,
        "avg_order_value_change": aov_change,
        "conversion_rate": "Not available",
        "conversion_rate_change": "Not available"
    }

    conn.close()
    return {
        "kpis": kpis,
        "monthly": monthly,
        "daily": daily,
        "heatmap": heatmap,
        "customer_growth": customer_growth,
        "product_categories": product_categories
    }


@app.get("/api/sales/forecast")
def get_sales_forecast(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT issued, amount_num
    FROM invoices
    WHERE user_id = ? AND status = 'Paid'
    ORDER BY issued ASC
    """, (user["id"],))
    rows = cursor.fetchall()
    conn.close()

    # If user has fewer than 3 paid invoices, report honest insufficient historical data
    if len(rows) < 3:
        return {
            "has_forecast": False,
            "message": "Not enough data for prediction (minimum 3 historical sales transactions required).",
            "monthly_forecasts": [],
            "q3_forecast": None,
            "q3_delta": None,
            "q3_confidence": None,
            "annual_target": None,
            "annual_delta": None,
            "annual_confidence": None,
            "model_metrics": sales_bundle.get("metrics")
        }

    # When >= 3 paid invoices exist, execute trained RandomForestRegressor ML model
    amounts = [r["amount_num"] or 0.0 for r in rows]
    total_sales = sum(amounts)
    n = len(amounts)
    avg_ticket = total_sales / max(1, n)

    model = sales_bundle["model"]
    features = sales_bundle["features"]
    sales_metrics = sales_bundle.get("metrics", {})
    r2 = sales_metrics.get("r2_score", 0.95)
    model_confidence = int(round(max(50.0, min(95.0, r2 * 100.0))))

    months = ["Month +1", "Month +2", "Month +3"]
    predictions = []
    prev_rev = amounts[-1] if amounts else avg_ticket

    for idx, month_label in enumerate(months, start=1):
        month_idx = n + idx
        proj_orders = max(10, round(n * 1.5 + idx * 3))
        proj_mkt = round(avg_ticket * proj_orders * 0.08, 2)

        input_data = pd.DataFrame(
            [[month_idx, proj_orders, proj_mkt]],
            columns=features
        )
        pred_rev = max(0.0, float(model.predict(input_data)[0]))

        if prev_rev > 0:
            delta_val = round(((pred_rev - prev_rev) / prev_rev) * 100, 1)
            delta_str = f"{'+' if delta_val >= 0 else ''}{delta_val}%"
        else:
            delta_str = "0%"

        if pred_rev >= 10000000:
            fmt_pred = f"₹{(pred_rev / 10000000):.2f}Cr"
        elif pred_rev >= 100000:
            fmt_pred = f"₹{(pred_rev / 100000):.1f}L"
        else:
            fmt_pred = f"₹{pred_rev:,.0f}"

        predictions.append({
            "month": month_label,
            "predicted_revenue": round(pred_rev, 2),
            "predicted_revenue_formatted": fmt_pred,
            "delta": delta_str,
            "confidence": model_confidence,
            "model": sales_metrics.get("model_type", "RandomForestRegressor")
        })
        prev_rev = pred_rev

    q3_sum = sum(p["predicted_revenue"] for p in predictions)
    q3_fmt = f"₹{(q3_sum / 100000):.1f}L" if q3_sum >= 100000 else f"₹{q3_sum:,.0f}"
    annual_val = q3_sum * 4
    annual_fmt = f"₹{(annual_val / 10000000):.2f}Cr" if annual_val >= 10000000 else f"₹{(annual_val / 100000):.1f}L"

    return {
        "has_forecast": True,
        "message": "",
        "monthly_forecasts": predictions,
        "q3_forecast": q3_fmt,
        "q3_delta": f"+{round((q3_sum / max(1.0, total_sales * 3)) * 100, 1)}%",
        "q3_confidence": model_confidence,
        "annual_target": annual_fmt,
        "annual_delta": "Projected from ML trend",
        "annual_confidence": model_confidence,
        "model_metrics": sales_metrics
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


# Standalone ML Models Evaluation Metrics Endpoint
@app.get("/api/ai/models/metrics")
def get_model_evaluation_metrics(user: dict = Depends(get_authenticated_user)):
    return {
        "status": "success",
        "models": {
            "customer_churn": {
                "name": "Customer Churn Prediction",
                "algorithm": churn_bundle.get("metrics", {}).get("model_type", "RandomForestClassifier(n_estimators=300, max_depth=10)"),
                "features": churn_bundle["features"],
                "metrics": {
                    "accuracy": churn_bundle.get("metrics", {}).get("accuracy"),
                    "precision": churn_bundle.get("metrics", {}).get("precision"),
                    "recall": churn_bundle.get("metrics", {}).get("recall"),
                    "f1_score": churn_bundle.get("metrics", {}).get("f1_score"),
                    "roc_auc": churn_bundle.get("metrics", {}).get("roc_auc"),
                    "test_samples": churn_bundle.get("metrics", {}).get("test_samples"),
                    "train_samples": churn_bundle.get("metrics", {}).get("train_samples")
                },
                "evaluation": "Evaluated on 20% holdout test dataset with stratified sampling"
            },
            "sales_forecasting": {
                "name": "Sales Revenue Forecasting",
                "algorithm": sales_bundle.get("metrics", {}).get("model_type", "RandomForestRegressor(n_estimators=250, max_depth=12)"),
                "features": sales_bundle["features"],
                "metrics": {
                    "mae": sales_bundle.get("metrics", {}).get("mae"),
                    "rmse": sales_bundle.get("metrics", {}).get("rmse"),
                    "r2_score": sales_bundle.get("metrics", {}).get("r2_score"),
                    "test_samples": sales_bundle.get("metrics", {}).get("test_samples"),
                    "train_samples": sales_bundle.get("metrics", {}).get("train_samples")
                },
                "evaluation": "Evaluated on 20% holdout test split against holdout revenue values"
            },
            "inventory_demand": {
                "name": "Inventory Restock Demand Forecasting",
                "algorithm": inventory_bundle.get("metrics", {}).get("model_type", "RandomForestRegressor(n_estimators=300, max_depth=12)"),
                "features": inventory_bundle["features"],
                "metrics": {
                    "mae": inventory_bundle.get("metrics", {}).get("mae"),
                    "rmse": inventory_bundle.get("metrics", {}).get("rmse"),
                    "r2_score": inventory_bundle.get("metrics", {}).get("r2_score"),
                    "test_samples": inventory_bundle.get("metrics", {}).get("test_samples"),
                    "train_samples": inventory_bundle.get("metrics", {}).get("train_samples")
                },
                "evaluation": "Evaluated on 20% holdout test dataset across SKU demand trajectories"
            }
        }
    }


# ============================================================
# 7. AI BUSINESS HEALTH SCORE ENGINE (MULTI-TENANT)
# ============================================================

def compute_business_health(user_id: int, conn=None):
    close_after = False
    if conn is None:
        conn = get_db()
        close_after = True
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM customers WHERE user_id = ?", (user_id,))
    total_customers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM products WHERE user_id = ?", (user_id,))
    total_products = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM invoices WHERE user_id = ?", (user_id,))
    total_invoices = cursor.fetchone()[0]

    if total_customers == 0 and total_products == 0 and total_invoices == 0:
        now_str = datetime.now().strftime("%b %d, %Y, %I:%M %p")
        if close_after:
            conn.close()
        return {
            "status": "success",
            "score": 0,
            "overall_score": 0,
            "health_level": "New Workspace",
            "components": [],
            "components_map": {},
            "component_details": {},
            "weights": {},
            "reasons": [
                {
                    "type": "info",
                    "component": "setup",
                    "text": "Your workspace is ready. Add customers, products, and invoices to compute your Business Health Score."
                }
            ],
            "last_updated": now_str
        }

    # 1. Sales Growth (Weight: 20%)
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(amount_num), 0) FROM invoices WHERE user_id = ? AND status = 'Paid'", (user_id,))
    paid_inv_count, paid_inv_sum = cursor.fetchone()

    growth_rate = 5.0 + min(15.0, paid_inv_count * 1.5) if paid_inv_count > 0 else 0.0
    sales_score = 95 if growth_rate >= 15 else (85 if growth_rate >= 8 else (70 if paid_inv_count > 0 else 40))

    # 2. Profit Margin (Weight: 20%)
    cursor.execute("SELECT SUM(sell * qty), SUM(buy * qty) FROM profit_products WHERE user_id = ?", (user_id,))
    p_row = cursor.fetchone()
    total_rev = p_row[0] or 0.0
    total_cost = p_row[1] or 0.0
    margin_pct = round(((total_rev - total_cost) / total_rev) * 100, 1) if total_rev > 0 else (45.0 if paid_inv_count > 0 else 0.0)
    profit_score = 92 if margin_pct >= 40 else (80 if margin_pct >= 25 else (60 if margin_pct > 0 else 50))

    # 3. Inventory Health (Weight: 15%)
    cursor.execute("SELECT COUNT(*), SUM(CASE WHEN stock <= reorder THEN 1 ELSE 0 END) FROM products WHERE user_id = ?", (user_id,))
    inv_row = cursor.fetchone()
    p_total = inv_row[0] or 0
    low_stock_count = inv_row[1] or 0
    in_stock_count = max(0, p_total - low_stock_count)
    inv_score = 100 if p_total == 0 else max(10, min(100, int((in_stock_count / max(1, p_total)) * 100)))

    # 4. Customer Churn Risk (Weight: 15%)
    cursor.execute("SELECT COUNT(*), SUM(CASE WHEN status = 'At Risk' OR churn >= 50 THEN 1 ELSE 0 END) FROM customers WHERE user_id = ?", (user_id,))
    cust_row = cursor.fetchone()
    c_total = cust_row[0] or 0
    at_risk_count = cust_row[1] or 0
    churn_rate_pct = round((at_risk_count / max(1, c_total)) * 100, 1) if c_total > 0 else 0.0
    churn_score = 100 if c_total == 0 else max(20, min(100, int(100 - churn_rate_pct)))

    # 5. Outstanding Invoices (Weight: 15%)
    cursor.execute("""
    SELECT COUNT(*),
           SUM(CASE WHEN status = 'Paid' THEN 1 ELSE 0 END),
           SUM(CASE WHEN status = 'Overdue' THEN 1 ELSE 0 END),
           COALESCE(SUM(CASE WHEN status = 'Overdue' THEN amount_num ELSE 0 END), 0)
    FROM invoices
    WHERE user_id = ?
    """, (user_id,))
    inv_stats = cursor.fetchone()
    i_total = inv_stats[0] or 0
    paid_count = inv_stats[1] or 0
    overdue_count = inv_stats[2] or 0
    overdue_sum = inv_stats[3] or 0.0

    paid_ratio = (paid_count / i_total) if i_total > 0 else 1.0
    outstanding_score = 100 if i_total == 0 else max(15, min(100, int(paid_ratio * 80 + 20 - (overdue_count * 10))))

    # 6. Employee Performance (Weight: 15%)
    cursor.execute("SELECT AVG(performance), AVG(attendance), COUNT(*) FROM employees WHERE user_id = ?", (user_id,))
    emp_stats = cursor.fetchone()
    avg_performance = emp_stats[0] or 90.0
    avg_attendance = emp_stats[1] or 95.0
    e_total = emp_stats[2] or 0
    emp_score = 90 if e_total == 0 else max(30, min(100, int(round((avg_performance * 0.7) + (avg_attendance * 0.3)))))

    components = [
        {
            "key": "sales_growth",
            "name": "Sales Growth",
            "score": sales_score,
            "weight": 0.20,
            "weight_pct": "20%",
            "metric": f"+{growth_rate:.1f}% MoM" if paid_inv_count > 0 else "0 sales recorded",
            "status": "Strong" if sales_score >= 80 else ("Moderate" if sales_score >= 60 else "Action Needed")
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
            "metric": f"{in_stock_count}/{p_total} in stock" if p_total > 0 else "No catalog items",
            "status": "Good" if inv_score >= 75 else "Low Stock"
        },
        {
            "key": "customer_churn",
            "name": "Customer Churn Risk",
            "score": churn_score,
            "weight": 0.15,
            "weight_pct": "15%",
            "metric": f"{churn_rate_pct:.1f}% churn risk" if c_total > 0 else "0 customers",
            "status": "Low Risk" if churn_score >= 75 else "Elevated Risk"
        },
        {
            "key": "outstanding_invoices",
            "name": "Outstanding Invoices",
            "score": outstanding_score,
            "weight": 0.15,
            "weight_pct": "15%",
            "metric": f"{int(paid_ratio * 100)}% collected" if i_total > 0 else "0 invoices",
            "status": "On Track" if outstanding_score >= 70 else "Action Needed"
        },
        {
            "key": "employee_performance",
            "name": "Employee Performance",
            "score": emp_score,
            "weight": 0.15,
            "weight_pct": "15%",
            "metric": f"{avg_performance:.1f}% rating" if e_total > 0 else "0 staff members",
            "status": "High" if emp_score >= 85 else "Standard"
        }
    ]

    weighted_total = sum(c["score"] * c["weight"] for c in components)
    overall_score = int(round(weighted_total))

    if overall_score >= 88:
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
    if paid_inv_count > 0:
        reasons.append({
            "type": "positive",
            "component": "sales_growth",
            "text": f"Recorded ₹{paid_inv_sum:,.0f} in collected sales revenue across {paid_inv_count} paid invoice(s)."
        })
    else:
        reasons.append({
            "type": "neutral",
            "component": "sales_growth",
            "text": "No completed invoice payments recorded yet. Issue invoices to track sales performance."
        })

    if low_stock_count > 0:
        reasons.append({
            "type": "negative",
            "component": "inventory_health",
            "text": f"{low_stock_count} product(s) are below safety reorder thresholds."
        })
    elif p_total > 0:
        reasons.append({
            "type": "positive",
            "component": "inventory_health",
            "text": "All catalog products maintain adequate inventory buffer levels."
        })

    if overdue_count > 0:
        reasons.append({
            "type": "negative",
            "component": "outstanding_invoices",
            "text": f"{overdue_count} invoice(s) are overdue totaling ₹{overdue_sum:,.0f}."
        })

    comp_dict = {c["key"]: c["score"] for c in components}
    comp_details = {
        c["key"]: {
            "score": c["score"],
            "weight": c["weight"],
            "metric": c["metric"],
            "status": "positive" if c["score"] >= 80 else ("warning" if c["score"] >= 60 else "danger")
        }
        for c in components
    }
    weights_dict = {c["key"]: c["weight"] for c in components}
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
# 8. DASHBOARD & INSIGHTS APIS (MULTI-TENANT & REAL DB VALUES)
# ============================================================

@app.get("/api/business-health")
def get_business_health(user: dict = Depends(get_authenticated_user)):
    return compute_business_health(user["id"])


@app.get("/api/dashboard/stats")
def get_dashboard_stats(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()

    # Active Customers count
    cursor.execute("SELECT COUNT(*) FROM customers WHERE user_id = ? AND status = 'Active'", (user["id"],))
    active_customers = cursor.fetchone()[0]

    # Invoices stats: Pending count
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(amount_num), 0) FROM invoices WHERE user_id = ? AND status = 'Pending'", (user["id"],))
    pending_orders_count, pending_amount = cursor.fetchone()

    # Total Paid Invoices revenue
    cursor.execute("SELECT COALESCE(SUM(amount_num), 0) FROM invoices WHERE user_id = ? AND status = 'Paid'", (user["id"],))
    total_paid_revenue = cursor.fetchone()[0]

    # Invoices for today
    today_str = datetime.now().strftime("%b %d, %Y")
    today_iso = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
    SELECT COALESCE(SUM(amount_num), 0) FROM invoices
    WHERE user_id = ? AND status = 'Paid' AND (issued = ? OR issued = ?)
    """, (user["id"], today_str, today_iso))
    today_revenue_num = cursor.fetchone()[0]

    monthly_rev_num = total_paid_revenue

    # Inventory stats
    cursor.execute("SELECT COUNT(*) FROM products WHERE user_id = ?", (user["id"],))
    total_products = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM products WHERE user_id = ? AND status = 'In Stock'", (user["id"],))
    in_stock_count = cursor.fetchone()[0]

    inventory_health_pct = round((in_stock_count / total_products) * 100) if total_products > 0 else 0

    # Low stock items
    cursor.execute("""
    SELECT * FROM products
    WHERE user_id = ? AND status IN ('Low Stock', 'Critical', 'Out of Stock')
    """, (user["id"],))
    low_stock_products = [dict(r) for r in cursor.fetchall()]

    conn.close()

    health_info = compute_business_health(user["id"])
    overall_health = health_info["overall_score"]

    formatted_today = f"₹{today_revenue_num:,.0f}" if today_revenue_num > 0 else "₹0"
    if monthly_rev_num >= 10000000:
        formatted_monthly = f"₹{(monthly_rev_num / 10000000):.2f}Cr"
    elif monthly_rev_num >= 100000:
        formatted_monthly = f"₹{(monthly_rev_num / 100000):.1f}L"
    else:
        formatted_monthly = f"₹{monthly_rev_num:,.0f}" if monthly_rev_num > 0 else "₹0"

    return {
        "kpis": {
            "today_revenue": formatted_today,
            "today_revenue_change": "0%",
            "monthly_revenue": formatted_monthly,
            "monthly_revenue_change": "0%",
            "active_customers": f"{active_customers:,}",
            "active_customers_change": "0%",
            "pending_orders": f"{pending_orders_count}",
            "pending_orders_change": f"{pending_orders_count} awaiting" if pending_orders_count > 0 else "0",
            "inventory_health": f"{inventory_health_pct}%",
            "inventory_health_change": "Optimal" if inventory_health_pct >= 75 else ("Attention needed" if total_products > 0 else "No products"),
            "business_health": f"{overall_health}/100",
            "business_health_change": f"{health_info['health_level']}"
        },
        "low_stock_alerts": low_stock_products
    }


@app.get("/api/dashboard/insights")
def get_dashboard_insights(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM customers WHERE user_id = ? AND churn >= 50", (user["id"],))
    high_churn_count = cursor.fetchone()[0]

    cursor.execute("SELECT name, stock, reorder FROM products WHERE user_id = ? AND status IN ('Critical', 'Out of Stock') LIMIT 1", (user["id"],))
    crit_prod = cursor.fetchone()

    cursor.execute("SELECT COUNT(*), COALESCE(SUM(amount_num), 0) FROM invoices WHERE user_id = ? AND status = 'Pending'", (user["id"],))
    pending_count, pending_sum = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM customers WHERE user_id = ?", (user["id"],))
    total_cust = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM products WHERE user_id = ?", (user["id"],))
    total_prod = cursor.fetchone()[0]

    conn.close()

    insights = []
    if total_cust == 0 and total_prod == 0:
        insights.append({
            "text": "Welcome to your Business Operations Copilot! Add your initial catalog products and customers to generate AI insights.",
            "type": "info"
        })
        insights.append({
            "text": "Your workspace is fully isolated. All customer intelligence, inventory, and invoices are strictly private to your account.",
            "type": "positive"
        })
        return insights

    if high_churn_count > 0:
        insights.append({
            "text": f"{high_churn_count} customer account(s) show elevated churn probability. Customer Success outreach is recommended.",
            "type": "warning"
        })
    else:
        insights.append({
            "text": "Customer retention indicators are healthy with minimal churn risk detected.",
            "type": "positive"
        })

    if crit_prod:
        insights.append({
            "text": f"'{crit_prod[0]}' is low on stock ({crit_prod[1]} units remaining). Emergency restock recommended.",
            "type": "danger"
        })

    if pending_count > 0:
        insights.append({
            "text": f"{pending_count} pending invoice(s) totaling ₹{pending_sum:,.0f} scheduled for collection.",
            "type": "info"
        })

    return insights


@app.get("/api/dashboard/activity")
def get_dashboard_activity(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT icon, text, category, color, created_at
    FROM business_activities
    WHERE user_id = ?
    ORDER BY id DESC LIMIT 10
    """, (user["id"],))
    rows = cursor.fetchall()
    conn.close()

    def format_relative_time(created_str: str) -> str:
        try:
            dt = datetime.strptime(created_str, "%Y-%m-%d %H:%M:%S")
            diff = datetime.now() - dt
            seconds = int(diff.total_seconds())
            if seconds < 60:
                return "Just now"
            elif seconds < 3600:
                return f"{seconds // 60} min ago"
            elif seconds < 86400:
                return f"{seconds // 3600} hr ago"
            else:
                return f"{diff.days}d ago"
        except Exception:
            return "Recently"

    activities = []
    for r in rows:
        activities.append({
            "icon": r["icon"] or "Activity",
            "text": r["text"],
            "time": format_relative_time(r["created_at"]),
            "color": r["color"] or "text-indigo-500"
        })

    return activities


# ============================================================
# 9. AI COPILOT INTERACTIVE CHAT API (DATABASE-AWARE)
# ============================================================

@app.post("/api/copilot/chat")
def copilot_chat(req: CopilotChatRequest, user: dict = Depends(get_authenticated_user)):
    query = req.message.lower().strip()
    conn = get_db()
    cursor = conn.cursor()

    if any(w in query for w in ["revenue", "sales", "today", "income", "money"]):
        cursor.execute("SELECT COALESCE(SUM(amount_num), 0) FROM invoices WHERE user_id = ? AND status = 'Paid'", (user["id"],))
        paid_rev = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM invoices WHERE user_id = ?", (user["id"],))
        total_inv = cursor.fetchone()[0]

        if total_inv == 0:
            response_text = (
                f"You do not have any invoices recorded in your workspace yet.\n\n"
                f"To start tracking revenue, navigate to **Invoices** and click **New Invoice**."
            )
            chart = False
        else:
            response_text = (
                f"Here is your revenue summary from your live database:\n\n"
                f"- **Total Collected Revenue:** ₹{paid_rev:,.0f}\n"
                f"- **Total Invoices Issued:** {total_inv}\n\n"
                f"You can view detailed monthly breakdowns and seasonal projections on the **Sales Analytics** page."
            )
            chart = True

    elif any(w in query for w in ["churn", "at risk", "retention", "customer"]):
        cursor.execute("SELECT name, company, churn, ltv FROM customers WHERE user_id = ? AND churn >= 40 ORDER BY churn DESC", (user["id"],))
        risky = cursor.fetchall()
        if not risky:
            cursor.execute("SELECT COUNT(*) FROM customers WHERE user_id = ?", (user["id"],))
            total_cust = cursor.fetchone()[0]
            if total_cust == 0:
                response_text = "You currently have 0 customers registered. Add customers from the **Customers** page to track churn."
            else:
                response_text = "Great news! None of your customers show high churn risk (>40%) right now."
        else:
            list_str = "\n".join([f"- **{r['name']}** ({r['company']}): **{r['churn']}% churn risk**" for r in risky])
            response_text = (
                f"The AI Churn Prediction model identified the following accounts requiring attention:\n\n"
                f"{list_str}\n\n"
                f"**Recommendation:** Schedule a proactive satisfaction check-in and consider extending a contract incentive."
            )
        chart = False

    elif any(w in query for w in ["inventory", "stock", "reorder", "product"]):
        cursor.execute("SELECT name, stock, reorder, status FROM products WHERE user_id = ? AND status IN ('Critical', 'Low Stock', 'Out of Stock')", (user["id"],))
        low_items = cursor.fetchall()
        if not low_items:
            cursor.execute("SELECT COUNT(*) FROM products WHERE user_id = ?", (user["id"],))
            p_cnt = cursor.fetchone()[0]
            if p_cnt == 0:
                response_text = "Your inventory catalog is currently empty. Add products from the **Inventory** page."
            else:
                response_text = "All catalog products currently maintain healthy inventory levels above their reorder points."
        else:
            items_str = "\n".join([f"- **{r['name']}**: {r['stock']} units left (Reorder: {r['reorder']}) — *{r['status']}*" for r in low_items])
            response_text = (
                f"Here is your current restock priority based on inventory demand analysis:\n\n"
                f"{items_str}\n\n"
                f"**Recommended Action:** Create restock orders for items near or below their threshold."
            )
        chart = False

    elif any(w in query for w in ["employee", "staff", "team"]):
        cursor.execute("SELECT name, role, dept, performance FROM employees WHERE user_id = ? ORDER BY performance DESC LIMIT 5", (user["id"],))
        top_emps = cursor.fetchall()
        if not top_emps:
            response_text = "You do not have any employees listed in your team directory yet. Add them from the **Employees** page."
        else:
            emp_str = "\n".join([f"- **{r['name']}** ({r['role']}, {r['dept']}): **{r['performance']}%** performance" for r in top_emps])
            response_text = f"Here is the top performing personnel in your team:\n\n{emp_str}"
        chart = False

    else:
        cursor.execute("SELECT COUNT(*) FROM customers WHERE user_id = ?", (user["id"],))
        c_cnt = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM products WHERE user_id = ?", (user["id"],))
        p_cnt = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM invoices WHERE user_id = ?", (user["id"],))
        i_cnt = cursor.fetchone()[0]

        response_text = (
            f"I checked your live business workspace:\n\n"
            f"- **Active Customers:** {c_cnt}\n"
            f"- **Catalog Products:** {p_cnt}\n"
            f"- **Invoices Tracked:** {i_cnt}\n\n"
            f"You can ask me questions about your revenue, inventory restocking, churn analysis, or business health."
        )
        chart = False

    conn.close()
    return {
        "role": "ai",
        "content": response_text,
        "chart": chart
    }


# ============================================================
# 10. REPORTS & PROFIT ANALYZER APIS (MULTI-TENANT)
# ============================================================

@app.get("/api/reports/{report_type}")
def get_report_data(report_type: str, user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()

    if "customer" in report_type.lower():
        cursor.execute("SELECT name, company, ltv, orders, status FROM customers WHERE user_id = ?", (user["id"],))
        cust_rows = [[r[0], r[1], r[2], str(r[3]), r[4]] for r in cursor.fetchall()]
        data = {
            "headers": ["Customer", "Company / Segment", "LTV", "Orders", "Status"],
            "rows": cust_rows,
            "summary": [
                {"label": "Total Customers", "value": str(len(cust_rows))},
                {"label": "Active Customers", "value": str(sum(1 for r in cust_rows if r[4] == "Active"))},
                {"label": "At Risk", "value": str(sum(1 for r in cust_rows if r[4] == "At Risk"))}
            ]
        }
    elif "inventory" in report_type.lower():
        cursor.execute("SELECT name, sku, stock, reorder, status FROM products WHERE user_id = ?", (user["id"],))
        prod_rows = [[r[0], r[1], str(r[2]), str(r[3]), r[4]] for r in cursor.fetchall()]
        data = {
            "headers": ["Product", "SKU", "Stock", "Reorder Level", "Status"],
            "rows": prod_rows,
            "summary": [
                {"label": "Total SKUs", "value": str(len(prod_rows))},
                {"label": "Low Stock / Critical", "value": str(sum(1 for r in prod_rows if r[4] in ["Low Stock", "Critical", "Out of Stock"]))}
            ]
        }
    elif "employee" in report_type.lower():
        cursor.execute("SELECT name, dept, salary, attendance, performance FROM employees WHERE user_id = ?", (user["id"],))
        emp_rows = [[r[0], r[1], r[2], f"{r[3]}%", f"{r[4]}%"] for r in cursor.fetchall()]
        data = {
            "headers": ["Name", "Department", "Salary", "Attendance", "Performance"],
            "rows": emp_rows,
            "summary": [
                {"label": "Total Employees", "value": str(len(emp_rows))}
            ]
        }
    else:
        cursor.execute("SELECT id, client, amount, status, issued FROM invoices WHERE user_id = ?", (user["id"],))
        inv_rows = [[r[0], r[1], r[2], r[3], r[4]] for r in cursor.fetchall()]
        cursor.execute("SELECT COALESCE(SUM(amount_num), 0) FROM invoices WHERE user_id = ? AND status = 'Paid'", (user["id"],))
        paid_sum = cursor.fetchone()[0]
        data = {
            "headers": ["Invoice ID", "Client", "Amount", "Status", "Issued Date"],
            "rows": inv_rows,
            "summary": [
                {"label": "Total Invoices", "value": str(len(inv_rows))},
                {"label": "Collected Revenue", "value": f"₹{paid_sum:,.0f}"}
            ]
        }

    conn.close()
    return data


@app.get("/api/profit/products")
def get_profit_products(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM profit_products WHERE user_id = ? ORDER BY id ASC", (user["id"],))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# ============================================================
# 11. AI ACTION CENTER ENGINE (MULTI-TENANT & DYNAMIC)
# ============================================================

def generate_action_center_items(user_id: int, conn=None):
    close_after = False
    if conn is None:
        conn = get_db()
        close_after = True
    cursor = conn.cursor()

    actions = []

    # 1. Inventory Actions
    cursor.execute("SELECT id, name, sku, stock, reorder, price, status, avg_daily_demand FROM products WHERE user_id = ?", (user_id,))
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
                "why_explanation": "Zero inventory causes fulfillment bottlenecks and prevents sales capture.",
                "entity_id": p_id,
                "entity_type": "product",
                "action_type": "restock",
                "target_page": "inventory",
                "primary_button_label": "Restock Product",
                "secondary_button_label": "View Inventory"
            })
        elif stock <= reorder:
            is_crit = stock <= max(1, reorder // 3)
            prio = "critical" if is_crit else "high"
            actions.append({
                "id": f"inv-low-{p_id}",
                "priority": prio,
                "category": "inventory",
                "title": f"Low Stock: {name} ({stock} remaining)",
                "problem": f"Only {stock} unit(s) remain in stock, below the safe threshold of {reorder} units.",
                "data_metrics": f"Stock: {stock} / Reorder: {reorder}",
                "recommendation": f"Restock {reorder - stock + 10} units to restore safe operational buffers.",
                "why_explanation": "Inventory buffer is low; customer orders may trigger an immediate stockout.",
                "entity_id": p_id,
                "entity_type": "product",
                "action_type": "restock",
                "target_page": "inventory",
                "primary_button_label": "Restock Product",
                "secondary_button_label": "View Inventory"
            })

    # 2. Customer Churn Risk Actions
    cursor.execute("SELECT id, name, company, email, ltv, orders, status, days_since_last_purchase, support_tickets, complaints, churn FROM customers WHERE user_id = ?", (user_id,))
    customers = [dict(r) for r in cursor.fetchall()]
    for c in customers:
        churn_pct = c.get("churn", 0)
        c_status = c.get("status", "Active")
        c_name = c["name"]
        c_comp = c.get("company", "")
        c_id = c["id"]

        if churn_pct >= 60 or c_status == "At Risk":
            actions.append({
                "id": f"cust-churn-{c_id}",
                "priority": "high",
                "category": "customers",
                "title": f"High Churn Risk: {c_name} ({c_comp})",
                "problem": f"Client shows an elevated {churn_pct}% churn probability.",
                "data_metrics": f"Churn Risk: {churn_pct}% | Status: {c_status}",
                "recommendation": "Initiate dedicated outreach and offer a contract renewal incentive.",
                "why_explanation": "Customer satisfaction indicators point to imminent departure without intervention.",
                "entity_id": c_id,
                "entity_type": "customer",
                "action_type": "outreach",
                "target_page": "customers",
                "primary_button_label": "View Customer",
                "secondary_button_label": "Plan Outreach"
            })

    # 3. Invoice & Overdue Actions
    cursor.execute("SELECT id, client, amount, amount_num, due, issued, status FROM invoices WHERE user_id = ?", (user_id,))
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
                "problem": f"Invoice {i_id} for ₹{amt_num:,.0f} is overdue (Due: {due}).",
                "data_metrics": f"Amount: ₹{amt_num:,.0f} | Due: {due}",
                "recommendation": "Send a formal payment reminder to accounts payable.",
                "why_explanation": "Overdue receivables tie up working capital.",
                "entity_id": i_id,
                "entity_type": "invoice",
                "action_type": "reminder",
                "target_page": "invoices",
                "primary_button_label": "View Invoice",
                "secondary_button_label": "Send Reminder"
            })

    # Aliases
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
            a["impact"] = "High Impact" if a.get("priority") in ["critical", "high"] else "Medium Impact"

    prio_weights = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    actions.sort(key=lambda a: prio_weights.get(a["priority"], 99))

    crit_count = sum(1 for a in actions if a["priority"] == "critical")
    high_count = sum(1 for a in actions if a["priority"] == "high")
    med_count = sum(1 for a in actions if a["priority"] == "medium")
    low_count = sum(1 for a in actions if a["priority"] == "low")

    now_str = datetime.now().strftime("%b %d, %Y, %I:%M %p")
    if close_after:
        conn.close()

    return {
        "status": "success",
        "summary": {
            "total": len(actions),
            "critical": crit_count,
            "high": high_count,
            "medium": med_count,
            "low": low_count
        },
        "actions": actions,
        "items": actions,
        "last_analyzed": now_str
    }


@app.get("/api/action-center")
def get_action_center(user: dict = Depends(get_authenticated_user)):
    return generate_action_center_items(user["id"])


# ============================================================
# SPA CLIENT-SIDE FALLBACK ROUTE
# ============================================================

@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"], include_in_schema=False)
def serve_spa_frontend(full_path: str, request: Request):
    clean_path = full_path.lstrip("/")
    # Strictly protect API routes, auth endpoints, health, docs, redoc, and schema from being caught by SPA fallback
    if (
        clean_path.startswith("api/")
        or clean_path == "api"
        or clean_path.startswith("auth/")
        or clean_path == "auth"
        or clean_path == "health"
        or clean_path.startswith("health/")
        or clean_path == "docs"
        or clean_path.startswith("docs/")
        or clean_path == "redoc"
        or clean_path.startswith("redoc/")
        or clean_path == "openapi.json"
        or clean_path.startswith("openapi.json/")
    ):
        raise HTTPException(status_code=404, detail=f"API route not found: /{clean_path}")

    # SPA client-side routing fallback ONLY serves index.html for GET and HEAD requests.
    # Non-GET requests to unmapped endpoints must return HTTP 404, never fallback or 405.
    if request.method not in ("GET", "HEAD"):
        raise HTTPException(status_code=404, detail=f"Route not found: /{clean_path}")

    # Check if a static file directly in dist exists (e.g. favicon.ico, logo.svg)
    if clean_path and DIST_DIR.exists():
        direct_file = DIST_DIR / clean_path
        if direct_file.is_file():
            return FileResponse(str(direct_file))

    # Fallback to SPA index.html for client-side routing
    if DIST_INDEX_FILE.exists():
        return FileResponse(str(DIST_INDEX_FILE))

    raise HTTPException(
        status_code=404,
        detail="Frontend build (dist/index.html) not found. Run 'npm run build' first."
    )


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