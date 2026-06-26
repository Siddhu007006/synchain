"""
Schema validation tests — ensures Literal types reject invalid values.
"""

import pytest
from pydantic import ValidationError
from schemas import SimulationInput


class TestSimulationInputValidation:
    """Verify backend rejects invalid enum values."""

    def test_valid_input(self):
        si = SimulationInput(
            product="Test",
            stock=100,
            warehouse="W1",
            demand=200,
            supplier_delay=3,
        )
        assert si.warehouse == "W1"
        assert si.market_trend == "Neutral"  # default
        assert si.supply_status == "Medium"  # default
        assert si.season == "Normal"  # default

    def test_invalid_warehouse(self):
        with pytest.raises(ValidationError, match="W1.*W2.*W3"):
            SimulationInput(
                product="Test",
                stock=100,
                warehouse="W4",
                demand=200,
                supplier_delay=3,
            )

    def test_invalid_market_trend(self):
        with pytest.raises(ValidationError):
            SimulationInput(
                product="Test",
                stock=100,
                warehouse="W1",
                demand=200,
                supplier_delay=3,
                market_trend="Bullish",
            )

    def test_invalid_supply_status(self):
        with pytest.raises(ValidationError):
            SimulationInput(
                product="Test",
                stock=100,
                warehouse="W1",
                demand=200,
                supplier_delay=3,
                supply_status="None",
            )

    def test_invalid_season(self):
        with pytest.raises(ValidationError):
            SimulationInput(
                product="Test",
                stock=100,
                warehouse="W1",
                demand=200,
                supplier_delay=3,
                season="Summer",
            )

    def test_negative_stock_rejected(self):
        with pytest.raises(ValidationError):
            SimulationInput(
                product="Test",
                stock=-100,
                warehouse="W1",
                demand=200,
                supplier_delay=3,
            )

    def test_negative_delay_rejected(self):
        with pytest.raises(ValidationError):
            SimulationInput(
                product="Test",
                stock=100,
                warehouse="W1",
                demand=200,
                supplier_delay=-1,
            )

    def test_all_valid_enum_combinations(self):
        """Verify every valid enum value is accepted."""
        for wh in ["W1", "W2", "W3"]:
            for trend in ["Positive", "Neutral", "Negative"]:
                for supply in ["High", "Medium", "Low"]:
                    for season in ["Festival", "Normal", "Off-season"]:
                        si = SimulationInput(
                            product="Test",
                            stock=100,
                            warehouse=wh,
                            demand=200,
                            supplier_delay=3,
                            market_trend=trend,
                            supply_status=supply,
                            season=season,
                        )
                        assert si.warehouse == wh
