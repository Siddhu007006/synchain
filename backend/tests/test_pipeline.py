"""
Pipeline integration tests — verify DecisionAgent orchestration end-to-end.
"""

from agents.scenario_agent import ScenarioAgent
from schemas import SimulationInput
from services import simulate_supply_chain


class TestPipelineIntegration:
    """Full pipeline: input → DecisionAgent → all 4 agents → result."""

    def test_basic_pipeline(self):
        result = simulate_supply_chain(
            SimulationInput(
                product="Widget",
                stock=5000,
                warehouse="W1",
                demand=8000,
                supplier_delay=3,
                market_trend="Neutral",
                supply_status="Medium",
                season="Normal",
            )
        )
        assert result.demand_forecast > 0
        assert result.recommended_inventory > 0
        assert result.selected_warehouse in {"W1", "W2", "W3"}
        assert result.risk in {"Low", "Medium", "High"}
        assert 0.0 <= result.overall_confidence <= 1.0
        assert len(result.agent_breakdown) == 4
        assert result.explanation  # non-empty

    def test_pipeline_agent_breakdown_names(self):
        result = simulate_supply_chain(
            SimulationInput(
                product="Test",
                stock=1000,
                warehouse="W2",
                demand=5000,
                supplier_delay=7,
                market_trend="Negative",
                supply_status="Low",
                season="Off-season",
            )
        )
        names = {s.agent_name for s in result.agent_breakdown}
        assert names == {"DemandAgent", "InventoryAgent", "LogisticsAgent", "RiskAgent"}

    def test_pipeline_high_risk_scenario(self):
        """High delay + Low supply + Negative market → should produce High risk."""
        result = simulate_supply_chain(
            SimulationInput(
                product="Critical Part",
                stock=100,
                warehouse="W1",
                demand=10000,
                supplier_delay=10,
                market_trend="Negative",
                supply_status="Low",
                season="Festival",
            )
        )
        assert result.risk == "High"

    def test_pipeline_low_risk_scenario(self):
        """No delay + High supply + Positive market → should produce Low risk."""
        result = simulate_supply_chain(
            SimulationInput(
                product="Commodity",
                stock=10000,
                warehouse="W1",
                demand=1000,
                supplier_delay=0,
                market_trend="Positive",
                supply_status="High",
                season="Normal",
            )
        )
        assert result.risk == "Low"


class TestScenarioAgent:
    """Scenario agent produces 4 comparisons with impact deltas."""

    def test_scenario_count(self):
        inp = SimulationInput(
            product="Test",
            stock=5000,
            warehouse="W1",
            demand=8000,
            supplier_delay=3,
        )
        base_result = simulate_supply_chain(inp)
        agent = ScenarioAgent()
        scenarios = agent.run(
            base_input=inp,
            base_result=base_result,
            run_pipeline=simulate_supply_chain,
        )
        assert len(scenarios) == 4

    def test_scenario_names(self):
        inp = SimulationInput(
            product="Test",
            stock=5000,
            warehouse="W1",
            demand=8000,
            supplier_delay=3,
        )
        base_result = simulate_supply_chain(inp)
        agent = ScenarioAgent()
        scenarios = agent.run(
            base_input=inp,
            base_result=base_result,
            run_pipeline=simulate_supply_chain,
        )
        names = {s["scenario_name"] for s in scenarios}
        assert names == {
            "Demand Surge",
            "Supplier Shutdown",
            "Inventory Shortage",
            "Transport Delay",
        }

    def test_demand_surge_increases_demand(self):
        inp = SimulationInput(
            product="Test",
            stock=5000,
            warehouse="W1",
            demand=8000,
            supplier_delay=3,
        )
        base_result = simulate_supply_chain(inp)
        agent = ScenarioAgent()
        scenarios = agent.run(
            base_input=inp,
            base_result=base_result,
            run_pipeline=simulate_supply_chain,
        )
        surge = next(s for s in scenarios if s["scenario_name"] == "Demand Surge")
        assert surge["impact"]["demand_change"] > 0
