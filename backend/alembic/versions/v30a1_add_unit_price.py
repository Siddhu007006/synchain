"""Add unit_price to products table (V3.0)

Revision ID: v30a1_add_unit_price
Revises: k1l2m3n4o5p6
Create Date: 2026-06-20
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "v30a1_add_unit_price"
down_revision = "k1l2m3n4o5p6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("unit_price", sa.Float(), nullable=False, server_default="0.0"),
    )


def downgrade() -> None:
    op.drop_column("products", "unit_price")
