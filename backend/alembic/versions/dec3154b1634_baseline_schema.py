"""baseline_schema

Revision ID: dec3154b1634
Revises:
Create Date: 2026-06-04 19:32:44.620194

Creates the core simulations and results tables from scratch.
This is the foundation migration — all other migrations depend on it.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dec3154b1634"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create core simulation and result tables."""
    op.create_table(
        "simulations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("product", sa.String(), nullable=False, index=True),
        sa.Column("stock", sa.Float(), nullable=False),
        sa.Column("warehouse", sa.String(), nullable=False),
        sa.Column("demand", sa.Float(), nullable=False),
        sa.Column("supplier_delay", sa.Float(), nullable=False),
        sa.Column(
            "market_trend", sa.String(), server_default="Neutral", nullable=False
        ),
        sa.Column(
            "supply_status", sa.String(), server_default="Medium", nullable=False
        ),
        sa.Column("season", sa.String(), server_default="Normal", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
        ),
    )

    op.create_table(
        "results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "simulation_id",
            sa.Integer(),
            sa.ForeignKey("simulations.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("demand_forecast", sa.Float(), nullable=False),
        sa.Column("recommended_inventory", sa.Float(), nullable=False),
        sa.Column("selected_warehouse", sa.String(), nullable=False),
        sa.Column("route", sa.String(), nullable=False),
        sa.Column("risk", sa.String(), nullable=False),
        sa.Column("strategy", sa.String(), nullable=False),
        sa.Column("agent_breakdown", sa.Text(), nullable=True),
        sa.Column("overall_confidence", sa.Float(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Drop core tables."""
    op.drop_table("results")
    op.drop_table("simulations")
