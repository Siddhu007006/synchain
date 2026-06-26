"""
ForecastEngine — deterministic EWMA-based demand forecasting.

Reads Digital Twin state and produces multi-horizon demand forecasts
with confidence scores and natural-language explanations.

Forecast Formula (revised — demand and supply are independent):
  forecast_demand = avg_demand × trend_factor × season_factor

Supply Risk (separate from demand):
  supply_risk = classify(supplier_reliability)
  supply_risk may be ELEVATED by active signals (E4)

Confidence Framework (absorbs uncertainty from all sources):
  base_confidence = clamp(base + horizon_penalty + trend_bonus + supplier_bonus, 0.1, 1.0)
  signal_penalty  = sum(weight[type] × severity for each active signal)    [E4]
  final_confidence = clamp(base_confidence - signal_penalty, 0.1, 1.0)     [E4]

Design Decisions:
  - Demand forecast is pure demand — no supply contamination.
  - Supply risk is surfaced as a separate field, not mixed into demand.
  - Confidence absorbs uncertainty from simulation count, horizon, trend, supply, AND signals.
  - Signals affect confidence (severity-proportional), risk (elevation), and explanations.
  - Explanations include full audit trail: base confidence, signal penalties, final confidence.
  - Forecasts are on-demand only (not auto-generated after simulations).
  - Horizons are abstract planning periods, not calendar units.
"""

import json
from dataclasses import dataclass, field

from digital_twin.manager import TwinManager
from forecasting.models import ForecastRecord
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Factors
# ---------------------------------------------------------------------------

# Trend factor: how demand changes per horizon based on trend direction
TREND_GROWTH_PER_HORIZON = 0.05  # Rising: +5% per horizon
TREND_DECLINE_PER_HORIZON = 0.03  # Falling: -3% per horizon (slower = realistic)

# Season multipliers
SEASON_FACTORS = {
    "Festival": 1.15,
    "Normal": 1.0,
    "Off-season": 0.85,
}

# Supply risk thresholds (reliability score → risk category)
SUPPLY_RISK_HIGH_THRESHOLD = 50.0
SUPPLY_RISK_MEDIUM_THRESHOLD = 80.0

# Confidence parameters
CONFIDENCE_SIM_DIVISOR = 10  # base = min(sim_count / 10, 1.0)
CONFIDENCE_HORIZON_PENALTY = 0.10  # -10% per horizon
CONFIDENCE_TREND_BONUS = 0.05  # +5% for Stable, -5% otherwise
CONFIDENCE_SUPPLIER_HIGH = -0.10  # reliability < 50 → -10%
CONFIDENCE_SUPPLIER_MED = 0.0  # reliability 50–80 → 0%
CONFIDENCE_SUPPLIER_LOW = 0.05  # reliability ≥ 80 → +5%
CONFIDENCE_MIN = 0.10
CONFIDENCE_MAX = 1.0

# Phase E4: Signal confidence weights (severity-proportional)
# penalty = weight × severity
SIGNAL_CONFIDENCE_WEIGHTS: dict[str, float] = {
    # E3 internal signals
    "DemandSpike": 0.10,  # Demand volatility
    "SupplierDegradation": 0.15,  # Supply disruption (highest impact)
    "WarehouseOverload": 0.08,  # Operational constraint
    "TrendShift": 0.00,  # Already in trend_factor, no double-counting
    # E5 external signals
    "NewsDisruption": 0.06,  # Informational, may not directly impact
    "WeatherAlert": 0.10,  # Physical disruption, high supply chain impact
    "CommodityShock": 0.08,  # Cost pressure, moderate forecast impact
    "EconomicShift": 0.05,  # Macro trend, slow-moving, lowest direct impact
    # E6 compound signals
    # NOTE: These stack additively with their atomic trigger penalties.
    # This is intentional (Additive Penalty Stacking, see E6 Architecture Report D6).
    # Post-E6 Business Logic Audit will validate penalty calibration.
    "SupplyShock": 0.12,  # DemandSpike + SupplierDegradation
    "FulfillmentCrisis": 0.10,  # WarehouseOverload + DemandSpike
    "MarketDisruption": 0.08,  # TrendShift + SupplierDegradation
    "PerfectStorm": 0.15,  # WeatherAlert + SupplierDeg + DemandSpike (3-trigger)
    "CostSqueeze": 0.06,  # CommodityShock + EconomicShift
}

