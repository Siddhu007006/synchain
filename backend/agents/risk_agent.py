"""
RiskAgent — Multi-factor supply chain risk assessment.

Upgrade from L2 (single-variable threshold) to L2+ (multi-factor scoring).

Risk Score Formula (documented):
─────────────────────────────────
  risk_score = (delay_score × 0.50)
             + (supply_score × 0.30)
             + (market_score × 0.20)

  delay_score (supplier_delay in days):
    delay > 7    → 1.0  (critical delay)
    delay > 5    → 0.8  (high delay)
    delay > 3    → 0.5  (moderate delay)
    delay > 1    → 0.3  (minor delay)
    delay <= 1   → 0.1  (negligible)

  supply_score (supply_status):
    Low    → 0.9  (scarcity drives risk)
    Medium → 0.5
    High   → 0.1

  market_score (market_trend):
    Negative → 0.8  (declining market adds pressure)
    Neutral  → 0.4
    Positive → 0.2  (healthy market reduces risk)

  Risk Classification:
    risk_score >= 0.65 → "High"
    risk_score >= 0.35 → "Medium"
    risk_score <  0.35 → "Low"

Confidence Formula:
─────────────────────────────────
  C_risk = 0.50 (base)
         + factor_agreement   (0.00–0.30)
         + boundary_distance  (0.00–0.20)

  factor_agreement:
    All 3 factors point same direction → 0.30
    2 of 3 agree                       → 0.20
    Mixed signals                      → 0.05

  boundary_distance:
    |risk_score - nearest_boundary| > 0.20 → 0.20
    |risk_score - nearest_boundary| > 0.10 → 0.10
    Otherwise                              → 0.00
─────────────────────────────────
"""

from agents.base_agent import AgentStepResult, BaseAgent

# --- Factor scoring tables ---
_DELAY_SCORES = [
    (7, 1.0),
    (5, 0.8),
    (3, 0.5),
    (1, 0.3),
]
_DELAY_DEFAULT = 0.1

_SUPPLY_SCORES = {"Low": 0.9, "Medium": 0.5, "High": 0.1}
_MARKET_SCORES = {"Negative": 0.8, "Neutral": 0.4, "Positive": 0.2}

# Weights
_W_DELAY = 0.50
_W_SUPPLY = 0.30
_W_MARKET = 0.20

# Classification thresholds
_HIGH_THRESHOLD = 0.65
_MEDIUM_THRESHOLD = 0.35


def _delay_score(delay: float) -> float:
    for threshold, score in _DELAY_SCORES:
        if delay > threshold:
            return score
    return _DELAY_DEFAULT


def _classify(risk_score: float) -> str:
    if risk_score >= _HIGH_THRESHOLD:
        return "High"
    elif risk_score >= _MEDIUM_THRESHOLD:
        return "Medium"
    return "Low"


def _factor_direction(
    score: float, thresholds: tuple[float, float] = (0.6, 0.4)
) -> str:
    """Classify a factor score as 'high_risk', 'medium', or 'low_risk'."""
    if score >= thresholds[0]:
        return "high_risk"
    elif score <= thresholds[1]:
        return "low_risk"
    return "medium"


class RiskAgent(BaseAgent):
    """Multi-factor supply chain risk assessment using delay, supply status, and market trend."""

    @property
    def name(self) -> str:
        return "RiskAgent"

    def run(
        self,
        supplier_delay: float,
        supply_status: str = "Medium",
        market_trend: str = "Neutral",
    ) -> AgentStepResult:
        input_summary = {
            "supplier_delay_days": supplier_delay,
            "supply_status": supply_status,
            "market_trend": market_trend,
        }

        def _compute(supplier_delay, supply_status, market_trend):
            d_score = _delay_score(supplier_delay)
            s_score = _SUPPLY_SCORES.get(supply_status, 0.5)
            m_score = _MARKET_SCORES.get(market_trend, 0.4)

            risk_score = round(
                (d_score * _W_DELAY) + (s_score * _W_SUPPLY) + (m_score * _W_MARKET),
                3,
            )
            risk_level = _classify(risk_score)
            return risk_level, risk_score, d_score, s_score, m_score

        (risk_level, risk_score, d_score, s_score, m_score), elapsed_ms = (
            self._timed_execute(
                _compute,
                supplier_delay=supplier_delay,
                supply_status=supply_status,
                market_trend=market_trend,
            )
        )

        # --- Confidence formula ---
        base_confidence = 0.50

        # Factor agreement: how many factors point the same direction
        directions = [
            _factor_direction(d_score),
            _factor_direction(s_score),
            _factor_direction(m_score),
        ]
        unique_directions = set(directions)
        if len(unique_directions) == 1:
            factor_agreement = 0.30  # All agree
        elif (
            len(
                [
                    d
                    for d in directions
                    if d == max(set(directions), key=directions.count)
                ]
            )
            >= 2
        ):
            factor_agreement = 0.20  # 2 of 3 agree
        else:
            factor_agreement = 0.05  # Mixed signals

        # Boundary distance
        boundaries = [_HIGH_THRESHOLD, _MEDIUM_THRESHOLD]
        min_distance = min(abs(risk_score - b) for b in boundaries)
        if min_distance > 0.20:
            boundary_distance = 0.20
        elif min_distance > 0.10:
            boundary_distance = 0.10
        else:
            boundary_distance = 0.00

        confidence = round(
            min(base_confidence + factor_agreement + boundary_distance, 1.0), 2
        )

        # --- Explanation ---
        factor_parts = [
            f"delay {supplier_delay:.0f}d (score {d_score})",
            f"supply '{supply_status}' (score {s_score})",
            f"market '{market_trend}' (score {m_score})",
        ]
        explanation = (
            f"Multi-factor risk score {risk_score:.2f} -> '{risk_level}' "
            f"(thresholds: >=0.65=High, >=0.35=Medium, <0.35=Low). "
            f"Factors: {', '.join(factor_parts)}. "
            f"Confidence {confidence:.0%}: "
            f"{'all factors agree' if factor_agreement >= 0.30 else 'most factors agree' if factor_agreement >= 0.20 else 'mixed signals'}, "
            f"{'well clear of boundaries' if boundary_distance >= 0.20 else 'near a classification boundary' if boundary_distance == 0.00 else 'moderate distance from boundaries'}."
        )

        return AgentStepResult(
            agent_name=self.name,
            input_summary=input_summary,
            output_data={"risk_level": risk_level, "risk_score": round(risk_score, 2)},
            confidence=confidence,
            explanation=explanation,
            execution_ms=elapsed_ms,
            status="success",
        )
