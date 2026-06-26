"""
ExplanationAgent — Synthesizes all agent step results into a human-readable narrative.

This agent does NOT use LLMs. It uses template-based synthesis to produce a coherent
summary of the multi-agent decision pipeline.

The narrative covers:
  1. Overall confidence assessment
  2. Demand forecast rationale
  3. Inventory recommendation context
  4. Logistics decision
  5. Risk assessment
  6. Actionable conclusion
"""

from agents.base_agent import AgentStepResult


def _confidence_label(c: float) -> str:
    if c >= 0.85:
        return "very high"
    elif c >= 0.70:
        return "high"
    elif c >= 0.55:
        return "moderate"
    else:
        return "low"


class ExplanationAgent:
    """Generates a human-readable narrative from all agent step results."""

    @property
    def name(self) -> str:
        return "ExplanationAgent"

    def run(
        self,
        agent_steps: list[AgentStepResult],
        overall_confidence: float,
        strategy: str,
    ) -> str:
        """
        Produce a multi-sentence explanation of the pipeline decision.

        Parameters
        ----------
        agent_steps : list[AgentStepResult]
            The step results from all specialist agents.
        overall_confidence : float
            The weighted overall confidence score.
        strategy : str
            The strategy string from DecisionAgent.

        Returns
        -------
        str
            A human-readable narrative paragraph.
        """
        # Index steps by agent name for easy lookup
        steps = {s.agent_name: s for s in agent_steps}
        agent_count = len(agent_steps)
        conf_label = _confidence_label(overall_confidence)

        parts = []

        # Opening: overall assessment
        parts.append(
            f"Based on analysis by {agent_count} specialist agents "
            f"(overall confidence: {overall_confidence:.0%}, {conf_label}):"
        )

        # Demand
        demand_step = steps.get("DemandAgent")
        if demand_step:
            forecast = demand_step.output_data.get("predicted_demand", 0)
            inp = demand_step.input_summary
            parts.append(
                f"Demand is projected at {forecast:,.0f} units, "
                f"driven by {inp.get('market_trend', 'neutral').lower()} market conditions "
                f"and {inp.get('season', 'normal').lower()} seasonal patterns "
                f"(confidence: {demand_step.confidence:.0%})."
            )

        # Inventory
        inv_step = steps.get("InventoryAgent")
        if inv_step:
            rec = inv_step.output_data.get("recommended_inventory", 0)
            supply = inv_step.input_summary.get("supply_status", "medium")
            parts.append(
                f"Given {supply.lower()} supply availability, "
                f"recommended inventory is {rec:,.0f} units with appropriate safety buffer "
                f"(confidence: {inv_step.confidence:.0%})."
            )

        # Logistics
        log_step = steps.get("LogisticsAgent")
        if log_step:
            wh = log_step.output_data.get("selected_warehouse", "?")
            route = log_step.output_data.get("route", "?")
            parts.append(
                f"Optimal routing is through warehouse {wh} via route {route} "
                f"(confidence: {log_step.confidence:.0%})."
            )

        # Risk
        risk_step = steps.get("RiskAgent")
        if risk_step:
            risk = risk_step.output_data.get("risk_level", "?")
            delay = risk_step.input_summary.get("supplier_delay_days", 0)
            parts.append(
                f"Supply chain risk is assessed as {risk.lower()} "
                f"based on {delay:.0f}-day supplier delay "
                f"(confidence: {risk_step.confidence:.0%})."
            )

        # Closing: strategy
        parts.append(f"Recommended action: {strategy}")

        return " ".join(parts)
