"""
Metering service (Phase E9).

Provides:
  - MeteringService.record(): Fire-and-forget usage event recording
  - MeteringService.get_usage(): Usage summary for an org
  - MeteringService.get_breakdown(): Detailed usage by type and date

Concept:
  Metering is separate from billing. This service only records what
  happened, not what it costs. Billing logic would consume these
  events to compute invoices.
"""

import json
import logging
from datetime import datetime

from metering.models import UsageEvent
from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger("synchain.metering")


class MeteringService:
    """Service for recording and querying usage events."""

    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        org_id: int,
        event_type: str,
        quantity: int = 1,
        metadata: dict | None = None,
    ) -> None:
        """
        Record a usage event. Fire-and-forget — does not raise on failure.

        Args:
            org_id: Organization being metered
            event_type: Type of event (e.g., "simulation.run")
            quantity: Number of units consumed (default: 1)
            metadata: Optional JSON-serializable context
        """
        try:
            event = UsageEvent(
                org_id=org_id,
                event_type=event_type,
                quantity=quantity,
                metadata_json=json.dumps(metadata) if metadata else None,
            )
            self.db.add(event)
            self.db.commit()
        except Exception:
            logger.exception("Failed to record usage event: %s", event_type)
            self.db.rollback()

    def get_usage(
        self,
        org_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict:
        """
        Get usage summary for an organization.

        Returns total events and per-type counts.
        """
        stmt = (
            select(
                UsageEvent.event_type,
                func.sum(UsageEvent.quantity).label("total_quantity"),
                func.count(UsageEvent.id).label("event_count"),
            )
            .where(UsageEvent.org_id == org_id)
            .group_by(UsageEvent.event_type)
        )

        if start:
            stmt = stmt.where(UsageEvent.timestamp >= start)
        if end:
            stmt = stmt.where(UsageEvent.timestamp <= end)

        rows = self.db.execute(stmt).all()

        by_type = {}
        total_events = 0
        total_quantity = 0

        for row in rows:
            by_type[row.event_type] = {
                "event_count": row.event_count,
                "total_quantity": row.total_quantity,
            }
            total_events += row.event_count
            total_quantity += row.total_quantity

        return {
            "org_id": org_id,
            "total_events": total_events,
            "total_quantity": total_quantity,
            "by_type": by_type,
            "period": {
                "start": start.isoformat() if start else None,
                "end": end.isoformat() if end else None,
            },
        }

    def get_breakdown(
        self,
        org_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Get detailed usage events for an organization.

        Returns individual events ordered by timestamp descending.
        """
        stmt = select(UsageEvent).where(UsageEvent.org_id == org_id)

        if start:
            stmt = stmt.where(UsageEvent.timestamp >= start)
        if end:
            stmt = stmt.where(UsageEvent.timestamp <= end)

        stmt = stmt.order_by(UsageEvent.timestamp.desc()).limit(limit)
        events = self.db.execute(stmt).scalars().all()

        return [
            {
                "id": e.id,
                "event_type": e.event_type,
                "quantity": e.quantity,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "metadata": json.loads(e.metadata_json) if e.metadata_json else None,
            }
            for e in events
        ]
