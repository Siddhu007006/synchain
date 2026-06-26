"""
SQLAlchemy 2.0 models for Company (V2 Phase 1).

The Company is the root business entity in V2.
All products, suppliers, warehouses, and digital twins will belong to a company.

Archive workflow (safe delete):
  is_archived = False  → active, visible in listings
  is_archived = True   → archived, hidden from listings, all data preserved
"""

from datetime import datetime

from database import Base
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column


class Company(Base):
    """Root business entity — represents a real-world company using SynChain."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(index=True)
    industry: Mapped[str] = mapped_column(default="")
    country: Mapped[str] = mapped_column(default="")

    # Archive workflow — never hard-delete a company with data
    is_archived: Mapped[bool] = mapped_column(default=False, index=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    # Phase E8: Multi-tenant isolation — each company belongs to one org
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), index=True, default=1
    )
