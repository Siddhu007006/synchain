"""
InventoryAgent — Recommends optimal inventory level with safety margin.

Design Decision: Stock in Confidence vs. Calculation
─────────────────────────────────────────────────────
  The recommendation formula is:
    recommended_inventory = predicted_demand × safety_factor

  Current stock (stock) is NOT used in this formula. This is intentional:
    - recommended_inventory is a TARGET LEVEL, not an ORDER QUANTITY
    - The target is demand-driven: "how much should we have?"
    - The delta (how much to order) = recommended_inventory - stock
    - This delta is shown in the UI as "Inventory Delta"

  Stock IS used in the CONFIDENCE formula (demand_gap_clarity) because:
    - A large gap between stock and predicted_demand = clear decision → high confidence
    - Stock ≈ demand = ambiguous whether to restock → low confidence

  Stock IS used in the EXPLANATION (shows delta above/below current stock).

Confidence Formula (documented):
─────────────────────────────────
  C_inventory = 0.50                          # base: deterministic safety-factor math
              + supply_clarity                # 0.00–0.25 based on supply_status strength
              + demand_gap_clarity            # 0.00–0.25 based on stock-to-demand ratio

  supply_clarity:
    Low  → 0.25  (clear signal: constrained supply requires aggressive buffer)
    High → 0.20  (clear signal: abundant supply allows lean inventory)
    Medium → 0.10  (ambiguous: default buffer, less decisive)

  demand_gap_clarity:
    |stock - predicted_demand| / predicted_demand > 0.5  → 0.25  (large gap, clear decision)
    |stock - predicted_demand| / predicted_demand > 0.2  → 0.15  (moderate gap)
    Otherwise                                            → 0.05  (stock ≈ demand, unclear)

  Result range: [0.65, 1.00]
─────────────────────────────────
"""

from agents.base_agent import AgentStepResult, BaseAgent

SUPPLY_SAFETY_FACTORS = {
    "High": 1.05,
    "Medium": 1.10,
    "Low": 1.25,
}

_SUPPLY_CONFIDENCE = {"Low": 0.25, "High": 0.20, "Medium": 0.10}


class InventoryAgent(BaseAgent):
    """Recommends optimal inventory level, adjusting safety margin by supply availability."""

    @property
    def name(self) -> str:
        return "InventoryAgent"

    def run(
        self,
        predicted_demand: float,
        stock: float,
        supply_status: str = "Medium",
    ) -> AgentStepResult:
        input_summary = {
            "predicted_demand": predicted_demand,
            "current_stock": stock,
            "supply_status": supply_status,
        }

        def _compute(predicted_demand, supply_status):
            safety_factor = SUPPLY_SAFETY_FACTORS.get(supply_status, 1.10)
            return round(predicted_demand * safety_factor, 2), safety_factor

        (recommended_inventory, safety_factor), elapsed_ms = self._timed_execute(
            _compute,
            predicted_demand=predicted_demand,
            supply_status=supply_status,
        )

        # --- Confidence formula ---
        base_confidence = 0.50
        supply_clarity = _SUPPLY_CONFIDENCE.get(supply_status, 0.10)

        gap_ratio = abs(stock - predicted_demand) / max(predicted_demand, 1)
        if gap_ratio > 0.5:
            demand_gap_clarity = 0.25
        elif gap_ratio > 0.2:
            demand_gap_clarity = 0.15
        else:
            demand_gap_clarity = 0.05

        confidence = round(
            min(base_confidence + supply_clarity + demand_gap_clarity, 1.0), 2
        )

        # --- Explanation ---
        delta = recommended_inventory - stock
        delta_direction = "above" if delta > 0 else "below"

        explanation = (
            f"Supply status '{supply_status}' → safety factor {safety_factor}×. "
            f"Recommended {recommended_inventory:,.0f} units "
            f"({abs(delta):,.0f} {delta_direction} current stock of {stock:,.0f}). "
            f"Confidence {confidence:.0%}: supply signal {'clear' if supply_clarity >= 0.20 else 'ambiguous'}"
            f", stock-demand gap {'large' if demand_gap_clarity >= 0.25 else 'moderate' if demand_gap_clarity >= 0.15 else 'small'}."
        )

        return AgentStepResult(
            agent_name=self.name,
            input_summary=input_summary,
            output_data={"recommended_inventory": recommended_inventory},
            confidence=confidence,
            explanation=explanation,
            execution_ms=elapsed_ms,
            status="success",
        )
