"""Add idempotency_key to sales for duplicate checkout protection

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sales") as batch_op:
        batch_op.add_column(
            sa.Column(
                "idempotency_key",
                sa.String(64),
                nullable=True,
            )
        )
        batch_op.create_unique_constraint(
            "uq_sales_idempotency_key", ["idempotency_key"]
        )


def downgrade() -> None:
    with op.batch_alter_table("sales") as batch_op:
        batch_op.drop_constraint("uq_sales_idempotency_key", type_="unique")
        batch_op.drop_column("idempotency_key")
