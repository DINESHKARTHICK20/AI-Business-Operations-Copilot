"""Create rate_limits table for persistent and distributed rate limiting

Revision ID: 004_create_rate_limits_table
Revises: 003_composite_tenant_fks
Create Date: 2026-11-24 09:40:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '004_create_rate_limits_table'
down_revision: Union[str, None] = '003_composite_tenant_fks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'rate_limits',
        sa.Column('rate_key', sa.String(length=191), nullable=False),
        sa.Column('attempts', sa.Integer(), server_default='1', nullable=False),
        sa.Column('first_attempt_at', sa.DateTime(), nullable=False),
        sa.Column('last_attempt_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('rate_key'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    op.create_index('ix_rate_limits_expires_at', 'rate_limits', ['expires_at'])


def downgrade() -> None:
    op.drop_index('ix_rate_limits_expires_at', table_name='rate_limits')
    op.drop_table('rate_limits')
