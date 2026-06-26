"""
SQLAlchemy 2.0 models for SynChain.

Uses mapped_column() instead of deprecated Column().
Database structure supports:
  - Simulation history (via simulations table with created_at timestamp)
  - Agent breakdown storage (JSON-serialized in agent_breakdown column)
  - Scenario comparison via stored inputs
"""

from datetime import datetime

from database import Base
from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Simulation(Base):
    """Stores the raw input for each simulation run."""

    __tablename__ = "simulations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product: Mapped[str] = mapped_column(index=True)
    stock: Mapped[float]
    warehouse: Mapped[str]
    demand: Mapped[float]
    supplier_delay: Mapped[float]
    market_trend: Mapped[str] = mapped_column(default="Neutral")
    supply_status: Mapped[str] = mapped_column(default="Medium")
    season: Mapped[str] = mapped_column(default="Normal")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)

    # Phase E8: Multi-tenant isolation
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), index=True, default=1
    )

    # Phase E: Optional link to a Digital Twin
    twin_id: Mapped[int | None] = mapped_column(
        ForeignKey("digital_twins.id"), default=None, nullable=True
    )

    # V2.4: Optional links to Product and Company for traceability
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id"), default=None, nullable=True, index=True
    )
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"), default=None, nullable=True, index=True
    )

    # V2.5: Optional links to Supplier and Warehouse record for traceability
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id"), default=None, nullable=True, index=True
    )
    warehouse_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id"), default=None, nullable=True, index=True
    )

    result: Mapped["Result"] = relationship(back_populates="simulation", uselist=False)


class Result(Base):
    """Stores the computed output for a simulation run."""

    __tablename__ = "results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    simulation_id: Mapped[int] = mapped_column(
        ForeignKey("simulations.id"), unique=True
    )

    # Core result fields (Phase A)
    demand_forecast: Mapped[float]
    recommended_inventory: Mapped[float]
    selected_warehouse: Mapped[str]
    route: Mapped[str]
    risk: Mapped[str]
    strategy: Mapped[str]

    # Phase B: Agent Enhancement fields
    agent_breakdown: Mapped[str | None] = mapped_column(Text, default=None)
    overall_confidence: Mapped[float | None] = mapped_column(default=None)
    explanation: Mapped[str | None] = mapped_column(Text, default=None)

    simulation: Mapped["Simulation"] = relationship(back_populates="result")
