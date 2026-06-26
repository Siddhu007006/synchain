"""
ScenarioAgent — Runs predefined what-if disruption scenarios.

Architecture Note:
─────────────────────────────────
  ScenarioAgent is an ORCHESTRATOR, not a step agent.

  It does NOT inherit BaseAgent because:
    - BaseAgent.run() → AgentStepResult (single agent envelope)
    - ScenarioAgent.run() → list[dict] (multiple scenario comparisons)
    - ScenarioAgent doesn't produce its own output — it re-runs the
      entire 4-agent pipeline with modified inputs.

  This is intentional: ScenarioAgent is a meta-agent that coordinates
  multiple full pipeline executions, not a specialist decision-maker.

Takes a base SimulationInput and runs 4 disruption scenarios through the
existing DecisionAgent pipeline, producing comparison results with impact deltas.

Scenarios:
─────────────────────────────────
  1. Demand Surge:       demand × 1.20 (+20%)
  2. Supplier Shutdown:  supplier_delay → 10 days
  3. Inventory Shortage: stock × 0.70 (-30%)
  4. Transport Delay:    supplier_delay × 1.50
─────────────────────────────────

Each scenario returns:
  - scenario_name: human-readable label
  - scenario_description: what was changed
  - modified_input: the tweaked SimulationInput
  - result: full SimulationResult from running the pipeline
  - impact: delta summary (risk_change, demand_change, inventory_change, confidence_change, recommendation_changed)
"""

from schemas import SimulationInput, SimulationResult

SCENARIO_DEFINITIONS = [
    {
        "name": "Demand Surge",
        "description": "Demand increases by 20% due to unexpected market spike",
        "apply": lambda inp: _set(inp, demand=inp.demand * 1.20),
    },
    {
        "name": "Supplier Shutdown",
        "description": "Primary supplier shuts down, delivery delay jumps to 10 days",
        "apply": lambda inp: _set(inp, supplier_delay=10.0),
    },
    {
        "name": "Inventory Shortage",
        "description": "Current stock drops by 30% due to quality issues or theft",
        "apply": lambda inp: _set(inp, stock=inp.stock * 0.70),
    },
    {
        "name": "Transport Delay",
        "description": "Transport disruption increases supplier delay by 50%",
        "apply": lambda inp: _set(inp, supplier_delay=inp.supplier_delay * 1.50),
    },
]


def _set(inp: SimulationInput, **overrides) -> SimulationInput:
    """Create a copy of the input with specific field overrides."""
    data = inp.model_dump()
    data.update(overrides)
    return SimulationInput(**data)


def _compute_impact(
    base: SimulationResult,
    scenario: SimulationResult,
) -> dict:
    """Compute the delta between base and scenario results."""
    demand_change = scenario.demand_forecast - base.demand_forecast
    inventory_change = scenario.recommended_inventory - base.recommended_inventory
    confidence_change = scenario.overall_confidence - base.overall_confidence

    # Risk ordinal comparison
    risk_order = {"Low": 0, "Medium": 1, "High": 2}
    base_risk_val = risk_order.get(base.risk, 1)
    scenario_risk_val = risk_order.get(scenario.risk, 1)
    risk_delta = scenario_risk_val - base_risk_val

    if risk_delta > 0:
        risk_change = f"+{risk_delta} level{'s' if risk_delta > 1 else ''} ({base.risk} -> {scenario.risk})"
    elif risk_delta < 0:
        risk_change = f"{risk_delta} level{'s' if abs(risk_delta) > 1 else ''} ({base.risk} -> {scenario.risk})"
    else:
        risk_change = f"No change ({scenario.risk})"

    recommendation_changed = (
        base.selected_warehouse != scenario.selected_warehouse
        or base.route != scenario.route
        or base.risk != scenario.risk
    )

    return {
        "demand_change": round(demand_change, 1),
        "inventory_change": round(inventory_change, 1),
        "confidence_change": round(confidence_change, 2),
        "risk_change": risk_change,
        "recommendation_changed": recommendation_changed,
        "warehouse_changed": base.selected_warehouse != scenario.selected_warehouse,
        "route_changed": base.route != scenario.route,
    }


class ScenarioAgent:
    """Runs 4 predefined disruption scenarios and compares results to the base simulation."""

    def run(
        self,
        base_input: SimulationInput,
        base_result: SimulationResult,
        run_pipeline,
    ) -> list[dict]:
        """
        Run all scenarios and return comparison results.

        Args:
            base_input: The original simulation input.
            base_result: The original simulation result.
            run_pipeline: Callable that takes SimulationInput and returns SimulationResult.

        Returns:
            List of scenario comparison dicts.
        """
        comparisons = []

        for scenario_def in SCENARIO_DEFINITIONS:
            modified_input = scenario_def["apply"](base_input)
            scenario_result = run_pipeline(modified_input)
            impact = _compute_impact(base_result, scenario_result)

            comparisons.append(
                {
                    "scenario_name": scenario_def["name"],
                    "scenario_description": scenario_def["description"],
                    "modified_input": modified_input.model_dump(),
                    "result": {
                        "demand_forecast": scenario_result.demand_forecast,
                        "recommended_inventory": scenario_result.recommended_inventory,
                        "selected_warehouse": scenario_result.selected_warehouse,
                        "route": scenario_result.route,
                        "risk": scenario_result.risk,
                        "overall_confidence": scenario_result.overall_confidence,
                        "strategy": scenario_result.strategy,
                    },
                    "impact": impact,
                }
            )

        return comparisons
