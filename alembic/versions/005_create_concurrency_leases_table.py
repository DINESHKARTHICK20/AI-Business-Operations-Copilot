"""Create concurrency_leases table for distributed resource protection and concurrency control

Revision ID: 005_concurrency_leases
Revises: 004_create_rate_limits_table
Create Date: 2026-11-25 20:30:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '005_concurrency_leases'
down_revision: Union[str, None] = '004_create_rate_limits_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    
    if 'concurrency_leases' not in tables:
        op.create_table(
            'concurrency_leases',
            sa.Column('lease_id', sa.String(length=64), nullable=False),
            sa.Column('resource_type', sa.String(length=64), nullable=False),
            sa.Column('user_id', sa.Integer(), server_default='0', nullable=False),
            sa.Column('worker_pid', sa.Integer(), nullable=False),
            sa.Column('worker_host', sa.String(length=128), nullable=False),
            sa.Column('acquired_at', sa.DateTime(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint('lease_id'),
            mysql_engine='InnoDB',
            mysql_charset='utf8mb4',
            mysql_collate='utf8mb4_unicode_ci'
        )
        op.create_index('idx_conc_res_user', 'concurrency_leases', ['resource_type', 'user_id'])
        op.create_index('idx_conc_expires', 'concurrency_leases', ['expires_at'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    
    if 'concurrency_leases' in tables:
        op.drop_index('idx_conc_expires', table_name='concurrency_leases')
        op.drop_index('idx_conc_res_user', table_name='concurrency_leases')
        op.drop_table('concurrency_leases')
