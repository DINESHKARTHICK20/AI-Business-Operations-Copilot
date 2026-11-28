"""Enforce invoice ID separation, tenant-safe numbering, and atomic sequences (SEC-13)

Revision ID: 007_invoice_id_collision_protection
Revises: 006_session_timeouts
Create Date: 2026-11-28 09:40:00
"""
import re
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '007_invoice_id_protection'
down_revision: Union[str, None] = '006_session_timeouts'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    inspector = sa.inspect(bind)
    inv_columns = [c['name'] for c in inspector.get_columns('invoices')]
    inv_indexes = [i['name'] for i in inspector.get_indexes('invoices')]
    inv_uqs = [u['name'] for u in inspector.get_unique_constraints('invoices')]
    existing_tables = inspector.get_table_names()

    # 1. Add separated business-facing invoice_number, idempotency_key, and created_at to invoices
    if 'invoice_number' not in inv_columns:
        op.add_column('invoices', sa.Column('invoice_number', sa.String(length=128), nullable=True))
    if 'idempotency_key' not in inv_columns:
        op.add_column('invoices', sa.Column('idempotency_key', sa.String(length=128), nullable=True))
    if 'created_at' not in inv_columns:
        op.add_column('invoices', sa.Column('created_at', sa.DateTime(), nullable=True))
        op.execute(sa.text("UPDATE invoices SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
        if dialect_name == 'mysql':
            op.alter_column(
                'invoices',
                'created_at',
                existing_type=sa.DateTime(),
                nullable=False,
                server_default=sa.text('CURRENT_TIMESTAMP')
            )

    # 2. Preserve historical invoice numbers by backfilling invoice_number = id without modifying historical IDs
    op.execute(sa.text("UPDATE invoices SET invoice_number = id WHERE invoice_number IS NULL"))

    # 3. Audit for any conflicting (user_id, invoice_number) pairs before applying unique constraint
    dup_check = bind.execute(sa.text(
        "SELECT user_id, invoice_number, COUNT(*) as cnt "
        "FROM invoices WHERE invoice_number IS NOT NULL "
        "GROUP BY user_id, invoice_number HAVING COUNT(*) > 1"
    )).fetchall()
    if dup_check:
        raise RuntimeError(f"Duplicate (user_id, invoice_number) records found during audit: {dup_check}")

    # 4. Enforce composite per-tenant uniqueness and idempotency constraints
    with op.batch_alter_table('invoices') as batch_op:
        if 'uq_invoices_user_number' not in inv_uqs:
            batch_op.create_unique_constraint('uq_invoices_user_number', ['user_id', 'invoice_number'])
        if 'uq_invoices_user_idempotency' not in inv_uqs:
            batch_op.create_unique_constraint('uq_invoices_user_idempotency', ['user_id', 'idempotency_key'])
        if 'idx_invoices_user_number' not in inv_indexes:
            batch_op.create_index('idx_invoices_user_number', ['user_id', 'invoice_number'])

    # 5. Create concurrency-safe per-tenant sequence table
    if 'invoice_sequences' not in existing_tables:
        if dialect_name == 'mysql':
            op.create_table(
                'invoice_sequences',
                sa.Column('user_id', sa.BigInteger(), nullable=False),
                sa.Column('last_number', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
                sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
                sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_invoice_sequences_user', ondelete='CASCADE'),
                sa.PrimaryKeyConstraint('user_id'),
                mysql_engine='InnoDB',
                mysql_charset='utf8mb4',
                mysql_collate='utf8mb4_unicode_ci'
            )
        else:
            op.create_table(
                'invoice_sequences',
                sa.Column('user_id', sa.BigInteger(), nullable=False),
                sa.Column('last_number', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
                sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
                sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_invoice_sequences_user', ondelete='CASCADE'),
                sa.PrimaryKeyConstraint('user_id')
            )

    # 6. Seed invoice_sequences per tenant from existing invoice numbering history
    existing_rows = bind.execute(sa.text("SELECT user_id, invoice_number FROM invoices")).fetchall()
    existing_seqs = {
        int(r[0]) for r in bind.execute(sa.text("SELECT user_id FROM invoice_sequences")).fetchall()
    }
    user_max = {}
    user_counts = {}
    for row in existing_rows:
        uid = int(row[0])
        num_str = str(row[1] or "")
        user_counts[uid] = user_counts.get(uid, 0) + 1
        m = re.search(r'(\d+)$', num_str.strip())
        if m:
            seq_val = int(m.group(1))
            if seq_val > user_max.get(uid, 0):
                user_max[uid] = seq_val

    for uid, cnt in user_counts.items():
        if uid not in existing_seqs:
            seed_val = max(cnt, user_max.get(uid, 0))
            bind.execute(
                sa.text("INSERT INTO invoice_sequences (user_id, last_number) VALUES (:uid, :seq)"),
                {"uid": uid, "seq": seed_val}
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    inv_columns = [c['name'] for c in inspector.get_columns('invoices')]
    inv_indexes = [i['name'] for i in inspector.get_indexes('invoices')]
    inv_uqs = [u['name'] for u in inspector.get_unique_constraints('invoices')]
    existing_tables = inspector.get_table_names()

    if 'invoice_sequences' in existing_tables:
        op.drop_table('invoice_sequences')

    with op.batch_alter_table('invoices') as batch_op:
        if 'idx_invoices_user_number' in inv_indexes:
            batch_op.drop_index('idx_invoices_user_number')
        if 'uq_invoices_user_idempotency' in inv_uqs:
            batch_op.drop_constraint('uq_invoices_user_idempotency', type_='unique')
        if 'uq_invoices_user_number' in inv_uqs:
            batch_op.drop_constraint('uq_invoices_user_number', type_='unique')
        if 'created_at' in inv_columns:
            batch_op.drop_column('created_at')
        if 'idempotency_key' in inv_columns:
            batch_op.drop_column('idempotency_key')
        if 'invoice_number' in inv_columns:
            batch_op.drop_column('invoice_number')
