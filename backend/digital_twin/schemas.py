"""
Pydantic schemas for the Digital Twin REST API.

Covers:
  - Twin creation/listing/detail responses
  - State domain snapshots (product, warehouse, supplier, market)
  - State history entries
  - Signal event entries (schema only — populated in E3)
"""

from typing import Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Twin CRUD schemas
# ---------------------------------------------------------------------------


class TwinCreateRequest(BaseModel):
    """Request to create a new digital twin."""

    name: str = Field(
        default="Default Supply Chain",
        description="Human-readable name for the supply chain twin",
    )
    company_id: Optional[int] = Field(
        default=None,
        description="Optional company this twin belongs to (V2.2)",
    )


class TwinSummary(BaseModel):
    """Condensed twin entry for listing."""

    id: int
    name: str
    simulation_count: int
    company_id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# State domain snapshots
# ---------------------------------------------------------------------------


class ProductStateSnapshot(BaseModel):
    """Read-only view of a product's state within a twin."""

    product_name: str
    latest_stock: float
    latest_demand: float
    avg_demand: float
    demand_trend: str
    simulation_count: int
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class WarehouseStateSnapshot(BaseModel):
    """Read-only view of a warehouse's state within a twin."""

    warehouse_id: str
    times_selected: int
    utilization_pct: float
    selection_rate: float
    avg_delivery_score: float
    avg_risk_score: float
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class SupplierStateSnapshot(BaseModel):
    """Read-only view of aggregate supplier state within a twin."""

    avg_delay: float
    max_delay_seen: float
    reliability_score: float
    supply_status_mode: str
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class MarketStateSnapshot(BaseModel):
    """Read-only view of global market state within a twin."""

    trend_mode: str
    season_mode: str
    avg_confidence: float
    avg_risk_score: float
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Full twin detail (with all state domains)
# ---------------------------------------------------------------------------


class TwinDetailResponse(BaseModel):
    """Full twin state snapshot with all domains."""

    id: int
    name: str
    simulation_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    product_states: list[ProductStateSnapshot] = Field(default_factory=list)
    warehouse_states: list[WarehouseStateSnapshot] = Field(default_factory=list)
    supplier_state: Optional[SupplierStateSnapshot] = None
    market_state: Optional[MarketStateSnapshot] = None


# ---------------------------------------------------------------------------
# State history
# ---------------------------------------------------------------------------


class StateHistoryEntry(BaseModel):
    """Single state change record from twin_state_history."""

    id: int
    entity_type: str
    entity_id: str
    field_name: str
    old_value: Optional[str] = None
    new_value: str
    changed_at: Optional[str] = None

    model_config = {"from_attributes": True}


class TwinHistoryResponse(BaseModel):
    """Response from GET /api/v1/twins/{id}/history."""

    twin_id: int
    total_entries: int
    entries: list[StateHistoryEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Signal events (schema only — populated in Phase E3)
# ---------------------------------------------------------------------------


class SignalEventEntry(BaseModel):
    """Single signal event record."""

    id: int
    source: str
    signal_type: str
    severity: float
    payload: str  # JSON string
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class TwinSignalsResponse(BaseModel):
    """Response from GET /api/v1/twins/{id}/signals."""

    twin_id: int
    total_events: int
    events: list[SignalEventEntry] = Field(default_factory=list)
