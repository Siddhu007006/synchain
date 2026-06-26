"""Add companies table (V2 Phase 1)

Revision ID: e5f6g7h8i9j0
Revises: d4f776eb36ba
Create Date: 2026-06-10 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6g7h8i9j0"
down_revision: Union[str, Sequence[str], None] = "j0k1l2m3n4o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the companies table."""
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True, index=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False, index=True),
        sa.Column("industry", sa.String(), nullable=False, server_default=""),
        sa.Column("country", sa.String(), nullable=False, server_default=""),
        sa.Column(
            "org_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
            server_default="1",
            index=True,
        ),
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
    """Drop the companies table."""
    op.drop_table("companies")
