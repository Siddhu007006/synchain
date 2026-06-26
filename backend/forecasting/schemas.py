"""
Pydantic schemas for the Forecasting REST API.

Covers:
  - Forecast generation responses (per-horizon points)
  - Forecast record listing (audit trail)
  - Forecast summary (read-only aggregation)
"""

from typing import Optional

from pydantic import BaseModel, Field
from signals.schemas import ActiveSignalEntry

# ---------------------------------------------------------------------------
# Forecast generation
# ---------------------------------------------------------------------------


class ForecastSourceState(BaseModel):
    """Snapshot of twin state used as forecast input."""

    avg_demand: float
    demand_trend: str
    simulation_count: int
    season: str
    supplier_reliability: float


class ForecastPointResponse(BaseModel):
    """Single horizon forecast output."""

    horizon: int
    forecast_demand: float
    trend_factor: float
    season_factor: float
    supply_risk: str
    confidence: float
    explanation: str


class ForecastResponse(BaseModel):
    """Response from GET /twins/{id}/forecast."""

    twin_id: int
    product: str
    generated_at: str
    source_state: ForecastSourceState
    forecasts: list[ForecastPointResponse] = Field(default_factory=list)
    active_signals: list[ActiveSignalEntry] = Field(
        default_factory=list,
        description="Recent signals relevant to this product (E3)",
    )


# ---------------------------------------------------------------------------
# Forecast record listing (audit trail)
# ---------------------------------------------------------------------------


class ForecastRecordEntry(BaseModel):
    """Single persisted forecast record."""

    id: int
    product_name: str
    horizon: int
    forecast_demand: float
    trend_factor: float
    season_factor: float
    supply_risk: str
    confidence: float
    explanation: str
    source_avg_demand: float
    source_trend: str
    source_season: str
    source_reliability: float
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class ForecastRecordsResponse(BaseModel):
    """Response from GET /twins/{id}/forecasts."""

    twin_id: int
    total_records: int
    records: list[ForecastRecordEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Forecast summary (read-only aggregation)
# ---------------------------------------------------------------------------


class LatestForecast(BaseModel):
    """Most recent horizon-1 forecast for a product."""

    forecast_demand: float
    confidence: float
    supply_risk: str
    generated_at: Optional[str] = None


class ProductForecastSummary(BaseModel):
    """Per-product forecast summary."""

    product: str
    avg_demand: float
    demand_trend: str
    latest_forecast: Optional[LatestForecast] = None


class ForecastSummaryResponse(BaseModel):
    """Response from GET /twins/{id}/forecast/summary."""

    twin_id: int
    products: list[ProductForecastSummary] = Field(default_factory=list)
