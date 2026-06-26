"""create_import_jobs_table

Revision ID: k1l2m3n4o5p6
Revises: i9j0k1l2m3n4
Create Date: 2026-06-12 22:00:00.000000

V2.6: Import audit trail table.
Tracks CSV import operations for history and debugging.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "k1l2m3n4o5p6"
down_revision: Union[str, Sequence[str], None] = "i9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the import_jobs table."""
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        if "import_jobs" in inspector.get_table_names():
            return
    except Exception:
        pass  # Offline mode: create unconditionally

    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("entity_type", sa.String(), nullable=False, index=True),
        sa.Column("file_name", sa.String(), server_default="", nullable=False),
        sa.Column("rows_processed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_success", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("errors_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), index=True
        ),
    )


def downgrade() -> None:
    """Drop the import_jobs table."""
    op.drop_table("import_jobs")
