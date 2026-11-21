"""Initial enterprise schema for PostgreSQL

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-21 19:05:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('password', sa.String(length=255), server_default='', nullable=False),
        sa.Column('company', sa.String(length=255), server_default='', nullable=False),
        sa.Column('biz_type', sa.String(length=100), server_default='', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_verified', sa.Boolean(), server_default='true', nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_users_email', 'users', ['email'], unique=True)

    # 2. user_sessions table
    op.create_table(
        'user_sessions',
        sa.Column('token', sa.String(length=128), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_activity', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('csrf_token', sa.String(length=128), server_default='', nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('token')
    )
    op.create_index('idx_user_sessions_user_id', 'user_sessions', ['user_id'])

    # 3. customers table
    op.create_table(
        'customers',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), server_default='', nullable=False),
        sa.Column('company', sa.String(length=255), server_default='', nullable=False),
        sa.Column('status', sa.String(length=50), server_default='Active', nullable=False),
        sa.Column('ltv', sa.String(length=100), server_default='₹0', nullable=False),
        sa.Column('total_spend', sa.Numeric(precision=14, scale=2), server_default='0.00', nullable=False),
        sa.Column('orders', sa.Integer(), server_default='0', nullable=False),
        sa.Column('joined', sa.String(length=50), server_default='', nullable=False),
        sa.Column('churn', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('days_since_last_purchase', sa.Integer(), server_default='0', nullable=False),
        sa.Column('support_tickets', sa.Integer(), server_default='0', nullable=False),
        sa.Column('complaints', sa.Integer(), server_default='0', nullable=False),
        sa.Column('average_order_value', sa.Numeric(precision=14, scale=2), server_default='0.00', nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_customers_user_id', 'customers', ['user_id'])

    # 4. products table (composite unique on user_id, sku)
    op.create_table(
        'products',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('sku', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=100), server_default='General', nullable=False),
        sa.Column('stock', sa.Integer(), server_default='0', nullable=False),
        sa.Column('reorder', sa.Integer(), server_default='0', nullable=False),
        sa.Column('price', sa.String(length=50), server_default='$0.00', nullable=False),
        sa.Column('price_num', sa.Numeric(precision=14, scale=2), server_default='0.00', nullable=False),
        sa.Column('status', sa.String(length=50), server_default='In Stock', nullable=False),
        sa.Column('trend', sa.String(length=50), server_default='Stable', nullable=False),
        sa.Column('avg_daily_demand', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('trend_factor', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('promotion_factor', sa.Float(), server_default='1.0', nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'sku', name='uq_products_user_sku')
    )
    op.create_index('idx_products_user_sku', 'products', ['user_id', 'sku'])
    op.create_index('idx_products_sku', 'products', ['sku'])

    # 5. invoices table (RESTRICT on user_id and customer_id)
    op.create_table(
        'invoices',
        sa.Column('id', sa.String(length=128), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('customer_id', sa.BigInteger(), nullable=True),
        sa.Column('client', sa.String(length=255), nullable=False),
        sa.Column('amount', sa.String(length=50), server_default='$0.00', nullable=False),
        sa.Column('amount_num', sa.Numeric(precision=14, scale=2), server_default='0.00', nullable=False),
        sa.Column('due', sa.String(length=50), server_default='', nullable=False),
        sa.Column('issued', sa.String(length=50), server_default='', nullable=False),
        sa.Column('status', sa.String(length=50), server_default='Pending', nullable=False),
        sa.Column('items', sa.Text(), server_default='[]', nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=14, scale=2), server_default='0.00', nullable=False),
        sa.Column('tax', sa.Numeric(precision=14, scale=2), server_default='0.00', nullable=False),
        sa.Column('discount', sa.Numeric(precision=14, scale=2), server_default='0.00', nullable=False),
        sa.Column('total', sa.Numeric(precision=14, scale=2), server_default='0.00', nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_invoices_user_id', 'invoices', ['user_id'])
    op.create_index('idx_invoices_customer_id', 'invoices', ['customer_id'])

    # 6. invoice_items table (CASCADE invoice, SET NULL product)
    op.create_table(
        'invoice_items',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('invoice_id', sa.String(length=128), nullable=False),
        sa.Column('product_id', sa.BigInteger(), nullable=True),
        sa.Column('product_name', sa.String(length=255), nullable=False),
        sa.Column('quantity', sa.Integer(), server_default='1', nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=14, scale=2), server_default='0.00', nullable=False),
        sa.Column('line_total', sa.Numeric(precision=14, scale=2), server_default='0.00', nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_invoice_items_invoice_id', 'invoice_items', ['invoice_id'])
    op.create_index('idx_invoice_items_user_id', 'invoice_items', ['user_id'])
    op.create_index('idx_invoice_items_product_id', 'invoice_items', ['product_id'])

    # 7. employees table
    op.create_table(
        'employees',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=100), server_default='', nullable=False),
        sa.Column('dept', sa.String(length=100), server_default='General', nullable=False),
        sa.Column('salary', sa.String(length=100), server_default='₹0', nullable=False),
        sa.Column('status', sa.String(length=50), server_default='Active', nullable=False),
        sa.Column('attendance', sa.Float(), server_default='100.0', nullable=False),
        sa.Column('performance', sa.Float(), server_default='5.0', nullable=False),
        sa.Column('joined', sa.String(length=50), server_default='', nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_employees_user_id', 'employees', ['user_id'])

    # 8. business_activities table
    op.create_table(
        'business_activities',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('icon', sa.String(length=100), server_default='Activity', nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=100), server_default='system', nullable=False),
        sa.Column('color', sa.String(length=50), server_default='#4f46e5', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_business_activities_user_id', 'business_activities', ['user_id'])

    # 9. notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('type', sa.String(length=100), server_default='info', nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('desc', sa.Text(), server_default='', nullable=False),
        sa.Column('read', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_notifications_user_id', 'notifications', ['user_id'])

    # 10. profit_products table
    op.create_table(
        'profit_products',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=100), server_default='General', nullable=False),
        sa.Column('buy', sa.Numeric(precision=14, scale=2), server_default='0.00', nullable=False),
        sa.Column('sell', sa.Numeric(precision=14, scale=2), server_default='0.00', nullable=False),
        sa.Column('qty', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_profit_products_user_id', 'profit_products', ['user_id'])

    # 11. expenses table
    op.create_table(
        'expenses',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('category', sa.String(length=100), server_default='Operating', nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), server_default='0.00', nullable=False),
        sa.Column('description', sa.Text(), server_default='', nullable=False),
        sa.Column('date', sa.String(length=50), server_default='', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_expenses_user_id', 'expenses', ['user_id'])

    # 12. legacy_orphans_archive table
    op.create_table(
        'legacy_orphans_archive',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source_table', sa.String(length=100), nullable=False),
        sa.Column('source_id', sa.BigInteger(), nullable=False),
        sa.Column('original_user_id', sa.BigInteger(), nullable=False),
        sa.Column('record_payload', sa.Text(), nullable=False),
        sa.Column('archived_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('archive_reason', sa.Text(), server_default='Historical orphan record from deleted test user account', nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_legacy_orphans_archive_user', 'legacy_orphans_archive', ['original_user_id'])
    op.create_index('idx_legacy_orphans_archive_table', 'legacy_orphans_archive', ['source_table'])


def downgrade() -> None:
    op.drop_table('legacy_orphans_archive')
    op.drop_table('expenses')
    op.drop_table('profit_products')
    op.drop_table('notifications')
    op.drop_table('business_activities')
    op.drop_table('employees')
    op.drop_table('invoice_items')
    op.drop_table('invoices')
    op.drop_table('products')
    op.drop_table('customers')
    op.drop_table('user_sessions')
    op.drop_table('users')
