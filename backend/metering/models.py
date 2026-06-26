"""
Usage event SQLAlchemy model (Phase E9).

Records individual usage events for billing-ready metering.
Each event is an immutable record of a specific action taken
within an organization.

Concept:
  Metering records raw usage events without billing logic. This
  creates the data foundation for future billing integration
  (Stripe, etc.) without coupling to any specific payment provider.
  Events are append-only and org-scoped.
"""

from datetime import datetime

from database import Base
from sqlalchemy import ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class UsageEvent(Base):
    """Individual usage event for billing metering."""

    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    event_type: Mapped[str] = mapped_column(index=True)  # e.g., "simulation.run"
    quantity: Mapped[int] = mapped_column(default=1)
    timestamp: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    metadata_json: Mapped[str | None] = mapped_column(
        Text, default=None
    )  # JSON extra data

    __table_args__ = (
        Index("ix_usage_org_type", "org_id", "event_type"),
        Index("ix_usage_org_timestamp", "org_id", "timestamp"),
    )
