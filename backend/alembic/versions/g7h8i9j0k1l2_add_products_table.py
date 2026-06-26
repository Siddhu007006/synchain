"""Add products table (V2.3)

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-06-10 18:00:00.000000

Products are the first piece of business data owned by a Company.
They carry stock and demand figures that will prefill the simulation
form in V2.4 — so this schema is designed with that in mind:
  - current_stock       → prefills SimulationInput.stock
  - avg_monthly_demand  → prefills SimulationInput.demand
  - category            → context label, no logic yet
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, Sequence[str], None] = "f6g7h8i9j0k1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the products table."""
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(), nullable=False, index=True),
        sa.Column("category", sa.String(), nullable=False, server_default=""),
        sa.Column("current_stock", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_monthly_demand", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    """Drop the products table."""
    op.drop_table("products")
