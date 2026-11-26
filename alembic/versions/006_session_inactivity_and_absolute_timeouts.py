"""Add session inactivity and absolute timeout fields and indexes to user_sessions

Revision ID: 006_session_timeouts
Revises: 005_concurrency_leases
Create Date: 2026-11-26 10:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '006_session_timeouts'
down_revision: Union[str, None] = '005_concurrency_leases'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('user_sessions')]
    indexes = [idx['name'] for idx in inspector.get_indexes('user_sessions')]

    # 1. Add last_activity_at column if not present
    if 'last_activity_at' not in columns:
        op.add_column(
            'user_sessions',
            sa.Column('last_activity_at', sa.DateTime(), nullable=True)
        )
        # Populate existing sessions with their last_activity or created_at (safe legacy handling)
        op.execute("UPDATE user_sessions SET last_activity_at = COALESCE(last_activity, created_at)")
        # Alter column to be NOT NULL with default
        op.alter_column(
            'user_sessions',
            'last_activity_at',
            existing_type=sa.DateTime(),
            nullable=False,
            server_default=sa.func.now()
        )

    # 2. Add performance & cleanup indexes
    if 'idx_user_sessions_expires_at' not in indexes:
        op.create_index('idx_user_sessions_expires_at', 'user_sessions', ['expires_at'])

    if 'idx_user_sessions_last_activity' not in indexes:
        op.create_index('idx_user_sessions_last_activity', 'user_sessions', ['last_activity'])

    if 'idx_user_sessions_last_activity_at' not in indexes:
        op.create_index('idx_user_sessions_last_activity_at', 'user_sessions', ['last_activity_at'])

    if 'idx_user_sessions_revoked_at' not in indexes:
        op.create_index('idx_user_sessions_revoked_at', 'user_sessions', ['revoked_at'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('user_sessions')]
    indexes = [idx['name'] for idx in inspector.get_indexes('user_sessions')]

    if 'idx_user_sessions_revoked_at' in indexes:
        op.drop_index('idx_user_sessions_revoked_at', table_name='user_sessions')

    if 'idx_user_sessions_last_activity_at' in indexes:
        op.drop_index('idx_user_sessions_last_activity_at', table_name='user_sessions')

    if 'idx_user_sessions_last_activity' in indexes:
        op.drop_index('idx_user_sessions_last_activity', table_name='user_sessions')

    if 'idx_user_sessions_expires_at' in indexes:
        op.drop_index('idx_user_sessions_expires_at', table_name='user_sessions')

    if 'last_activity_at' in columns:
        op.drop_column('user_sessions', 'last_activity_at')
