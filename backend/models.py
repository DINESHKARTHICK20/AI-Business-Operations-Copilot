"""
SQLAlchemy 2.0 Declarative Models
AI Business Operations Copilot - MySQL Staging & Production Architecture

Configured for MySQL 8.0 (InnoDB, utf8mb4), SQLite local development, and PostgreSQL.
Includes multi-tenant tenant isolation, strict ON DELETE rules for financial records,
and the non-destructive legacy_orphans_archive table.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

MYSQL_TABLE_ARGS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci"
}


# ============================================================
# 1. USERS TABLE (ROOT AUTHENTICATION DIRECTORY)
# ============================================================
class User(Base):
    __tablename__ = "users"
    __table_args__ = (MYSQL_TABLE_ARGS,)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password: Mapped[str] = mapped_column(String(255), default="", server_default="")
    company: Mapped[str] = mapped_column(String(255), default="", server_default="")
    biz_type: Mapped[str] = mapped_column(String(100), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))

    # Relationships
    sessions: Mapped[List["UserSession"]] = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    customers: Mapped[List["Customer"]] = relationship("Customer", back_populates="user", cascade="all, delete-orphan")
    products: Mapped[List["Product"]] = relationship("Product", back_populates="user", cascade="all, delete-orphan")
    invoices: Mapped[List["Invoice"]] = relationship("Invoice", back_populates="user")
    employees: Mapped[List["Employee"]] = relationship("Employee", back_populates="user", cascade="all, delete-orphan")
    activities: Mapped[List["BusinessActivity"]] = relationship("BusinessActivity", back_populates="user", cascade="all, delete-orphan")
    notifications: Mapped[List["Notification"]] = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    profit_products: Mapped[List["ProfitProduct"]] = relationship("ProfitProduct", back_populates="user", cascade="all, delete-orphan")
    expenses: Mapped[List["Expense"]] = relationship("Expense", back_populates="user", cascade="all, delete-orphan")


# ============================================================
# 2. USER SESSIONS (SEC-02 HTTPONLY AUTH)
# ============================================================
class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("idx_user_sessions_expires_at", "expires_at"),
        Index("idx_user_sessions_last_activity", "last_activity"),
        Index("idx_user_sessions_last_activity_at", "last_activity_at"),
        Index("idx_user_sessions_revoked_at", "revoked_at"),
        MYSQL_TABLE_ARGS,
    )

    token: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_activity: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    csrf_token: Mapped[str] = mapped_column(String(128), default="", server_default="")

    user: Mapped["User"] = relationship("User", back_populates="sessions")


# ============================================================
# 3. CUSTOMERS TABLE
# ============================================================
class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_customers_id_user"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), default="", server_default="")
    company: Mapped[str] = mapped_column(String(255), default="", server_default="")
    status: Mapped[str] = mapped_column(String(50), default="Active", server_default="Active")
    ltv: Mapped[str] = mapped_column(String(100), default="₹0", server_default="₹0")
    total_spend: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00"))
    orders: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    joined: Mapped[str] = mapped_column(String(50), default="", server_default="")
    churn: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    days_since_last_purchase: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    support_tickets: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    complaints: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    average_order_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00"))

    user: Mapped["User"] = relationship("User", back_populates="customers")
    invoices: Mapped[List["Invoice"]] = relationship("Invoice", back_populates="customer")


# ============================================================
# 4. PRODUCTS TABLE (MULTI-TENANT COMPOSITE SKU)
# ============================================================
class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("user_id", "sku", name="uq_products_user_sku"),
        UniqueConstraint("id", "user_id", name="uq_products_id_user"),
        Index("idx_products_user_sku", "user_id", "sku"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), default="General", server_default="General")
    stock: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    reorder: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    price: Mapped[str] = mapped_column(String(50), default="$0.00", server_default="$0.00")
    price_num: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00"))
    status: Mapped[str] = mapped_column(String(50), default="In Stock", server_default="In Stock")
    trend: Mapped[str] = mapped_column(String(50), default="Stable", server_default="Stable")
    avg_daily_demand: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))
    trend_factor: Mapped[float] = mapped_column(Float, default=1.0, server_default=text("1.0"))
    promotion_factor: Mapped[float] = mapped_column(Float, default=1.0, server_default=text("1.0"))

    user: Mapped["User"] = relationship("User", back_populates="products")
    invoice_items: Mapped[List["InvoiceItem"]] = relationship("InvoiceItem", back_populates="product")


# ============================================================
# 5. INVOICES TABLE (FINANCIAL RETENTION RESTRICT & COMPOSITE TENANT FK)
# ============================================================
class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_invoices_id_user"),
        UniqueConstraint("user_id", "invoice_number", name="uq_invoices_user_number"),
        UniqueConstraint("user_id", "idempotency_key", name="uq_invoices_user_idempotency"),
        Index("idx_invoices_user_number", "user_id", "invoice_number"),
        ForeignKeyConstraint(
            ["customer_id", "user_id"],
            ["customers.id", "customers.user_id"],
            name="fk_invoices_customer_tenant",
            ondelete="RESTRICT",
            onupdate="CASCADE"
        ),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    # ON DELETE RESTRICT guarantees invoices cannot be deleted via cascading user/customer deletes
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    invoice_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    client: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[str] = mapped_column(String(50), default="$0.00", server_default="$0.00")
    amount_num: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00"))
    due: Mapped[str] = mapped_column(String(50), default="", server_default="")
    issued: Mapped[str] = mapped_column(String(50), default="", server_default="")
    status: Mapped[str] = mapped_column(String(50), default="Pending", server_default="Pending")
    items: Mapped[str] = mapped_column(Text, default="[]")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00"))
    tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00"))
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00"))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="invoices")
    customer: Mapped[Optional["Customer"]] = relationship(
        "Customer",
        back_populates="invoices",
        foreign_keys=[customer_id, user_id],
        primaryjoin="and_(Invoice.customer_id == Customer.id, Invoice.user_id == Customer.user_id)"
    )
    line_items: Mapped[List["InvoiceItem"]] = relationship(
        "InvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        foreign_keys="[InvoiceItem.invoice_id, InvoiceItem.user_id]",
        primaryjoin="and_(Invoice.id == InvoiceItem.invoice_id, Invoice.user_id == InvoiceItem.user_id)"
    )


# ============================================================
# 6. INVOICE ITEMS (IMMUTABLE SNAPSHOT & COMPOSITE TENANT FKS)
# ============================================================
class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["invoice_id", "user_id"],
            ["invoices.id", "invoices.user_id"],
            name="fk_invoice_items_invoice_tenant",
            ondelete="CASCADE",
            onupdate="CASCADE"
        ),
        ForeignKeyConstraint(
            ["product_id", "user_id"],
            ["products.id", "products.user_id"],
            name="fk_invoice_items_product_tenant",
            ondelete="RESTRICT",
            onupdate="CASCADE"
        ),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # SET NULL / RESTRICT preserves line item records when product catalog item is altered
    product_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00"))

    invoice: Mapped["Invoice"] = relationship(
        "Invoice",
        back_populates="line_items",
        foreign_keys=[invoice_id, user_id],
        primaryjoin="and_(InvoiceItem.invoice_id == Invoice.id, InvoiceItem.user_id == Invoice.user_id)"
    )
    product: Mapped[Optional["Product"]] = relationship(
        "Product",
        back_populates="invoice_items",
        foreign_keys=[product_id, user_id],
        primaryjoin="and_(InvoiceItem.product_id == Product.id, InvoiceItem.user_id == Product.user_id)"
    )


# ============================================================
# 6B. INVOICE SEQUENCES (SEC-13 ATOMIC PER-TENANT NUMBERING)
# ============================================================
class InvoiceSequence(Base):
    __tablename__ = "invoice_sequences"
    __table_args__ = (MYSQL_TABLE_ARGS,)

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", name="fk_invoice_sequences_user", ondelete="CASCADE"),
        primary_key=True
    )
    last_number: Mapped[int] = mapped_column(BigInteger, default=0, server_default=text("0"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ============================================================
# 7. EMPLOYEES TABLE
# ============================================================
class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (MYSQL_TABLE_ARGS,)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(100), default="", server_default="")
    dept: Mapped[str] = mapped_column(String(100), default="General", server_default="General")
    salary: Mapped[str] = mapped_column(String(100), default="₹0", server_default="₹0")
    status: Mapped[str] = mapped_column(String(50), default="Active", server_default="Active")
    attendance: Mapped[float] = mapped_column(Float, default=100.0, server_default=text("100.0"))
    performance: Mapped[float] = mapped_column(Float, default=5.0, server_default=text("5.0"))
    joined: Mapped[str] = mapped_column(String(50), default="", server_default="")

    user: Mapped["User"] = relationship("User", back_populates="employees")


# ============================================================
# 8. BUSINESS ACTIVITIES TABLE
# ============================================================
class BusinessActivity(Base):
    __tablename__ = "business_activities"
    __table_args__ = (MYSQL_TABLE_ARGS,)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    icon: Mapped[str] = mapped_column(String(100), default="Activity", server_default="Activity")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="system", server_default="system")
    color: Mapped[str] = mapped_column(String(50), default="#4f46e5", server_default="#4f46e5")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="activities")


# ============================================================
# 9. NOTIFICATIONS TABLE
# ============================================================
class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (MYSQL_TABLE_ARGS,)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(100), default="info", server_default="info")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    desc: Mapped[str] = mapped_column(Text, default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="notifications")


# ============================================================
# 10. PROFIT PRODUCTS TABLE
# ============================================================
class ProfitProduct(Base):
    __tablename__ = "profit_products"
    __table_args__ = (MYSQL_TABLE_ARGS,)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="General", server_default="General")
    buy: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00"))
    sell: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00"))
    qty: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    user: Mapped["User"] = relationship("User", back_populates="profit_products")


# ============================================================
# 11. EXPENSES TABLE
# ============================================================
class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (MYSQL_TABLE_ARGS,)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), default="Operating", server_default="Operating")
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00"))
    description: Mapped[str] = mapped_column(Text, default="")
    date: Mapped[str] = mapped_column(String(50), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="expenses")


# ============================================================
# 12. LEGACY ORPHANS ARCHIVE (STAGING AUDIT TABLE)
# ============================================================
class LegacyOrphansArchive(Base):
    __tablename__ = "legacy_orphans_archive"
    __table_args__ = (MYSQL_TABLE_ARGS,)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_table: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    original_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    record_payload: Mapped[str] = mapped_column(Text, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    archive_reason: Mapped[str] = mapped_column(String(255), default="Historical orphan record from deleted test user account", server_default="Historical orphan record from deleted test user account")


# ============================================================
# 13. RATE LIMITS (SEC-08 PERSISTENT & DISTRIBUTED ENFORCEMENT)
# ============================================================
class RateLimit(Base):
    __tablename__ = "rate_limits"
    __table_args__ = (
        Index("ix_rate_limits_expires_at", "expires_at"),
        MYSQL_TABLE_ARGS,
    )

    rate_key: Mapped[str] = mapped_column(String(191), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    first_attempt_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_attempt_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


# ============================================================
# 14. CONCURRENCY LEASES (SEC-09 DISTRIBUTED RESOURCE PROTECTION)
# ============================================================
class ConcurrencyLease(Base):
    __tablename__ = "concurrency_leases"
    __table_args__ = (
        Index("idx_conc_res_user", "resource_type", "user_id"),
        Index("idx_conc_expires", "expires_at"),
        MYSQL_TABLE_ARGS,
    )

    lease_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    worker_pid: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_host: Mapped[str] = mapped_column(String(128), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


