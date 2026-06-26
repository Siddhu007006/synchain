"""digital_twin_tables

Revision ID: a7b2c3d4e5f6
Revises: dec3154b1634
Create Date: 2026-06-04 20:00:00.000000

Phase E1: Digital Twin Foundation
Creates 7 new tables + adds twin_id FK to simulations.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "dec3154b1634"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Digital Twin tables and link simulations."""

    # 1. Root twin entity
    op.create_table(
        "digital_twins",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "name", sa.String(), nullable=False, server_default="Default Supply Chain"
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("simulation_count", sa.Integer(), server_default="0"),
    )
    op.create_index("ix_digital_twins_id", "digital_twins", ["id"])

    # 2. Per-product state
    op.create_table(
        "product_states",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "twin_id", sa.Integer(), sa.ForeignKey("digital_twins.id"), nullable=False
        ),
        sa.Column("product_name", sa.String(), nullable=False),
        sa.Column("latest_stock", sa.Float(), server_default="0"),
        sa.Column("latest_demand", sa.Float(), server_default="0"),
        sa.Column("avg_demand", sa.Float(), server_default="0"),
        sa.Column("demand_trend", sa.String(), server_default="Stable"),
        sa.Column("simulation_count", sa.Integer(), server_default="0"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_product_states_id", "product_states", ["id"])
    op.create_index("ix_product_states_twin_id", "product_states", ["twin_id"])
    op.create_index(
        "ix_product_states_product_name", "product_states", ["product_name"]
    )

    # 3. Per-warehouse state
    op.create_table(
        "warehouse_states",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "twin_id", sa.Integer(), sa.ForeignKey("digital_twins.id"), nullable=False
        ),
        sa.Column("warehouse_id", sa.String(), nullable=False),
        sa.Column("times_selected", sa.Integer(), server_default="0"),
        sa.Column("utilization_pct", sa.Float(), server_default="0"),
        sa.Column("selection_rate", sa.Float(), server_default="0"),
        sa.Column("avg_delivery_score", sa.Float(), server_default="0"),
        sa.Column("avg_risk_score", sa.Float(), server_default="0"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_warehouse_states_id", "warehouse_states", ["id"])
    op.create_index("ix_warehouse_states_twin_id", "warehouse_states", ["twin_id"])

    # 4. Aggregate supplier state
    op.create_table(
        "supplier_states",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "twin_id",
            sa.Integer(),
            sa.ForeignKey("digital_twins.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("avg_delay", sa.Float(), server_default="0"),
        sa.Column("max_delay_seen", sa.Float(), server_default="0"),
        sa.Column("reliability_score", sa.Float(), server_default="100"),
        sa.Column("supply_status_mode", sa.String(), server_default="Medium"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_supplier_states_id", "supplier_states", ["id"])
    op.create_index("ix_supplier_states_twin_id", "supplier_states", ["twin_id"])

    # 5. Global market state
    op.create_table(
        "market_states",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "twin_id",
            sa.Integer(),
            sa.ForeignKey("digital_twins.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("trend_mode", sa.String(), server_default="Neutral"),
        sa.Column("season_mode", sa.String(), server_default="Normal"),
        sa.Column("avg_confidence", sa.Float(), server_default="0"),
        sa.Column("avg_risk_score", sa.Float(), server_default="0"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_market_states_id", "market_states", ["id"])
    op.create_index("ix_market_states_twin_id", "market_states", ["twin_id"])

    # 6. State change audit log
    op.create_table(
        "twin_state_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "twin_id", sa.Integer(), sa.ForeignKey("digital_twins.id"), nullable=False
        ),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("field_name", sa.String(), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=False),
        sa.Column("changed_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_twin_state_history_id", "twin_state_history", ["id"])
    op.create_index("ix_twin_state_history_twin_id", "twin_state_history", ["twin_id"])
    op.create_index(
        "ix_twin_state_history_changed_at", "twin_state_history", ["changed_at"]
    )

    # 7. Signal events (schema only — populated in Phase E3)
    op.create_table(
        "signal_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "twin_id", sa.Integer(), sa.ForeignKey("digital_twins.id"), nullable=False
        ),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("signal_type", sa.String(), nullable=False),
        sa.Column("severity", sa.Float(), server_default="0"),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_signal_events_id", "signal_events", ["id"])
    op.create_index("ix_signal_events_twin_id", "signal_events", ["twin_id"])
    op.create_index("ix_signal_events_created_at", "signal_events", ["created_at"])

    # 8. Add optional twin_id FK to existing simulations table
    with op.batch_alter_table("simulations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("twin_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_simulations_twin_id", "digital_twins", ["twin_id"], ["id"]
        )


def downgrade() -> None:
    """Drop Digital Twin tables and remove twin_id from simulations."""

    with op.batch_alter_table("simulations", schema=None) as batch_op:
        batch_op.drop_constraint("fk_simulations_twin_id", type_="foreignkey")
        batch_op.drop_column("twin_id")

    op.drop_table("signal_events")
    op.drop_table("twin_state_history")
    op.drop_table("market_states")
    op.drop_table("supplier_states")
    op.drop_table("warehouse_states")
    op.drop_table("product_states")
    op.drop_table("digital_twins")