# Risk elevation threshold: only elevate if signal severity > this
RISK_ELEVATION_THRESHOLD = 0.5
RISK_ELEVATION_SOURCES = {
    # E4 atomic
    "SupplierDegradation",
    "WarehouseOverload",
    "WeatherAlert",
    # E6 compound
    "SupplyShock",
    "FulfillmentCrisis",
    "PerfectStorm",
}


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class ForecastInput:
    """Snapshot of twin state used as forecast input."""

    avg_demand: float
    demand_trend: str  # Rising | Stable | Falling
    simulation_count: int
    season_mode: str  # Festival | Normal | Off-season
    supplier_reliability: float  # 0–100


@dataclass
class ForecastPoint:
    """Single horizon forecast output."""

    horizon: int
    forecast_demand: float
    trend_factor: float
    season_factor: float
    supply_risk: str  # Low | Medium | High
    confidence: float
    explanation: str
    # E4 audit trail (internal, not exposed in API schema)
    base_confidence: float = 0.0
    signal_penalty: float = 0.0


@dataclass
class SignalAdjustment:
    """Result of applying signal adjustments to a forecast point."""

    adjusted_confidence: float
    base_confidence: float
    signal_penalty: float
    adjusted_risk: str
    risk_elevated: bool
    original_risk: str
    explanation_suffix: str
    penalty_details: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure computation functions (stateless, testable)
# ---------------------------------------------------------------------------


def compute_trend_factor(trend: str, horizon: int) -> float:
    """
    Compute trend multiplier for a given horizon.

    Rising:  1.0 + (0.05 × h) — 5% growth per horizon
    Stable:  1.0
    Falling: 1.0 - (0.03 × h) — 3% decline per horizon
    """
    if trend == "Rising":
        return round(1.0 + TREND_GROWTH_PER_HORIZON * horizon, 4)
    elif trend == "Falling":
        return round(max(0.1, 1.0 - TREND_DECLINE_PER_HORIZON * horizon), 4)
    return 1.0


def compute_season_factor(season: str) -> float:
    """Map season mode to demand multiplier."""
    return SEASON_FACTORS.get(season, 1.0)


def classify_supply_risk(reliability: float) -> str:
    """
    Classify supplier reliability into risk category.

    This is independent of demand — supply risk is surfaced
    alongside the forecast, not mixed into it.
    """
    if reliability < SUPPLY_RISK_HIGH_THRESHOLD:
        return "High"
    elif reliability < SUPPLY_RISK_MEDIUM_THRESHOLD:
        return "Medium"
    return "Low"


def compute_confidence(
    simulation_count: int,
    horizon: int,
    trend: str,
    reliability: float,
) -> float:
    """
    Compute BASE forecast confidence score (0.1–1.0).

    This is the E2 confidence formula. In E4, signal penalties are applied
    on top of this via apply_signal_adjustments().

    Components:
      base:     min(sim_count / 10, 1.0) — data volume
      horizon:  -0.10 × h — distance penalty
      trend:    +0.05 if Stable, -0.05 otherwise — stability bonus
      supplier: +0.05 if reliable, -0.10 if unreliable — supply certainty
    """
    base = min(simulation_count / CONFIDENCE_SIM_DIVISOR, 1.0)
    horizon_adj = -CONFIDENCE_HORIZON_PENALTY * horizon
    trend_adj = CONFIDENCE_TREND_BONUS if trend == "Stable" else -CONFIDENCE_TREND_BONUS

    if reliability >= SUPPLY_RISK_MEDIUM_THRESHOLD:
        supplier_adj = CONFIDENCE_SUPPLIER_LOW
    elif reliability >= SUPPLY_RISK_HIGH_THRESHOLD:
        supplier_adj = CONFIDENCE_SUPPLIER_MED
    else:
        supplier_adj = CONFIDENCE_SUPPLIER_HIGH

    raw = base + horizon_adj + trend_adj + supplier_adj
    return round(max(CONFIDENCE_MIN, min(CONFIDENCE_MAX, raw)), 4)


