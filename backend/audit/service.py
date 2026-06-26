"""
Audit logging service (Phase E9).

Provides:
  - AuditService.log(): Record an audit event
  - AuditService.list_events(): Query audit events (org-scoped)
  - AuditService.archive_old(): Move old events to archive table

Concept:
  Audit logging records security-relevant and data-mutating actions
  as immutable events. The request_id field links audit events to
  structured logs for full request reconstruction.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from audit.models import AuditLog, AuditLogArchive
from logging_config import request_id_var
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

logger = logging.getLogger("synchain.audit")


class AuditService:
    """Service for recording and querying audit events."""

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        action: str,
        resource_type: str,
        resource_id: str | int | None = None,
        user_id: int | None = None,
        org_id: int | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        """
        Record an audit event.

        This is a synchronous write — the event is committed immediately
        so it cannot be lost if the request fails later.

        Args:
            action: Action identifier (e.g., "simulation.create")
            resource_type: Type of affected resource (e.g., "Simulation")
            resource_id: ID of the affected resource
            user_id: Who performed the action
            org_id: Which organization context
            details: Optional JSON-serializable extra data
            ip_address: Client IP address
        """
        entry = AuditLog(
            user_id=user_id,
            org_id=org_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            details=json.dumps(details) if details else None,
            ip_address=ip_address,
            request_id=request_id_var.get(),
        )
        self.db.add(entry)
        self.db.commit()

        logger.info(
            "Audit: %s %s/%s by user=%s org=%s",
            action,
            resource_type,
            resource_id,
            user_id,
            org_id,
        )
        return entry

    def list_events(
        self,
        org_id: int,
        action: str | None = None,
        resource_type: str | None = None,
        user_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLog]:
        """
        Query audit events for an organization.

        All filters are optional. Results are ordered by timestamp descending.
        """
        stmt = select(AuditLog).where(AuditLog.org_id == org_id)

        if action:
            stmt = stmt.where(AuditLog.action == action)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if start_date:
            stmt = stmt.where(AuditLog.timestamp >= start_date)
        if end_date:
            stmt = stmt.where(AuditLog.timestamp <= end_date)

        stmt = stmt.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count_events(self, org_id: int) -> int:
        """Count total audit events for an organization."""
        from sqlalchemy import func

        result = self.db.execute(
            select(func.count(AuditLog.id)).where(AuditLog.org_id == org_id)
        ).scalar()
        return result or 0

    def archive_old(self, retention_days: int = 90) -> int:
        """
        Move audit events older than retention_days to the archive table.

        Returns the number of archived events.

        This is designed to be called periodically (e.g., daily cron)
        to keep the active audit_logs table performant.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

        # Select old events
        old_events = (
            self.db.execute(select(AuditLog).where(AuditLog.timestamp < cutoff))
            .scalars()
            .all()
        )

        if not old_events:
            return 0

        # Copy to archive
        for event in old_events:
            archive_entry = AuditLogArchive(
                id=event.id,
                timestamp=event.timestamp,
                user_id=event.user_id,
                org_id=event.org_id,
                action=event.action,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                details=event.details,
                ip_address=event.ip_address,
                request_id=event.request_id,
            )
            self.db.add(archive_entry)

        # Delete from active table
        count = len(old_events)
        self.db.execute(delete(AuditLog).where(AuditLog.timestamp < cutoff))
        self.db.commit()

        logger.info(
            "Archived %d audit events older than %d days", count, retention_days
        )
        return count
