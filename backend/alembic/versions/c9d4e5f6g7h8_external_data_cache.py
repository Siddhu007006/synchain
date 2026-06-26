"""external_data_cache table

Revision ID: c9d4e5f6g7h8
Revises: b8c3d4e5f6g7
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op

revision = "c9d4e5f6g7h8"
down_revision = "b8c3d4e5f6g7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_data_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(), nullable=False, index=True),
        sa.Column("data_key", sa.String(), nullable=False, index=True),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("fetched_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("external_data_cache")
