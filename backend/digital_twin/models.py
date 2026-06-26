"""
SQLAlchemy 2.0 models for the Digital Twin state layer.

Tables:
  - digital_twins:        Root twin entity (one per supply chain)
  - product_states:       Per-product demand/stock tracking (EWMA)
  - warehouse_states:     Per-warehouse utilization + selection metrics
  - supplier_states:      Aggregate supplier reliability (V1 — see design note)
  - market_states:        Global market condition trends
  - twin_state_history:   Audit log of every state mutation
  - signal_events:        Persistent record of signal readings (populated in E3)

Design Notes:
  - SupplierState is a V1 aggregate model. It tracks global supplier metrics
    across all simulations in a twin. In future phases, this will evolve into
    per-supplier state models with individual supplier IDs, performance
    histories, and relationship graphs.
  - The Digital Twin evolves from simulation outcomes and user-generated
    simulations, not from real-world operational telemetry.
"""

from datetime import datetime

from database import Base
from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship


class DigitalTwin(Base):
    """Root twin entity — represents a single supply chain."""

    __tablename__ = "digital_twins"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(default="Default Supply Chain")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    simulation_count: Mapped[int] = mapped_column(default=0)

    # Phase E8: Multi-tenant isolation
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), index=True, default=1
    )

    # V2.2: Optional company ownership
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"), index=True, nullable=True, default=None
    )

    # Relationships
    product_states: Mapped[list["ProductState"]] = relationship(
        back_populates="twin", cascade="all, delete-orphan"
    )
    warehouse_states: Mapped[list["WarehouseState"]] = relationship(
        back_populates="twin", cascade="all, delete-orphan"
    )
    supplier_state: Mapped["SupplierState | None"] = relationship(
        back_populates="twin", cascade="all, delete-orphan", uselist=False
    )
    market_state: Mapped["MarketState | None"] = relationship(
        back_populates="twin", cascade="all, delete-orphan", uselist=False
    )
    history: Mapped[list["TwinStateHistory"]] = relationship(
        back_populates="twin", cascade="all, delete-orphan"
    )
    signal_events: Mapped[list["SignalEvent"]] = relationship(
        back_populates="twin", cascade="all, delete-orphan"
    )


class ProductState(Base):
    """Per-product state within a twin. Tracks demand evolution via EWMA."""

    __tablename__ = "product_states"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    twin_id: Mapped[int] = mapped_column(ForeignKey("digital_twins.id"), index=True)
    product_name: Mapped[str] = mapped_column(index=True)
    latest_stock: Mapped[float] = mapped_column(default=0.0)
    latest_demand: Mapped[float] = mapped_column(default=0.0)
    avg_demand: Mapped[float] = mapped_column(default=0.0)
    demand_trend: Mapped[str] = mapped_column(default="Stable")  # Rising|Stable|Falling
    simulation_count: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    twin: Mapped["DigitalTwin"] = relationship(back_populates="product_states")

    __table_args__ = (
        # Enforce unique product per twin
        {"sqlite_autoincrement": True},
    )


class WarehouseState(Base):
    """Per-warehouse state within a twin. Tracks utilization and selection rate."""

    __tablename__ = "warehouse_states"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    twin_id: Mapped[int] = mapped_column(ForeignKey("digital_twins.id"), index=True)
    warehouse_id: Mapped[str]  # W1, W2, W3
    times_selected: Mapped[int] = mapped_column(default=0)
    utilization_pct: Mapped[float] = mapped_column(default=0.0)
    selection_rate: Mapped[float] = mapped_column(default=0.0)
    avg_delivery_score: Mapped[float] = mapped_column(default=0.0)
    avg_risk_score: Mapped[float] = mapped_column(default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    twin: Mapped["DigitalTwin"] = relationship(back_populates="warehouse_states")


class SupplierState(Base):
    """
    Aggregate supplier state within a twin (V1).

    Design Note: This is a V1 aggregate model tracking global supplier metrics
    across all simulations. In future phases, this will evolve into per-supplier
    state models with individual supplier IDs, performance histories, and
    relationship graphs.
    """

    __tablename__ = "supplier_states"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    twin_id: Mapped[int] = mapped_column(
        ForeignKey("digital_twins.id"), unique=True, index=True
    )
    avg_delay: Mapped[float] = mapped_column(default=0.0)
    max_delay_seen: Mapped[float] = mapped_column(default=0.0)
    reliability_score: Mapped[float] = mapped_column(default=100.0)
    supply_status_mode: Mapped[str] = mapped_column(default="Medium")
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    twin: Mapped["DigitalTwin"] = relationship(back_populates="supplier_state")


class MarketState(Base):
    """Global market condition state within a twin."""

    __tablename__ = "market_states"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    twin_id: Mapped[int] = mapped_column(
        ForeignKey("digital_twins.id"), unique=True, index=True
    )
    trend_mode: Mapped[str] = mapped_column(default="Neutral")
    season_mode: Mapped[str] = mapped_column(default="Normal")
    avg_confidence: Mapped[float] = mapped_column(default=0.0)
    avg_risk_score: Mapped[float] = mapped_column(default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    twin: Mapped["DigitalTwin"] = relationship(back_populates="market_state")


class TwinStateHistory(Base):
    """Audit log of every state mutation for trend analysis and debugging."""

    __tablename__ = "twin_state_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    twin_id: Mapped[int] = mapped_column(ForeignKey("digital_twins.id"), index=True)
    entity_type: Mapped[str]  # product | warehouse | supplier | market
    entity_id: Mapped[str]  # e.g. 'Widget-A', 'W1', 'supplier', 'market'
    field_name: Mapped[str]  # e.g. 'avg_demand', 'utilization_pct'
    old_value: Mapped[str | None] = mapped_column(Text, default=None)
    new_value: Mapped[str] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)

    twin: Mapped["DigitalTwin"] = relationship(back_populates="history")


class SignalEvent(Base):
    """Persistent record of signal readings (populated in Phase E3)."""

    __tablename__ = "signal_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    twin_id: Mapped[int] = mapped_column(ForeignKey("digital_twins.id"), index=True)
    source: Mapped[str]  # e.g. 'DemandTrendSignal'
    signal_type: Mapped[str]  # demand | supply | risk | market
    severity: Mapped[float] = mapped_column(default=0.0)
    payload: Mapped[str] = mapped_column(Text)  # JSON-encoded signal data
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)

    twin: Mapped["DigitalTwin"] = relationship(back_populates="signal_events")
