"""
SQLAlchemy 2.0 models for Supplier and Warehouse (V2.5).

Supplier prefills:
  lead_time_days  → SimulationInput.supplier_delay
  supply_status   → SimulationInput.supply_status  (High | Medium | Low)

Warehouse prefills:
  warehouse_id    → SimulationInput.warehouse  (W1 | W2 | W3)

Both are owned by a Company.
"""

from datetime import datetime

from database import Base
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column


class Supplier(Base):
    """A supplier owned by a Company."""

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)

    name: Mapped[str] = mapped_column(index=True)

    # Prefill targets
    lead_time_days: Mapped[float] = mapped_column(default=0.0)  # → supplier_delay
    supply_status: Mapped[str] = mapped_column(default="Medium")  # → supply_status

    # Context (displayed, not yet used in agent pipeline)
    reliability_pct: Mapped[float] = mapped_column(default=100.0)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class Warehouse(Base):
    """A warehouse owned by a Company."""

    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)

    name: Mapped[str] = mapped_column(index=True)

    # Prefill target — must be W1, W2, or W3
    warehouse_id: Mapped[str] = mapped_column(
        default="W1"
    )  # → SimulationInput.warehouse

    location: Mapped[str] = mapped_column(default="")
    capacity: Mapped[float] = mapped_column(default=10000.0)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
