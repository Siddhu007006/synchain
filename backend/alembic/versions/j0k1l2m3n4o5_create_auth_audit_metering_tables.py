"""create_auth_audit_metering_tables

Revision ID: j0k1l2m3n4o5
Revises: d4f776eb36ba
Create Date: 2026-06-12 21:00:00.000000

Phase E8/E9: Creates auth, audit, and metering tables.
These tables were previously created by Base.metadata.create_all(),
which has been removed in favor of Alembic-only schema management.

Must run BEFORE the companies migration which references organizations.id.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "j0k1l2m3n4o5"
down_revision: Union[str, Sequence[str], None] = "d4f776eb36ba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    """Check if a table already exists (for existing databases).

    Returns False in offline mode (--sql) since there is no real
    connection to inspect — this causes CREATE TABLE statements to
    be emitted unconditionally, which is the correct behavior for
    offline SQL generation.
    """
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        return table_name in inspector.get_table_names()
    except Exception:
        # Offline mode: MockConnection doesn't support inspect()
        return False


def upgrade() -> None:
    """Create auth, audit, and metering tables if they don't exist."""

    # --- Auth tables (Phase E8) ---

    if not _table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("email", sa.String(), nullable=False, unique=True, index=True),
            sa.Column("hashed_password", sa.String(), nullable=False),
            sa.Column("display_name", sa.String(), server_default="", nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
            sa.Column(
                "is_superadmin", sa.Boolean(), server_default="0", nullable=False
            ),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )

    if not _table_exists("organizations"):
        op.create_table(
            "organizations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(), nullable=False, unique=True),
            sa.Column("slug", sa.String(), nullable=False, unique=True, index=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column(
                "created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
        )

    if not _table_exists("memberships"):
        op.create_table(
            "memberships",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "org_id",
                sa.Integer(),
                sa.ForeignKey("organizations.id"),
                nullable=False,
                index=True,
            ),
            sa.Column("role", sa.String(), server_default="member", nullable=False),
            sa.Column("joined_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "org_id", name="uq_user_org"),
        )

    if not _table_exists("api_keys"):
        op.create_table(
            "api_keys",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("key_hash", sa.String(), nullable=False),
            sa.Column("key_prefix", sa.String(), nullable=False, index=True),
            sa.Column("name", sa.String(), server_default="Default", nullable=False),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "org_id",
                sa.Integer(),
                sa.ForeignKey("organizations.id"),
                nullable=False,
                index=True,
            ),
            sa.Column("scopes", sa.Text(), server_default="[]", nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
        )

    # --- Audit tables (Phase E9) ---

    if not _table_exists("audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "timestamp", sa.DateTime(), server_default=sa.func.now(), index=True
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id"),
                nullable=True,
                index=True,
            ),
            sa.Column(
                "org_id",
                sa.Integer(),
                sa.ForeignKey("organizations.id"),
                nullable=True,
                index=True,
            ),
            sa.Column("action", sa.String(), nullable=False, index=True),
            sa.Column("resource_type", sa.String(), nullable=False, index=True),
            sa.Column("resource_id", sa.String(), nullable=True),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("ip_address", sa.String(), nullable=True),
            sa.Column("request_id", sa.String(), nullable=True, index=True),
        )
        op.create_index("ix_audit_org_action", "audit_logs", ["org_id", "action"])
        op.create_index("ix_audit_org_timestamp", "audit_logs", ["org_id", "timestamp"])

    if not _table_exists("audit_logs_archive"):
        op.create_table(
            "audit_logs_archive",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("timestamp", sa.DateTime(), index=True),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("org_id", sa.Integer(), nullable=True, index=True),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("resource_type", sa.String(), nullable=False),
            sa.Column("resource_id", sa.String(), nullable=True),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("ip_address", sa.String(), nullable=True),
            sa.Column("request_id", sa.String(), nullable=True),
        )

    # --- Metering table (Phase E9) ---

    if not _table_exists("usage_events"):
        op.create_table(
            "usage_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "org_id",
                sa.Integer(),
                sa.ForeignKey("organizations.id"),
                nullable=False,
                index=True,
            ),
            sa.Column("event_type", sa.String(), nullable=False, index=True),
            sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
            sa.Column(
                "timestamp", sa.DateTime(), server_default=sa.func.now(), index=True
            ),
            sa.Column("metadata_json", sa.Text(), nullable=True),
        )
        op.create_index("ix_usage_org_type", "usage_events", ["org_id", "event_type"])
        op.create_index(
            "ix_usage_org_timestamp", "usage_events", ["org_id", "timestamp"]
        )


def downgrade() -> None:
    """Drop auth, audit, and metering tables."""
    for table in [
        "usage_events",
        "audit_logs_archive",
        "audit_logs",
        "api_keys",
        "memberships",
        "organizations",
        "users",
    ]:
        if _table_exists(table):
            op.drop_table(table)
