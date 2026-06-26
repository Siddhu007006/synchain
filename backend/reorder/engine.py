"""
Reorder Recommendation Engine (V3.0 Sprint A).

Uses the **Reorder Point Model** — NOT EOQ.

Formula:
  Reorder Point = Lead Time Demand + Safety Stock

Where:
  Lead Time Demand = daily_demand × lead_time_days
  Safety Stock     = z_score × σ_demand × √lead_time_days

  daily_demand     = forecast_demand / 30
  σ_demand         = forecast_demand × (1 - confidence)   # uncertainty proxy
  z_score          = 1.65  (95% service level)

Why Reorder Point and not EOQ:
  - EOQ requires holding cost and ordering cost — we don't have those.
  - Reorder Point uses data we already have: stock, forecast, lead time, signals.
  - Simpler to explain to a customer: "Order when stock drops below this level."
  - Trust comes from transparency, not mathematical sophistication.

Severity is derived from days_until_stockout:
  CRITICAL:  ≤ 7  days
  HIGH:      ≤ 14 days
  MEDIUM:    ≤ 30 days
  LOW:       ≤ 60 days
  NONE:      > 60 days

V3.0 Additions (pre-Sprint-B):
  - recommendation_confidence: composite trust score
  - financial_impact: estimated revenue at risk from stockout
  - inventory_health: company-level 0-100 KPI
"""

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

# Service level z-scores for safety stock
# 95% service level is standard for manufacturing
Z_SCORE_95 = 1.65

# Severity thresholds (days until stockout)
SEVERITY_THRESHOLDS = [
    (7, "CRITICAL"),
    (14, "HIGH"),
    (30, "MEDIUM"),
    (60, "LOW"),
]
SEVERITY_NONE = "NONE"


@dataclass
class ProductData:
    """Input: product inventory state."""

    product_id: int
    product_name: str
    company_id: int
    current_stock: float
    avg_monthly_demand: float
    unit_price: float = 0.0  # V3.0: for financial impact


@dataclass
class ForecastData:
    """Input: forecast engine output for a product."""

    forecast_demand: float  # monthly
    confidence: float  # 0.0 - 1.0
    supply_risk: str  # Low | Medium | High
    trend_factor: float = 1.0


@dataclass
class SupplierData:
    """Input: best available supplier for this product's company."""

    supplier_id: int
    supplier_name: str
    lead_time_days: float
    reliability_pct: float  # 0-100
    supply_status: str  # High | Medium | Low


@dataclass
class SignalContext:
    """Input: active signals relevant to this product."""

    active_count: int = 0
    critical_count: int = 0
    high_severity_signals: list[str] = field(default_factory=list)
    # Signal descriptions for explainability


@dataclass
class FinancialImpact:
    """
    Estimated financial exposure from stockout risk.

    Small manufacturers think in money — not signals, not forecasts.
    Even a rough estimate helps them prioritize.
    """

    stockout_risk: str  # CRITICAL | HIGH | MEDIUM | LOW | NONE
    units_at_risk: float  # demand during stockout period
    estimated_revenue_impact: float | None  # None if unit_price unknown
    currency: str = "USD"
    has_price_data: bool = False


@dataclass
class ReorderResult:
    """Output: complete recommendation for one product."""

    # Identity
    product_id: int
    product_name: str
    company_id: int

    # Severity
    severity: str

    # Inventory
    current_stock: float
    forecast_demand: float
    daily_demand: float

    # Stockout
    days_until_stockout: int
    stockout_date: str

    # Reorder Point breakdown
    reorder_point: float
    safety_stock: float
    lead_time_demand: float

    # Action
    recommended_quantity: float
    recommended_supplier_id: Optional[int]
    recommended_supplier_name: Optional[str]
    supplier_lead_time_days: float
    recommended_order_date: str

    # Confidence — raw forecast confidence
    confidence: float

    # V3.0: Composite recommendation confidence
    recommendation_confidence: float

    # V3.0: Financial impact
    financial_impact: FinancialImpact

    # Explainability
    reasoning: list[str]


def classify_severity(days_until_stockout: int) -> str:
    """Map days-until-stockout to severity label."""
    for threshold, label in SEVERITY_THRESHOLDS:
        if days_until_stockout <= threshold:
            return label
    return SEVERITY_NONE


