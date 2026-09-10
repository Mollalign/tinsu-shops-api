"""add category name lower index

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-09-10 10:00:00.000000

Adds a functional index on lower(categories.name) so that the exact
case-insensitive category lookup in _find_matching_category() can use an
index scan instead of a sequential scan.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d1e2f3a4b5c6"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Functional index: lower(name) for case-insensitive exact match on categories
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_categories_lower_name "
        "ON categories (lower(name));"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_categories_lower_name;")