# ---------------------------------------------------------------------------
# Phase E4: Signal adjustment functions
# ---------------------------------------------------------------------------


def compute_signal_penalty(active_signals: list) -> tuple[float, list[str]]:
    """
    Compute total confidence penalty from active signals.

    Formula: penalty = sum(weight[source] × severity) for each signal.
    TrendShift has weight 0.0 (already in trend_factor).

    Returns:
      (total_penalty, list of per-signal detail strings)
    """
    total = 0.0
    details: list[str] = []

    for sig in active_signals:
        source = _get_signal_source(sig)
        severity = _get_signal_severity(sig)
        weight = SIGNAL_CONFIDENCE_WEIGHTS.get(source, 0.0)
        penalty = round(weight * severity, 4)

        if penalty > 0:
            total += penalty
            details.append(
                f"{source} penalty: -{penalty:.2f} (severity {severity:.2f})"
            )

    return round(total, 4), details


def compute_risk_elevation(
    base_risk: str, active_signals: list
) -> tuple[str, bool, str | None]:
    """
    Elevate supply risk if critical operational signals exist.

    Rules:
      - Only SupplierDegradation and WarehouseOverload can elevate risk.
      - Only elevate if signal severity > 0.5.
      - Elevate by one tier (Low→Medium, Medium→High, High stays High).
      - Signals are evaluated severity-descending so the explanation credits
        the most severe signal (Business Logic Audit A2, 2026-06-06).

    Returns:
      (adjusted_risk, was_elevated, elevating_source)
    """
    elevation_map = {"Low": "Medium", "Medium": "High", "High": "High"}

    # Sort by severity descending so the most severe signal is credited
    sorted_signals = sorted(
        active_signals,
        key=lambda s: _get_signal_severity(s),
        reverse=True,
    )

    for sig in sorted_signals:
        source = _get_signal_source(sig)
        severity = _get_signal_severity(sig)

        if source in RISK_ELEVATION_SOURCES and severity > RISK_ELEVATION_THRESHOLD:
            elevated = elevation_map.get(base_risk, base_risk)
            if elevated != base_risk:
                return elevated, True, source

    return base_risk, False, None


def build_signal_explanation(
    base_confidence: float,
    signal_penalty: float,
    final_confidence: float,
    penalty_details: list[str],
    risk_elevated: bool,
    original_risk: str,
    adjusted_risk: str,
    elevating_source: str | None,
    elevating_severity: float | None,
    active_signals: list,
) -> str:
    """
    Build explanation suffix for signal adjustments.

    Provides full audit trail:
      - Base confidence
      - Each signal penalty
      - Final confidence
      - Risk elevation (if any)
      - TrendShift notes (if any)
    """
    parts: list[str] = []

    if signal_penalty > 0 or risk_elevated:
        parts.append("Signal adjustments:")

    # Confidence audit trail
    if signal_penalty > 0:
        penalty_str = ", ".join(penalty_details)
        parts.append(
            f"Base confidence {base_confidence:.2f}, "
            f"signal penalties [{penalty_str}], "
            f"final confidence {final_confidence:.2f}."
        )

    # Risk elevation
    if risk_elevated and elevating_source:
        sev_str = f", severity {elevating_severity:.2f}" if elevating_severity else ""
        parts.append(
            f"Risk elevated from {original_risk} to {adjusted_risk} "
            f"due to {elevating_source}{sev_str}."
        )

    # TrendShift notes (informational, no confidence impact)
    for sig in active_signals:
        source = _get_signal_source(sig)
        if source == "TrendShift":
            payload = _get_signal_payload(sig)
            old = payload.get("old_trend", "?")
            new = payload.get("new_trend", "?")
            shift_type = payload.get("shift_type", "unknown")
            parts.append(f"Note: Recent trend shift ({old} to {new}, {shift_type}).")

    return " ".join(parts)


