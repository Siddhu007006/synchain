"""
Pydantic schemas for Reorder Recommendation API (V3.0 Sprint A).

Output contract: every recommendation answers six questions:
  1. What should I order?       → product_name
  2. How much?                  → recommended_quantity
  3. Which supplier?            → recommended_supplier_name
  4. When should I order?       → recommended_order_date
  5. How urgent?                → severity + days_until_stockout
  6. Why?                       → reasoning (list of explanations)

Plus trust + financial context:
  7. How confident?             → recommendation_confidence
  8. What's the financial risk? → financial_impact
"""

from typing import Optional

from pydantic import BaseModel, Field


class FinancialImpactResponse(BaseModel):
    """Estimated financial exposure from stockout risk."""

    stockout_risk: str = Field(..., description="CRITICAL | HIGH | MEDIUM | LOW | NONE")
    units_at_risk: float = Field(
        ..., description="Demand units that would go unfulfilled during stockout"
    )
    estimated_revenue_impact: Optional[float] = Field(
        None, description="Revenue at risk in USD (null if unit_price not set)"
    )
    currency: str = "USD"
    has_price_data: bool = Field(
        ..., description="True if product has unit_price set for revenue calc"
    )


class ReorderRecommendation(BaseModel):
    """Single product reorder recommendation."""

    # Identity
    product_id: int
    product_name: str
    company_id: int

    # Severity
    severity: str = Field(
        ...,
        description="CRITICAL | HIGH | MEDIUM | LOW | NONE",
    )

    # Inventory state
    current_stock: float
    forecast_demand: float = Field(
        ..., description="Forecast monthly demand from the forecast engine"
    )
    daily_demand: float = Field(..., description="forecast_demand / 30")

    # Stockout projection
    days_until_stockout: int = Field(
        ..., description="Days until stock reaches zero at forecasted rate"
    )
    stockout_date: str = Field(..., description="Projected stockout date (ISO format)")

    # Reorder Point calculation
    reorder_point: float = Field(..., description="Lead Time Demand + Safety Stock")
    safety_stock: float
    lead_time_demand: float

    # Action
    recommended_quantity: float = Field(
        ..., description="Units to order (reorder_point - current_stock, min 0)"
    )
    recommended_supplier_id: Optional[int] = None
    recommended_supplier_name: Optional[str] = None
    supplier_lead_time_days: float = 0.0
    recommended_order_date: str = Field(
        ..., description="Latest date to place order (ISO format)"
    )

    # Forecast confidence (raw)
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Forecast confidence score"
    )

    # Composite recommendation confidence
    recommendation_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Composite trust score: "
            "50% forecast + 30% supplier reliability + 20% signal health"
        ),
    )

    # Financial impact
    financial_impact: FinancialImpactResponse = Field(
        ..., description="Estimated financial exposure from stockout risk"
    )

    # Explainability — mandatory
    reasoning: list[str] = Field(
        ...,
        min_length=1,
        description="Human-readable explanation chain for this recommendation",
    )


class InventoryHealthComponent(BaseModel):
    """Breakdown of inventory health score components."""

    forecast_confidence: float = Field(
        ..., description="Forecast quality score (0-100)"
    )
    stockout_safety: float = Field(
        ..., description="% of products NOT at critical/high risk (0-100)"
    )
    signal_health: float = Field(
        ..., description="Signal-adjusted confidence score (0-100)"
    )
    supplier_reliability: float = Field(
        ..., description="Supplier health score (0-100)"
    )


class InventoryHealthResponse(BaseModel):
    """Company-level Inventory Health KPI (0-100)."""

    company_id: int
    company_name: str
    score: int = Field(..., ge=0, le=100, description="Inventory health score (0-100)")
    grade: str = Field(..., description="HEALTHY | MODERATE | AT_RISK | CRITICAL | N/A")
    components: InventoryHealthComponent
    total_products: int
    critical_count: int
    high_count: int


class RecommendationListResponse(BaseModel):
    """Response from GET /companies/{id}/recommendations."""

    company_id: int
    company_name: str
    total: int
    critical_count: int = 0
    high_count: int = 0
    inventory_health: InventoryHealthResponse
    recommendations: list[ReorderRecommendation] = Field(default_factory=list)


class SingleRecommendationResponse(BaseModel):
    """Response from GET /products/{id}/recommendation."""

    recommendation: ReorderRecommendation
