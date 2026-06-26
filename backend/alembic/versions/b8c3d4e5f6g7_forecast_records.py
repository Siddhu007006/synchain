"""forecast_records table

Revision ID: b8c3d4e5f6g7
Revises: a7b2c3d4e5f6
Create Date: 2026-06-04
"""

import sqlalchemy as sa
from alembic import op

revision = "b8c3d4e5f6g7"
down_revision = "a7b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "forecast_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "twin_id",
            sa.Integer(),
            sa.ForeignKey("digital_twins.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("product_name", sa.String(), nullable=False, index=True),
        sa.Column("horizon", sa.Integer(), nullable=False),
        sa.Column("forecast_demand", sa.Float(), nullable=False),
        sa.Column("trend_factor", sa.Float(), nullable=False),
        sa.Column("season_factor", sa.Float(), nullable=False),
        sa.Column("supply_risk", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("source_avg_demand", sa.Float(), nullable=False),
        sa.Column("source_trend", sa.String(), nullable=False),
        sa.Column("source_season", sa.String(), nullable=False),
        sa.Column("source_reliability", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), index=True
        ),
    )


def downgrade() -> None:
    op.drop_table("forecast_records")
