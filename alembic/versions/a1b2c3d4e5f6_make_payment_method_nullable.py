"""Make payment_method nullable on sales (deprecated, no longer part of active workflow)

Revision ID: a1b2c3d4e5f6
Revises: 2e1d8c310fcc
Create Date: 2026-08-21

Safe strategy: make the column nullable and set existing rows to NULL.
This preserves history while removing it from the active API contract.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "a1b2c3d4e5f6"
down_revision = "2e1d8c310fcc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make payment_method nullable — existing rows keep their historical value
    with op.batch_alter_table("sales") as batch_op:
        batch_op.alter_column(
            "payment_method",
            existing_type=sa.String(),
            nullable=True,
        )


def downgrade() -> None:
    # Restore NOT NULL — fill any NULLs with CASH first to avoid constraint violation
    op.execute("UPDATE sales SET payment_method = 'CASH' WHERE payment_method IS NULL")
    with op.batch_alter_table("sales") as batch_op:
        batch_op.alter_column(
            "payment_method",
            existing_type=sa.String(),
            nullable=False,
        )