def calculate_recommendation_confidence(
    forecast_confidence: float,
    supplier_reliability_pct: float | None,
    signal_critical_count: int,
) -> float:
    """
    Composite recommendation confidence score (0.0 - 1.0).

    Weights:
      - Forecast confidence:    50% (demand prediction quality)
      - Supplier reliability:   30% (fulfillment certainty)
      - Signal uncertainty:     20% (external risk factors)

    Without this, users cannot gauge how much to trust
    the recommendation.
    """
    # Forecast component (0-1)
    forecast_score = forecast_confidence

    # Supplier component (0-1), default 0.5 if no supplier
    if supplier_reliability_pct is not None:
        supplier_score = supplier_reliability_pct / 100.0
    else:
        supplier_score = 0.5

    # Signal component: more critical signals → lower confidence
    # Each critical signal reduces by 0.15, capped at 0
    signal_score = max(0.0, 1.0 - (signal_critical_count * 0.15))

    composite = forecast_score * 0.50 + supplier_score * 0.30 + signal_score * 0.20
    return round(min(1.0, max(0.0, composite)), 3)


def calculate_financial_impact(
    daily_demand: float,
    days_until_stockout: int,
    lead_time_days: float,
    unit_price: float,
    severity: str,
) -> FinancialImpact:
    """
    Estimate financial exposure from potential stockout.

    units_at_risk = demand during the gap between stockout and
                    when replenishment would arrive.

    If lead_time > days_until_stockout:
      gap = lead_time - days_until_stockout (we're already late)
    else:
      gap = 0 (order in time → no exposure)

    estimated_revenue_impact = units_at_risk × unit_price
    """
    gap_days = max(0.0, lead_time_days - days_until_stockout)
    units_at_risk = round(daily_demand * gap_days, 1)

    has_price = unit_price > 0
    revenue_impact = round(units_at_risk * unit_price, 2) if has_price else None

    return FinancialImpact(
        stockout_risk=severity,
        units_at_risk=units_at_risk,
        estimated_revenue_impact=revenue_impact,
        has_price_data=has_price,
    )


