"""Enforce tenant-safe composite foreign keys and financial record protection

Revision ID: 003_composite_tenant_fks
Revises: 002_alter_customers_churn_to_int
Create Date: 2026-11-24 08:58:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003_composite_tenant_fks'
down_revision: Union[str, None] = '002_alter_customers_churn_to_int'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create unique composite constraints on parent entities to support composite FK references
    op.create_unique_constraint('uq_customers_id_user', 'customers', ['id', 'user_id'])
    op.create_unique_constraint('uq_products_id_user', 'products', ['id', 'user_id'])
    op.create_unique_constraint('uq_invoices_id_user', 'invoices', ['id', 'user_id'])

    # 2. Hardening Invoices -> Customers foreign key
    # Drop existing single-column FK on customer_id
    op.drop_constraint('invoices_ibfk_2', 'invoices', type_='foreignkey')
    # Create composite tenant-safe FK with RESTRICT to prevent accidental customer deletion destroying invoices
    op.create_foreign_key(
        'fk_invoices_customer_tenant',
        'invoices',
        'customers',
        ['customer_id', 'user_id'],
        ['id', 'user_id'],
        ondelete='RESTRICT',
        onupdate='CASCADE'
    )

    # 3. Hardening Invoice Items -> Invoices foreign key
    op.drop_constraint('invoice_items_ibfk_2', 'invoice_items', type_='foreignkey')
    op.create_foreign_key(
        'fk_invoice_items_invoice_tenant',
        'invoice_items',
        'invoices',
        ['invoice_id', 'user_id'],
        ['id', 'user_id'],
        ondelete='CASCADE',
        onupdate='CASCADE'
    )

    # 4. Hardening Invoice Items -> Products foreign key
    op.drop_constraint('invoice_items_ibfk_3', 'invoice_items', type_='foreignkey')
    op.create_foreign_key(
        'fk_invoice_items_product_tenant',
        'invoice_items',
        'products',
        ['product_id', 'user_id'],
        ['id', 'user_id'],
        ondelete='RESTRICT',
        onupdate='CASCADE'
    )


def downgrade() -> None:
    # Revert invoice_items composite FKs
    op.drop_constraint('fk_invoice_items_product_tenant', 'invoice_items', type_='foreignkey')
    op.create_foreign_key('invoice_items_ibfk_3', 'invoice_items', 'products', ['product_id'], ['id'], ondelete='SET NULL')

    op.drop_constraint('fk_invoice_items_invoice_tenant', 'invoice_items', type_='foreignkey')
    op.create_foreign_key('invoice_items_ibfk_2', 'invoice_items', 'invoices', ['invoice_id'], ['id'], ondelete='CASCADE')

    # Revert invoices composite FK
    op.drop_constraint('fk_invoices_customer_tenant', 'invoices', type_='foreignkey')
    op.create_foreign_key('invoices_ibfk_2', 'invoices', 'customers', ['customer_id'], ['id'], ondelete='RESTRICT')

    # Drop unique constraints
    op.drop_constraint('uq_invoices_id_user', 'invoices', type_='unique')
    op.drop_constraint('uq_products_id_user', 'products', type_='unique')
    op.drop_constraint('uq_customers_id_user', 'customers', type_='unique')
