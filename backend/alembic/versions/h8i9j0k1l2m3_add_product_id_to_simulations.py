"""Add product_id and company_id to simulations (V2.4)

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-06-11 00:00:00.000000

Adds two nullable FK columns to simulations:
  - product_id  → links a simulation back to the Product that prefilled it
  - company_id  → links a simulation to the Company context

Both are nullable — all existing simulations stay valid with NULL values.
The product name string on SimulationInput is still the primary field;
product_id is for traceability (results page, product intelligence page).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, Sequence[str], None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("simulations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("product_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("company_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_simulations_product_id", ["product_id"], unique=False)
        batch_op.create_index(
            "ix_simulations_company_id_v24", ["company_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_simulations_product_id", "products", ["product_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_simulations_company_id", "companies", ["company_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("simulations", schema=None) as batch_op:
        batch_op.drop_constraint("fk_simulations_company_id", type_="foreignkey")
        batch_op.drop_constraint("fk_simulations_product_id", type_="foreignkey")
        batch_op.drop_index("ix_simulations_company_id_v24")
        batch_op.drop_index("ix_simulations_product_id")
        batch_op.drop_column("company_id")
        batch_op.drop_column("product_id")
