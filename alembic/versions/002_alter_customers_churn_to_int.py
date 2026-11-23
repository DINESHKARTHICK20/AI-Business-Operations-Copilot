"""Alter customers.churn from Boolean to Integer to preserve churn risk scores

Revision ID: 002_alter_customers_churn_to_int
Revises: 001_initial_schema
Create Date: 2026-11-23 19:55:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_alter_customers_churn_to_int'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safely alter column churn to Integer across MySQL and SQLite
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.alter_column(
            'churn',
            existing_type=sa.Boolean(),
            type_=sa.Integer(),
            existing_server_default=sa.text('0'),
            existing_nullable=False
        )


def downgrade() -> None:
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.alter_column(
            'churn',
            existing_type=sa.Integer(),
            type_=sa.Boolean(),
            existing_server_default=sa.text('0'),
            existing_nullable=False
        )
