"""
Agent unit tests — validate confidence formulas and edge cases.

Each test follows the pattern:
  1. Construct known inputs
  2. Run the agent
  3. Assert output values AND confidence score match the documented formula
"""

from agents.demand_agent import DemandAgent
from agents.inventory_agent import InventoryAgent
from agents.logistics_agent import LogisticsAgent
from agents.risk_agent import RiskAgent


class TestDemandAgent:
    """Tests for DemandAgent confidence formula and computation."""

    def setup_method(self):
        self.agent = DemandAgent()

    def test_basic_forecast(self):
        """Neutral market + Normal season → demand × 1.2."""
        result = self.agent.run(demand=1000, market_trend="Neutral", season="Normal")
        assert result.output_data["predicted_demand"] == 1200.0
        assert result.status == "success"

    def test_festival_positive_market(self):
        """Positive + Festival → demand × 1.2 × 1.1 × 1.3."""
        result = self.agent.run(demand=1000, market_trend="Positive", season="Festival")
        expected = round(1000 * 1.2 * 1.1 * 1.3, 2)
        assert result.output_data["predicted_demand"] == expected

    def test_confidence_max(self):
        """Positive market + Festival season → max confidence."""
        result = self.agent.run(demand=1000, market_trend="Positive", season="Festival")
        assert result.confidence == 1.0  # 0.50 + 0.25 + 0.25

    def test_confidence_min(self):
        """Neutral market + Normal season → minimum confidence."""
        result = self.agent.run(demand=1000, market_trend="Neutral", season="Normal")
        assert result.confidence == 0.70  # 0.50 + 0.10 + 0.10

    def test_negative_market_offseason(self):
        """Negative + Off-season → demand × 1.2 × 0.9 × 0.8."""
        result = self.agent.run(
            demand=5000, market_trend="Negative", season="Off-season"
        )
        expected = round(5000 * 1.2 * 0.9 * 0.8, 2)
        assert result.output_data["predicted_demand"] == expected
        assert result.confidence == 1.0  # strong signals

    def test_input_summary_contains_only_consumed_fields(self):
        """Input summary should only have demand, market_trend, season."""
        result = self.agent.run(demand=1000)
        assert set(result.input_summary.keys()) == {"demand", "market_trend", "season"}


class TestInventoryAgent:
    """Tests for InventoryAgent confidence formula and computation."""

    def setup_method(self):
        self.agent = InventoryAgent()

    def test_medium_supply(self):
        """Medium supply → safety factor 1.10."""
        result = self.agent.run(
            predicted_demand=1000, stock=500, supply_status="Medium"
        )
        assert result.output_data["recommended_inventory"] == 1100.0

    def test_low_supply(self):
        """Low supply → safety factor 1.25."""
        result = self.agent.run(predicted_demand=1000, stock=500, supply_status="Low")
        assert result.output_data["recommended_inventory"] == 1250.0

    def test_high_supply(self):
        """High supply → safety factor 1.05."""
        result = self.agent.run(predicted_demand=1000, stock=500, supply_status="High")
        assert result.output_data["recommended_inventory"] == 1050.0

    def test_confidence_large_gap(self):
        """Stock far from demand → high demand_gap_clarity."""
        result = self.agent.run(predicted_demand=10000, stock=1000, supply_status="Low")
        # gap_ratio = |1000-10000|/10000 = 0.9 > 0.5 → 0.25
        # supply_clarity: Low → 0.25
        # confidence = 0.50 + 0.25 + 0.25 = 1.00
        assert result.confidence == 1.0

    def test_confidence_small_gap(self):
        """Stock ≈ demand → low demand_gap_clarity."""
        result = self.agent.run(
            predicted_demand=1000, stock=950, supply_status="Medium"
        )
        # gap_ratio = |950-1000|/1000 = 0.05 ≤ 0.2 → 0.05
        # supply_clarity: Medium → 0.10
        # confidence = 0.50 + 0.10 + 0.05 = 0.65
        assert result.confidence == 0.65


class TestRiskAgent:
    """Tests for RiskAgent multi-factor scoring."""

    def setup_method(self):
        self.agent = RiskAgent()

    def test_high_risk(self):
        """Critical delay + Low supply + Negative market → High risk."""
        result = self.agent.run(
            supplier_delay=10, supply_status="Low", market_trend="Negative"
        )
        assert result.output_data["risk_level"] == "High"

    def test_low_risk(self):
        """No delay + High supply + Positive market → Low risk."""
        result = self.agent.run(
            supplier_delay=0, supply_status="High", market_trend="Positive"
        )
        assert result.output_data["risk_level"] == "Low"

    def test_medium_risk(self):
        """Moderate delay + Medium supply + Neutral market → Medium risk."""
        result = self.agent.run(
            supplier_delay=4, supply_status="Medium", market_trend="Neutral"
        )
        assert result.output_data["risk_level"] == "Medium"

    def test_risk_score_range(self):
        """Risk score should always be between 0 and 1."""
        for delay in [0, 2, 5, 10]:
            for supply in ["Low", "Medium", "High"]:
                for market in ["Positive", "Neutral", "Negative"]:
                    result = self.agent.run(
                        supplier_delay=delay,
                        supply_status=supply,
                        market_trend=market,
                    )
                    assert 0 <= result.output_data["risk_score"] <= 1


class TestLogisticsAgent:
    """Tests for LogisticsAgent cost-optimized warehouse selection."""

    def setup_method(self):
        self.agent = LogisticsAgent()

    def test_selects_warehouse(self):
        """Output always contains a valid warehouse."""
        result = self.agent.run(warehouse="W1", stock=5000, predicted_demand=3000)
        assert result.output_data["selected_warehouse"] in {"W1", "W2", "W3"}

    def test_route_matches_warehouse(self):
        """Selected route must match the warehouse's route."""
        from agents.logistics_agent import WAREHOUSES

        result = self.agent.run(warehouse="W1", stock=5000, predicted_demand=3000)
        wh = result.output_data["selected_warehouse"]
        assert result.output_data["route"] == WAREHOUSES[wh]["route"]

    def test_home_bonus_applies(self):
        """When stock >= demand, home warehouse gets +0.15 bonus."""
        result = self.agent.run(warehouse="W1", stock=10000, predicted_demand=5000)
        # W1 should have the bonus since stock >= demand
        assert result.output_data["selected_warehouse"] == "W1"

    def test_high_demand_prefers_w2(self):
        """When only W2 has full capacity fit, W2 wins despite higher cost."""
        # At demand=14000: W2 cap=15k → cap_score=1.0 (only full-fit warehouse)
        # W1 cap=10k → cap_score=0.7 (10000 >= 11200)
        # W3 cap=8k  → cap_score=0.3 (8000 < 11200)
        # W2's capacity advantage overcomes its cost penalty
        result = self.agent.run(warehouse="W3", stock=1000, predicted_demand=14000)
        assert result.output_data["selected_warehouse"] == "W2"
