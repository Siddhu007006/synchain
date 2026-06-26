"""Add suppliers and warehouses tables (V2.5)

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-06-11 12:00:00.000000

Suppliers prefill:
  lead_time_days   → SimulationInput.supplier_delay
  supply_status    → SimulationInput.supply_status

Warehouses prefill:
  warehouse_id     → SimulationInput.warehouse  (W1 | W2 | W3)

Also adds supplier_id and warehouse_id FKs to simulations for traceability.
All FK columns on simulations are nullable — backward compatible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, Sequence[str], None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── suppliers ────────────────────────────────────────────────────────────
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(), nullable=False, index=True),
        # Prefills SimulationInput.supplier_delay
        sa.Column("lead_time_days", sa.Float(), nullable=False, server_default="0"),
        # Prefills SimulationInput.supply_status
        sa.Column(
            "supply_status", sa.String(), nullable=False, server_default="Medium"
        ),
        # Optional reliability context (shown on company page, not yet used in pipeline)
        sa.Column("reliability_pct", sa.Float(), nullable=False, server_default="100"),
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

    # ── warehouses ───────────────────────────────────────────────────────────
    op.create_table(
        "warehouses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(), nullable=False, index=True),
        # Prefills SimulationInput.warehouse — must be W1, W2, or W3
        sa.Column("warehouse_id", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=False, server_default=""),
        sa.Column("capacity", sa.Float(), nullable=False, server_default="10000"),
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

    # ── traceability FKs on simulations ──────────────────────────────────────
    with op.batch_alter_table("simulations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("supplier_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("warehouse_record_id", sa.Integer(), nullable=True)
        )
        batch_op.create_index(
            "ix_simulations_supplier_id", ["supplier_id"], unique=False
        )
        batch_op.create_index(
            "ix_simulations_warehouse_record_id", ["warehouse_record_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_simulations_supplier_id", "suppliers", ["supplier_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_simulations_warehouse_record_id",
            "warehouses",
            ["warehouse_record_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("simulations", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_simulations_warehouse_record_id", type_="foreignkey"
        )
        batch_op.drop_constraint("fk_simulations_supplier_id", type_="foreignkey")
        batch_op.drop_index("ix_simulations_warehouse_record_id")
        batch_op.drop_index("ix_simulations_supplier_id")
        batch_op.drop_column("warehouse_record_id")
        batch_op.drop_column("supplier_id")
    op.drop_table("warehouses")
    op.drop_table("suppliers")
