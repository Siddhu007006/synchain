"""
Pydantic response models for Signal Intelligence API endpoints.

Endpoints served:
  - GET /twins/{twin_id}/signals        → SignalListResponse
  - GET /twins/{twin_id}/signals/summary → SignalSummaryResponse
"""

from pydantic import BaseModel, Field


class SignalEventEntry(BaseModel):
    """Single signal event in API responses."""

    id: int
    source: str = Field(..., description="Detector name (e.g. DemandSpike)")
    signal_type: str = Field(..., description="demand | supply | risk | market")
    severity: float = Field(..., ge=0.0, le=1.0)
    severity_label: str = Field(..., description="info | warning | critical")
    payload: dict = Field(..., description="Structured signal context")
    created_at: str | None = None


class SignalListResponse(BaseModel):
    """Response for GET /twins/{twin_id}/signals."""

    twin_id: int
    total_signals: int
    signals: list[SignalEventEntry]


class SignalCountByType(BaseModel):
    """Signal counts broken down by type."""

    demand: int = 0
    supply: int = 0
    risk: int = 0
    market: int = 0
    external: int = 0  # E5: external provider signals (gap fix)
    compound: int = 0  # E6: compound pattern signals


class SignalCountBySeverity(BaseModel):
    """Signal counts broken down by severity label."""

    info: int = 0
    warning: int = 0
    critical: int = 0


class SignalSummaryResponse(BaseModel):
    """Response for GET /twins/{twin_id}/signals/summary."""

    twin_id: int
    total_signals: int
    by_type: SignalCountByType
    by_severity: SignalCountBySeverity
    latest_critical: SignalEventEntry | None = None
    health_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="1.0 = healthy, 0.0 = critical. Recency-weighted from last 10 signals.",
    )


class ActiveSignalEntry(BaseModel):
    """Signal entry embedded in forecast responses."""

    source: str
    signal_type: str
    severity: float
    payload: dict
    created_at: str | None = None
