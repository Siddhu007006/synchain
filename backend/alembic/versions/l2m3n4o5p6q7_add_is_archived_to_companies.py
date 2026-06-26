"""Add is_archived to companies (safe archive workflow)

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-06-12 00:00:00.000000

Replaces hard-delete with archive workflow.
  is_archived = False  (default) — company is active
  is_archived = True              — company is archived, hidden from listings

All existing companies default to is_archived=False (backward compatible).
The DELETE /companies/{id} endpoint now returns 409 when data exists,
or archives the company when it has no dependent records.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l2m3n4o5p6q7"
down_revision: Union[str, Sequence[str], None] = "v30a1_add_unit_price"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("companies", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.create_index("ix_companies_is_archived", ["is_archived"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("companies", schema=None) as batch_op:
        batch_op.drop_index("ix_companies_is_archived")
        batch_op.drop_column("is_archived")
