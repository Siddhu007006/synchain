"""
DecisionAgent — Orchestrates the multi-agent pipeline and produces the combined decision.

Weighted Overall Confidence Formula (documented):
─────────────────────────────────────────────────
  Weights reflect business impact — RiskAgent gets highest weight because
  an incorrect risk assessment has the most severe consequences:

    DemandAgent:     0.25  (demand drives inventory, but is a forecast)
    InventoryAgent:  0.20  (inventory recommendation follows from demand)
    LogisticsAgent:  0.15  (warehouse selection is binary, less nuanced)
    RiskAgent:       0.40  (risk assessment directly affects safety stock and strategy)

    overall_confidence = Σ (weight_i × confidence_i)

  Example:
    Demand=0.85, Inventory=0.80, Logistics=0.92, Risk=0.60
    = 0.25×0.85 + 0.20×0.80 + 0.15×0.92 + 0.40×0.60
    = 0.2125 + 0.16 + 0.138 + 0.24
    = 0.7505 → 75%
─────────────────────────────────────────────────
"""

from agents.base_agent import AgentStepResult, BaseAgent
from agents.demand_agent import DemandAgent
from agents.explanation_agent import ExplanationAgent
from agents.inventory_agent import InventoryAgent
from agents.logistics_agent import LogisticsAgent
from agents.risk_agent import RiskAgent
from schemas import AgentBreakdownItem, SimulationInput, SimulationResult

# Weights: RiskAgent has highest weight (0.40) because incorrect risk
# assessment has the most severe business consequences.
AGENT_WEIGHTS = {
    "DemandAgent": 0.25,
    "InventoryAgent": 0.20,
    "LogisticsAgent": 0.15,
    "RiskAgent": 0.40,
}


def _build_strategy(
    risk_level: str,
    selected_warehouse: str,
    recommended_inventory: float,
    market_trend: str,
    season: str,
    supply_status: str,
) -> str:
    """Generate a contextual strategy string from combined agent outputs."""
    risk_actions = {
        "High": "Diversify suppliers immediately and increase safety stock.",
        "Medium": "Monitor supplier performance and maintain buffer inventory.",
        "Low": "Optimize distribution for cost efficiency.",
    }
    action = risk_actions.get(risk_level, "Review supply chain status.")

    context_notes = []
    if market_trend == "Positive":
        context_notes.append("rising market demand")
    elif market_trend == "Negative":
        context_notes.append("declining market demand")

    if season == "Festival":
        context_notes.append("festival season surge")
    elif season == "Off-season":
        context_notes.append("off-season slowdown")

    if supply_status == "Low":
        context_notes.append("constrained supply")

    context_str = ""
    if context_notes:
        context_str = f" Accounting for {', '.join(context_notes)}."

    return (
        f"{action}"
        f" Route through {selected_warehouse} with target inventory of {recommended_inventory:.0f} units."
        f"{context_str}"
    )


def _weighted_confidence(steps: list[AgentStepResult]) -> float:
    """Compute weighted overall confidence using business-impact weights."""
    total_weight = 0.0
    weighted_sum = 0.0
    for step in steps:
        w = AGENT_WEIGHTS.get(step.agent_name, 0.20)
        weighted_sum += w * step.confidence
        total_weight += w
    return round(weighted_sum / max(total_weight, 0.01), 2)


class DecisionAgent(BaseAgent):
    """Final brain — orchestrates all specialist agents and produces the combined decision."""

    def __init__(self) -> None:
        self._demand = DemandAgent()
        self._inventory = InventoryAgent()
        self._logistics = LogisticsAgent()
        self._risk = RiskAgent()
        self._explanation = ExplanationAgent()

    @property
    def name(self) -> str:
        return "DecisionAgent"

    def run(self, payload: SimulationInput) -> SimulationResult:
        # Step 1 — Run each specialist agent (returns AgentStepResult)
        demand_step = self._demand.run(
            demand=payload.demand,
            market_trend=payload.market_trend,
            season=payload.season,
        )

        inventory_step = self._inventory.run(
            predicted_demand=demand_step.output_data["predicted_demand"],
            stock=payload.stock,
            supply_status=payload.supply_status,
        )

        logistics_step = self._logistics.run(
            warehouse=payload.warehouse,
            stock=payload.stock,
            predicted_demand=demand_step.output_data["predicted_demand"],
        )

        risk_step = self._risk.run(
            supplier_delay=payload.supplier_delay,
            supply_status=payload.supply_status,
            market_trend=payload.market_trend,
        )

        # Step 2 — Collect all steps
        agent_steps = [demand_step, inventory_step, logistics_step, risk_step]

        # Step 3 — Compute weighted overall confidence
        overall_confidence = _weighted_confidence(agent_steps)

        # Step 4 — Build strategy
        strategy = _build_strategy(
            risk_level=risk_step.output_data["risk_level"],
            selected_warehouse=logistics_step.output_data["selected_warehouse"],
            recommended_inventory=inventory_step.output_data["recommended_inventory"],
            market_trend=payload.market_trend,
            season=payload.season,
            supply_status=payload.supply_status,
        )

        # Step 5 — Generate explanation narrative
        explanation = self._explanation.run(
            agent_steps=agent_steps,
            overall_confidence=overall_confidence,
            strategy=strategy,
        )

        # Step 6 — Build agent breakdown for the response
        agent_breakdown = [
            AgentBreakdownItem(
                agent_name=s.agent_name,
                input_summary=s.input_summary,
                output_data=s.output_data,
                confidence=s.confidence,
                explanation=s.explanation,
                execution_ms=s.execution_ms,
                status=s.status,
            )
            for s in agent_steps
        ]

        return SimulationResult(
            demand_forecast=demand_step.output_data["predicted_demand"],
            recommended_inventory=inventory_step.output_data["recommended_inventory"],
            selected_warehouse=logistics_step.output_data["selected_warehouse"],
            route=logistics_step.output_data["route"],
            risk=risk_step.output_data["risk_level"],
            strategy=strategy,
            agent_breakdown=agent_breakdown,
            overall_confidence=overall_confidence,
            explanation=explanation,
        )