def apply_signal_adjustments(
    base_confidence: float,
    base_risk: str,
    active_signals: list,
) -> SignalAdjustment:
    """
    Apply all signal adjustments to a forecast point.

    Orchestrates:
      1. compute_signal_penalty() → confidence reduction
      2. compute_risk_elevation() → risk tier elevation
      3. build_signal_explanation() → audit trail text

    Returns SignalAdjustment with all adjusted values.
    """
    # 1. Confidence penalty
    penalty, penalty_details = compute_signal_penalty(active_signals)
    final_confidence = round(
        max(CONFIDENCE_MIN, min(CONFIDENCE_MAX, base_confidence - penalty)),
        4,
    )

    # 2. Risk elevation
    adjusted_risk, risk_elevated, elevating_source = compute_risk_elevation(
        base_risk,
        active_signals,
    )

    # Find elevating signal's severity for explanation
    elevating_severity = None
    if elevating_source:
        for sig in active_signals:
            if _get_signal_source(sig) == elevating_source:
                elevating_severity = _get_signal_severity(sig)
                break

    # 3. Explanation
    explanation_suffix = build_signal_explanation(
        base_confidence=base_confidence,
        signal_penalty=penalty,
        final_confidence=final_confidence,
        penalty_details=penalty_details,
        risk_elevated=risk_elevated,
        original_risk=base_risk,
        adjusted_risk=adjusted_risk,
        elevating_source=elevating_source,
        elevating_severity=elevating_severity,
        active_signals=active_signals,
    )

    return SignalAdjustment(
        adjusted_confidence=final_confidence,
        base_confidence=base_confidence,
        signal_penalty=penalty,
        adjusted_risk=adjusted_risk,
        risk_elevated=risk_elevated,
        original_risk=base_risk,
        explanation_suffix=explanation_suffix,
        penalty_details=penalty_details,
    )


# Signal accessor helpers — handle both SignalEvent ORM objects and dicts
def _get_signal_source(sig) -> str:
    if hasattr(sig, "source"):
        return sig.source
    if isinstance(sig, dict):
        return sig.get("source", "")
    return ""


def _get_signal_severity(sig) -> float:
    if hasattr(sig, "severity"):
        return sig.severity
    if isinstance(sig, dict):
        return sig.get("severity", 0.0)
    return 0.0


def _get_signal_payload(sig) -> dict:
    if hasattr(sig, "payload"):
        raw = sig.payload
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return {}
        if isinstance(raw, dict):
            return raw
    if isinstance(sig, dict):
        return sig.get("payload", {})
    return {}


def compute_forecast_demand(
    avg_demand: float,
    trend_factor: float,
    season_factor: float,
) -> float:
    """
    Compute pure demand forecast.

    forecast_demand = avg_demand × trend_factor × season_factor

    No supply contamination — demand is demand.
    """
    return round(avg_demand * trend_factor * season_factor, 2)


