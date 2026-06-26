"""
Audit log SQLAlchemy model (Phase E9).

Records security-relevant and data-mutating actions as immutable events.
Unlike application logs (which may be rotated), audit records are stored
in the database alongside business data, ensuring they survive log
rotation and are queryable via API.

Retention: Auto-archive after 90 days (configurable via settings.audit_archive_days).
Archived records are moved to `audit_logs_archive` table, never deleted.
"""

from datetime import datetime

from database import Base
from sqlalchemy import ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class AuditLog(Base):
    """Immutable audit event record."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    org_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    action: Mapped[str] = mapped_column(index=True)  # e.g., "simulation.create"
    resource_type: Mapped[str] = mapped_column(index=True)  # e.g., "Simulation"
    resource_id: Mapped[str | None] = mapped_column(
        default=None
    )  # ID of affected resource
    details: Mapped[str | None] = mapped_column(Text, default=None)  # JSON extra data
    ip_address: Mapped[str | None] = mapped_column(default=None)
    request_id: Mapped[str | None] = mapped_column(default=None, index=True)

    __table_args__ = (
        Index("ix_audit_org_action", "org_id", "action"),
        Index("ix_audit_org_timestamp", "org_id", "timestamp"),
    )


class AuditLogArchive(Base):
    """Archived audit events (older than retention period). Same schema as AuditLog."""

    __tablename__ = "audit_logs_archive"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(index=True)
    user_id: Mapped[int | None] = mapped_column(default=None)
    org_id: Mapped[int | None] = mapped_column(default=None, index=True)
    action: Mapped[str] = mapped_column()
    resource_type: Mapped[str] = mapped_column()
    resource_id: Mapped[str | None] = mapped_column(default=None)
    details: Mapped[str | None] = mapped_column(Text, default=None)
    ip_address: Mapped[str | None] = mapped_column(default=None)
    request_id: Mapped[str | None] = mapped_column(default=None)
