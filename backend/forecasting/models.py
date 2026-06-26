"""
SQLAlchemy model for persisting forecast outputs.

The forecast_records table stores every forecast generated via the API,
providing an audit trail and enabling future forecast-vs-actual analysis.

Design Note: Forecasts are generated on-demand (not auto-generated after
simulations). Each record snapshots the twin state used as input so the
forecast is fully reproducible even if twin state changes later.
"""

from datetime import datetime

from database import Base
from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class ForecastRecord(Base):
    """Persisted forecast output for audit and comparison."""

    __tablename__ = "forecast_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    twin_id: Mapped[int] = mapped_column(ForeignKey("digital_twins.id"), index=True)

    # Phase E8: Multi-tenant isolation
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), index=True, default=1
    )
    product_name: Mapped[str] = mapped_column(index=True)
    horizon: Mapped[int]
    forecast_demand: Mapped[float]
    trend_factor: Mapped[float]
    season_factor: Mapped[float]
    supply_risk: Mapped[str]  # Low | Medium | High
    confidence: Mapped[float]
    explanation: Mapped[str] = mapped_column(Text)

    # Input snapshots — what twin state was used to produce this forecast
    source_avg_demand: Mapped[float]
    source_trend: Mapped[str]
    source_season: Mapped[str]
    source_reliability: Mapped[float]

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