def build_explanation(
    product: str,
    horizon: int,
    avg_demand: float,
    forecast_demand: float,
    trend_factor: float,
    trend: str,
    season_factor: float,
    season: str,
    supply_risk: str,
    reliability: float,
    confidence: float,
    simulation_count: int,
) -> str:
    """
    Build human-readable forecast explanation.

    Decomposes the forecast into its factors so a supply chain manager
    can understand exactly why this number was produced.
    """
    parts = [
        f"Forecast for {product} at horizon {horizon}:",
        f"base demand {avg_demand:,.1f} (EWMA α=0.3)",
        f"× trend {trend_factor} ({trend}",
    ]

    if trend == "Rising":
        parts[-1] += f" +{TREND_GROWTH_PER_HORIZON*100:.0f}%/horizon)"
    elif trend == "Falling":
        parts[-1] += f" -{TREND_DECLINE_PER_HORIZON*100:.0f}%/horizon)"
    else:
        parts[-1] += ")"

    parts.append(f"× season {season_factor} ({season})")
    parts.append(f"= {forecast_demand:,.1f}.")
    parts.append(f"Supply risk: {supply_risk} (reliability {reliability:.1f}%).")
    parts.append(
        f"Confidence: {confidence:.2f} ({simulation_count} simulations, {trend} trend)."
    )

    return " ".join(parts)


def generate_forecast_point(
    inputs: ForecastInput,
    horizon: int,
    active_signals: list | None = None,
) -> ForecastPoint:
    """
    Generate a single forecast point for one horizon.

    If active_signals is provided (E4), applies signal adjustments:
      - Confidence: reduced by severity-proportional penalties
      - Risk: elevated if critical signals exist (severity > 0.5)
      - Explanation: augmented with signal audit trail
    """
    trend_f = compute_trend_factor(inputs.demand_trend, horizon)
    season_f = compute_season_factor(inputs.season_mode)
    base_risk = classify_supply_risk(inputs.supplier_reliability)
    base_conf = compute_confidence(
        inputs.simulation_count,
        horizon,
        inputs.demand_trend,
        inputs.supplier_reliability,
    )
    demand = compute_forecast_demand(inputs.avg_demand, trend_f, season_f)

    # E4: Apply signal adjustments if signals are present
    final_conf = base_conf
    final_risk = base_risk
    signal_penalty = 0.0
    signal_explanation = ""

    if active_signals:
        adj = apply_signal_adjustments(base_conf, base_risk, active_signals)
        final_conf = adj.adjusted_confidence
        final_risk = adj.adjusted_risk
        signal_penalty = adj.signal_penalty
        signal_explanation = adj.explanation_suffix

    explanation = build_explanation(
        product="",  # filled by caller
        horizon=horizon,
        avg_demand=inputs.avg_demand,
        forecast_demand=demand,
        trend_factor=trend_f,
        trend=inputs.demand_trend,
        season_factor=season_f,
        season=inputs.season_mode,
        supply_risk=final_risk,
        reliability=inputs.supplier_reliability,
        confidence=final_conf,
        simulation_count=inputs.simulation_count,
    )

    # Append signal explanation if present
    if signal_explanation:
        explanation = explanation + " " + signal_explanation

    return ForecastPoint(
        horizon=horizon,
        forecast_demand=demand,
        trend_factor=trend_f,
        season_factor=season_f,
        supply_risk=final_risk,
        confidence=final_conf,
        explanation=explanation,
        base_confidence=base_conf,
        signal_penalty=signal_penalty,
    )


# ---------------------------------------------------------------------------
# ForecastEngine — orchestrates twin read + computation + persistence
# ---------------------------------------------------------------------------


