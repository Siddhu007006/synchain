"""
DemandAgent — Forecasts future demand using base trend, market conditions, and seasonality.

Confidence Formula (documented):
─────────────────────────────────
  C_demand = 0.50                          # base: multiplicative model is deterministic
           + market_signal_strength        # 0.00–0.25 based on market_trend clarity
           + seasonal_signal_strength      # 0.00–0.25 based on season clarity

  market_signal_strength:
    Positive / Negative → 0.25  (strong directional signal)
    Neutral             → 0.10  (no signal is itself informative, but weaker)

  seasonal_signal_strength:
    Festival / Off-season → 0.25  (clear seasonal pattern)
    Normal                → 0.10  (baseline, less informative)

  Result range: [0.70, 1.00]
─────────────────────────────────
"""

from agents.base_agent import AgentStepResult, BaseAgent

DEFAULT_TREND_FACTOR = 1.2

MARKET_MULTIPLIERS = {
    "Positive": 1.1,
    "Neutral": 1.0,
    "Negative": 0.9,
}

SEASON_MULTIPLIERS = {
    "Festival": 1.3,
    "Normal": 1.0,
    "Off-season": 0.8,
}

# Confidence signal strengths
_MARKET_CONFIDENCE = {"Positive": 0.25, "Negative": 0.25, "Neutral": 0.10}
_SEASON_CONFIDENCE = {"Festival": 0.25, "Off-season": 0.25, "Normal": 0.10}


class DemandAgent(BaseAgent):
    """Forecasts future demand using base trend, market conditions, and seasonality."""

    @property
    def name(self) -> str:
        return "DemandAgent"

    def run(
        self,
        demand: float,
        market_trend: str = "Neutral",
        season: str = "Normal",
        trend_factor: float = DEFAULT_TREND_FACTOR,
    ) -> AgentStepResult:
        input_summary = {
            "demand": demand,
            "market_trend": market_trend,
            "season": season,
        }

        def _compute(demand, market_trend, season, trend_factor):
            market_mult = MARKET_MULTIPLIERS.get(market_trend, 1.0)
            season_mult = SEASON_MULTIPLIERS.get(season, 1.0)
            return round(demand * trend_factor * market_mult * season_mult, 2)

        predicted_demand, elapsed_ms = self._timed_execute(
            _compute,
            demand=demand,
            market_trend=market_trend,
            season=season,
            trend_factor=trend_factor,
        )

        # --- Confidence formula ---
        base_confidence = 0.50
        market_signal = _MARKET_CONFIDENCE.get(market_trend, 0.10)
        season_signal = _SEASON_CONFIDENCE.get(season, 0.10)
        confidence = round(min(base_confidence + market_signal + season_signal, 1.0), 2)

        # --- Explanation ---
        market_mult = MARKET_MULTIPLIERS.get(market_trend, 1.0)
        season_mult = SEASON_MULTIPLIERS.get(season, 1.0)

        parts = [f"Base demand {demand:,.0f} × trend factor {trend_factor}"]
        if market_trend != "Neutral":
            parts.append(f"{market_trend.lower()} market ({market_mult}×)")
        if season != "Normal":
            parts.append(f"{season.lower()} season ({season_mult}×)")
        parts.append(f"→ forecast {predicted_demand:,.0f} units")

        explanation = ". ".join(
            [
                " + ".join(parts),
                f"Confidence {confidence:.0%}: market signal {'strong' if market_signal >= 0.25 else 'weak'}"
                f", seasonal signal {'strong' if season_signal >= 0.25 else 'weak'}",
            ]
        )

        return AgentStepResult(
            agent_name=self.name,
            input_summary=input_summary,
            output_data={"predicted_demand": predicted_demand},
            confidence=confidence,
            explanation=explanation,
            execution_ms=elapsed_ms,
            status="success",
        )
