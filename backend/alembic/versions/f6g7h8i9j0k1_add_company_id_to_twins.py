"""Add company_id to digital_twins (V2.2)

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-06-10 12:00:00.000000

Adds nullable company_id FK to digital_twins so every twin
can optionally belong to a Company. NULL means the twin was
created before V2.2 or outside a company context — both are
valid and continue to work.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6g7h8i9j0k1"
down_revision: Union[str, Sequence[str], None] = "e5f6g7h8i9j0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable company_id column + index to digital_twins."""
    with op.batch_alter_table("digital_twins", schema=None) as batch_op:
        # SQLite batch mode requires explicit constraint names
        batch_op.add_column(
            sa.Column(
                "company_id",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            "fk_digital_twins_company_id",  # explicit name — required for SQLite batch
            "companies",
            ["company_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_digital_twins_company_id",
            ["company_id"],
            unique=False,
        )


def downgrade() -> None:
    """Remove company_id column from digital_twins."""
    with op.batch_alter_table("digital_twins", schema=None) as batch_op:
        batch_op.drop_index("ix_digital_twins_company_id")
        batch_op.drop_constraint("fk_digital_twins_company_id", type_="foreignkey")
        batch_op.drop_column("company_id")