class ForecastEngine:
    """
    Orchestrates forecast generation from Digital Twin state.

    Usage:
        engine = ForecastEngine(db)
        result = engine.generate(twin_id=1, product="Widget-A", horizons=[1,3,5])
    """

    def __init__(self, db: Session):
        self.db = db
        self.twin_mgr = TwinManager(db)

    def generate(
        self,
        twin_id: int,
        product: str,
        horizons: list[int],
    ) -> dict | None:
        """
        Generate forecasts for a product at specified horizons.

        Returns None if twin or product not found.
        Returns dict with source_state + forecast points.
        """
        twin = self.twin_mgr.get_twin(twin_id)
        if not twin:
            return None

        # Find product state
        product_state = None
        for ps in twin.product_states:
            if ps.product_name == product:
                product_state = ps
                break

        if not product_state:
            return None

        # Build forecast input from twin state
        inputs = ForecastInput(
            avg_demand=product_state.avg_demand,
            demand_trend=product_state.demand_trend,
            simulation_count=product_state.simulation_count,
            season_mode=(
                twin.market_state.season_mode if twin.market_state else "Normal"
            ),
            supplier_reliability=(
                twin.supplier_state.reliability_score if twin.supplier_state else 100.0
            ),
        )

        # E4: Fetch active signals BEFORE generating forecast points
        # so signals can influence confidence, risk, and explanations.
        active_signals = []
        try:
            from signals.engine import SignalEngine

            sig_engine = SignalEngine(self.db)
            active_signals = sig_engine.get_active_signals_for_product(
                twin_id=twin_id,
                product=product,
                limit=10,
            )
        except Exception:
            pass  # Non-blocking — forecast works without signals

        # Generate forecast points (with signal adjustments if available)
        points = []
        for h in horizons:
            point = generate_forecast_point(
                inputs,
                h,
                active_signals=active_signals or None,
            )
            # Fix explanation with actual product name
            point.explanation = point.explanation.replace(
                "Forecast for  at", f"Forecast for {product} at"
            )
            points.append(point)

            # Persist forecast record (stores signal-adjusted values)
            record = ForecastRecord(
                twin_id=twin_id,
                product_name=product,
                horizon=h,
                forecast_demand=point.forecast_demand,
                trend_factor=point.trend_factor,
                season_factor=point.season_factor,
                supply_risk=point.supply_risk,
                confidence=point.confidence,
                explanation=point.explanation,
                source_avg_demand=inputs.avg_demand,
                source_trend=inputs.demand_trend,
                source_season=inputs.season_mode,
                source_reliability=inputs.supplier_reliability,
            )
            self.db.add(record)

        self.db.commit()

        return {
            "twin_id": twin_id,
            "product": product,
            "source_state": {
                "avg_demand": inputs.avg_demand,
                "demand_trend": inputs.demand_trend,
                "simulation_count": inputs.simulation_count,
                "season": inputs.season_mode,
                "supplier_reliability": inputs.supplier_reliability,
            },
            "forecasts": points,
            "active_signals": active_signals,
        }

    def list_records(
        self,
        twin_id: int,
        product: str | None = None,
        limit: int = 20,
    ) -> list[ForecastRecord]:
        """List persisted forecast records for a twin."""
        from sqlalchemy import select

        stmt = (
            select(ForecastRecord)
            .where(ForecastRecord.twin_id == twin_id)
            .order_by(ForecastRecord.created_at.desc())
        )
        if product:
            stmt = stmt.where(ForecastRecord.product_name == product)
        stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt).all())

    def get_summary(self, twin_id: int) -> list[dict] | None:
        """
        Get latest horizon-1 forecast summary for all products in a twin.

        Read-only — does NOT generate new forecasts.
        Returns None if twin not found.
        """
        twin = self.twin_mgr.get_twin(twin_id)
        if not twin:
            return None

        summaries = []
        for ps in twin.product_states:
            # Find most recent horizon-1 forecast for this product
            from sqlalchemy import select

            stmt = (
                select(ForecastRecord)
                .where(
                    ForecastRecord.twin_id == twin_id,
                    ForecastRecord.product_name == ps.product_name,
                    ForecastRecord.horizon == 1,
                )
                .order_by(ForecastRecord.created_at.desc())
                .limit(1)
            )
            record = self.db.scalars(stmt).first()

            summaries.append(
                {
                    "product": ps.product_name,
                    "avg_demand": ps.avg_demand,
                    "demand_trend": ps.demand_trend,
                    "latest_forecast": (
                        {
                            "forecast_demand": record.forecast_demand,
                            "confidence": record.confidence,
                            "supply_risk": record.supply_risk,
                            "generated_at": (
                                record.created_at.isoformat()
                                if record.created_at
                                else None
                            ),
                        }
                        if record
                        else None
                    ),
                }
            )

        return summaries