def calculate_recommendation(
    product: ProductData,
    forecast: ForecastData | None,
    supplier: SupplierData | None,
    signals: SignalContext,
    today: date | None = None,
) -> ReorderResult:
    """
    Generate a reorder recommendation for a single product.

    This is a pure function — no DB access, no side effects.
    All inputs are dataclasses, output is a dataclass.

    Decision chain:
      1. Calculate daily demand from forecast (or fallback to avg_monthly_demand)
      2. Project days until stockout
      3. Calculate reorder point (lead time demand + safety stock)
      4. Determine recommended quantity
      5. Calculate order date (stockout_date - lead_time)
      6. Classify severity
      7. Calculate recommendation confidence
      8. Calculate financial impact
      9. Build reasoning chain
    """
    if today is None:
        today = date.today()

    reasoning: list[str] = []

    # --- Step 1: Daily demand ---
    if forecast and forecast.forecast_demand > 0:
        monthly_demand = forecast.forecast_demand
        confidence = forecast.confidence
        reasoning.append(
            f"Forecast demand: {monthly_demand:.0f} units/month "
            f"(confidence: {confidence:.0%})"
        )
    elif product.avg_monthly_demand > 0:
        monthly_demand = product.avg_monthly_demand
        confidence = 0.5  # low confidence — no forecast available
        reasoning.append(
            f"No forecast available. Using average demand: "
            f"{monthly_demand:.0f} units/month (confidence: 50%)"
        )
    else:
        # No demand data at all — cannot recommend
        empty_impact = FinancialImpact(
            stockout_risk="NONE",
            units_at_risk=0.0,
            estimated_revenue_impact=None,
            has_price_data=False,
        )
        return ReorderResult(
            product_id=product.product_id,
            product_name=product.product_name,
            company_id=product.company_id,
            severity=SEVERITY_NONE,
            current_stock=product.current_stock,
            forecast_demand=0.0,
            daily_demand=0.0,
            days_until_stockout=999,
            stockout_date=(today + timedelta(days=999)).isoformat(),
            reorder_point=0.0,
            safety_stock=0.0,
            lead_time_demand=0.0,
            recommended_quantity=0.0,
            recommended_supplier_id=None,
            recommended_supplier_name=None,
            supplier_lead_time_days=0.0,
            recommended_order_date=today.isoformat(),
            confidence=0.0,
            recommendation_confidence=0.0,
            financial_impact=empty_impact,
            reasoning=["No demand data available. Cannot generate recommendation."],
        )

    daily_demand = monthly_demand / 30.0

    # --- Step 2: Stockout projection ---
    if daily_demand > 0:
        days_until_stockout = max(0, int(product.current_stock / daily_demand))
    else:
        days_until_stockout = 999

    stockout_date = today + timedelta(days=days_until_stockout)

    reasoning.append(
        f"Current stock: {product.current_stock:.0f} units "
        f"→ covers {days_until_stockout} days at forecasted rate"
    )

    # --- Step 3: Lead time + Safety stock ---
    lead_time_days = supplier.lead_time_days if supplier else 7.0  # default 7 days

    if supplier:
        reasoning.append(
            f"Supplier: {supplier.supplier_name} "
            f"(lead time: {lead_time_days:.0f} days, "
            f"reliability: {supplier.reliability_pct:.0f}%)"
        )

    lead_time_demand = daily_demand * lead_time_days

    # Safety stock: z × σ × √L
    # σ (demand uncertainty) = monthly_demand × (1 - confidence)
    sigma_demand = monthly_demand * (1.0 - confidence)
    safety_stock = Z_SCORE_95 * sigma_demand * math.sqrt(lead_time_days / 30.0)

    # Adjust safety stock for low supplier reliability
    if supplier and supplier.reliability_pct < 80:
        reliability_factor = 1.0 + (100 - supplier.reliability_pct) / 100.0
        safety_stock *= reliability_factor
        reasoning.append(
            f"Safety stock increased {reliability_factor:.1f}× "
            f"due to supplier reliability ({supplier.reliability_pct:.0f}%)"
        )

    # Signal-driven adjustment
    if signals.critical_count > 0:
        signal_multiplier = 1.0 + (signals.critical_count * 0.15)
        safety_stock *= signal_multiplier
        for desc in signals.high_severity_signals:
            reasoning.append(f"Active signal: {desc}")
        reasoning.append(
            f"Safety stock increased {signal_multiplier:.1f}× "
            f"due to {signals.critical_count} critical signal(s)"
        )

    reorder_point = lead_time_demand + safety_stock

    # --- Step 4: Recommended quantity ---
    # Order enough to bring stock up to the reorder point
    # plus one month of demand as buffer
    target_stock = reorder_point + monthly_demand
    quantity_needed = max(0.0, target_stock - product.current_stock)
    # Round up to nearest whole unit
    recommended_quantity = math.ceil(quantity_needed)

    if recommended_quantity > 0:
        reasoning.append(
            f"Reorder point: {reorder_point:.0f} units "
            f"(lead time demand: {lead_time_demand:.0f} + "
            f"safety stock: {safety_stock:.0f})"
        )
        reasoning.append(
            f"Recommended order: {recommended_quantity} units "
            f"(target stock: {target_stock:.0f})"
        )
    else:
        reasoning.append(
            f"Stock ({product.current_stock:.0f}) is above reorder point "
            f"({reorder_point:.0f}). No order needed."
        )

    # --- Step 5: Order date ---
    # Must order by: stockout_date - lead_time_days
    order_by_date = stockout_date - timedelta(days=int(lead_time_days))
    # Don't recommend dates in the past
    if order_by_date < today:
        order_by_date = today
        if recommended_quantity > 0:
            reasoning.append(
                f"⚠ Order is OVERDUE — stockout in {days_until_stockout} days, "
                f"lead time is {lead_time_days:.0f} days"
            )
    else:
        if recommended_quantity > 0:
            reasoning.append(
                f"Order by {order_by_date.isoformat()} to prevent stockout "
                f"on {stockout_date.isoformat()}"
            )

    # --- Step 6: Severity ---
    severity = classify_severity(days_until_stockout)

    # --- Step 7: Recommendation confidence ---
    rec_confidence = calculate_recommendation_confidence(
        forecast_confidence=confidence,
        supplier_reliability_pct=(supplier.reliability_pct if supplier else None),
        signal_critical_count=signals.critical_count,
    )
    reasoning.append(f"Recommendation confidence: {rec_confidence:.0%}")

    # --- Step 8: Financial impact ---
    fin_impact = calculate_financial_impact(
        daily_demand=daily_demand,
        days_until_stockout=days_until_stockout,
        lead_time_days=lead_time_days,
        unit_price=product.unit_price,
        severity=severity,
    )
    if fin_impact.has_price_data and fin_impact.estimated_revenue_impact:
        reasoning.append(
            f"Estimated revenue at risk: "
            f"${fin_impact.estimated_revenue_impact:,.0f} "
            f"({fin_impact.units_at_risk:.0f} units × "
            f"${product.unit_price:.2f}/unit)"
        )
    elif fin_impact.units_at_risk > 0:
        reasoning.append(
            f"Units at risk during stockout gap: "
            f"{fin_impact.units_at_risk:.0f} units "
            f"(set unit_price on product for revenue estimate)"
        )

    return ReorderResult(
        product_id=product.product_id,
        product_name=product.product_name,
        company_id=product.company_id,
        severity=severity,
        current_stock=product.current_stock,
        forecast_demand=monthly_demand,
        daily_demand=round(daily_demand, 2),
        days_until_stockout=days_until_stockout,
        stockout_date=stockout_date.isoformat(),
        reorder_point=round(reorder_point, 1),
        safety_stock=round(safety_stock, 1),
        lead_time_demand=round(lead_time_demand, 1),
        recommended_quantity=recommended_quantity,
        recommended_supplier_id=supplier.supplier_id if supplier else None,
        recommended_supplier_name=supplier.supplier_name if supplier else None,
        supplier_lead_time_days=lead_time_days,
        recommended_order_date=order_by_date.isoformat(),
        confidence=round(confidence, 3),
        recommendation_confidence=rec_confidence,
        financial_impact=fin_impact,
        reasoning=reasoning,
    )


# ---------------------------------------------------------------------------
# Inventory Health Score — company-level KPI (0-100)
# ---------------------------------------------------------------------------


def calculate_inventory_health(
    recommendations: list[ReorderResult],
) -> dict:
    """
    Company-level Inventory Health Score (0-100).

    This is the executive KPI. A single number that answers:
    "How healthy is our inventory position right now?"

    Components (weighted):
      - Forecast confidence avg:   30%  (can we trust our demand forecast?)
      - Stockout risk score:       25%  (how many products are at risk?)
      - Signal health:             25%  (are there active disruption signals?)
      - Supplier reliability:      20%  (can our suppliers deliver?)

    Returns dict with score and component breakdown.
    """
    if not recommendations:
        return {
            "score": 0,
            "grade": "N/A",
            "components": {
                "forecast_confidence": 0.0,
                "stockout_safety": 0.0,
                "signal_health": 0.0,
                "supplier_reliability": 0.0,
            },
            "total_products": 0,
            "critical_count": 0,
            "high_count": 0,
        }

    n = len(recommendations)

    # 1. Forecast confidence (avg across products, 0-100)
    avg_confidence = sum(r.confidence for r in recommendations) / n
    forecast_score = avg_confidence * 100

    # 2. Stockout risk — % of products NOT in critical/high
    safe_count = sum(
        1 for r in recommendations if r.severity not in ("CRITICAL", "HIGH")
    )
    stockout_score = (safe_count / n) * 100

    # 3. Signal health — inverse of avg critical signal impact
    # recommendation_confidence already factors in signals
    avg_rec_conf = sum(r.recommendation_confidence for r in recommendations) / n
    signal_score = avg_rec_conf * 100

    # 4. Supplier reliability (from recommendation confidence)
    # Products with suppliers contribute their reliability
    supplier_scores = []
    for r in recommendations:
        if r.recommended_supplier_id is not None:
            # Back-derive from recommendation_confidence
            supplier_scores.append(r.recommendation_confidence)
        else:
            supplier_scores.append(0.5)
    avg_supplier = sum(supplier_scores) / len(supplier_scores) * 100

    # Weighted composite
    health = (
        forecast_score * 0.30
        + stockout_score * 0.25
        + signal_score * 0.25
        + avg_supplier * 0.20
    )
    health = round(min(100, max(0, health)))

    # Grade
    if health >= 80:
        grade = "HEALTHY"
    elif health >= 60:
        grade = "MODERATE"
    elif health >= 40:
        grade = "AT_RISK"
    else:
        grade = "CRITICAL"

    return {
        "score": health,
        "grade": grade,
        "components": {
            "forecast_confidence": round(forecast_score, 1),
            "stockout_safety": round(stockout_score, 1),
            "signal_health": round(signal_score, 1),
            "supplier_reliability": round(avg_supplier, 1),
        },
        "total_products": n,
        "critical_count": sum(1 for r in recommendations if r.severity == "CRITICAL"),
        "high_count": sum(1 for r in recommendations if r.severity == "HIGH"),
    }
