"""
Unit tests for the Reorder Point Engine (V3.0 Sprint A).

Tests are against the PURE engine functions — no DB, no FastAPI.
Each test constructs dataclass inputs and asserts dataclass outputs.

Test coverage:
  1. Normal reorder scenario
  2. Zero stock → CRITICAL severity
  3. Abundant stock → NONE severity
  4. No forecast data → falls back to avg_monthly_demand
  5. No demand data at all → graceful "no recommendation"
  6. No suppliers → uses default lead time
  7. Low supplier reliability → increases safety stock
  8. Critical signals → increases safety stock
  9. Severity classification thresholds
  10. Order date in the past → clamped to today
  11. Recommendation confidence composite
  12. Financial impact estimation
  13. Inventory health score
"""

from datetime import date

from reorder.engine import (
    ForecastData,
    ProductData,
    ReorderResult,
    SignalContext,
    SupplierData,
    calculate_financial_impact,
    calculate_inventory_health,
    calculate_recommendation,
    calculate_recommendation_confidence,
    classify_severity,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _product(
    stock: float = 500, demand: float = 1000, price: float = 0.0
) -> ProductData:
    return ProductData(
        product_id=1,
        product_name="Widget-X",
        company_id=1,
        current_stock=stock,
        avg_monthly_demand=demand,
        unit_price=price,
    )


def _forecast(demand: float = 900, confidence: float = 0.85) -> ForecastData:
    return ForecastData(
        forecast_demand=demand,
        confidence=confidence,
        supply_risk="Low",
        trend_factor=1.0,
    )


def _supplier(lead_time: float = 14, reliability: float = 90) -> SupplierData:
    return SupplierData(
        supplier_id=1,
        supplier_name="Acme Parts",
        lead_time_days=lead_time,
        reliability_pct=reliability,
        supply_status="High",
    )


def _signals(critical: int = 0) -> SignalContext:
    return SignalContext(
        active_count=critical,
        critical_count=critical,
        high_severity_signals=[f"Signal-{i}" for i in range(critical)],
    )


TODAY = date(2026, 7, 1)


# ---------------------------------------------------------------------------
# Tests: Severity Classification
# ---------------------------------------------------------------------------


class TestSeverityClassification:

    def test_critical(self):
        assert classify_severity(0) == "CRITICAL"
        assert classify_severity(7) == "CRITICAL"

    def test_high(self):
        assert classify_severity(8) == "HIGH"
        assert classify_severity(14) == "HIGH"

    def test_medium(self):
        assert classify_severity(15) == "MEDIUM"
        assert classify_severity(30) == "MEDIUM"

    def test_low(self):
        assert classify_severity(31) == "LOW"
        assert classify_severity(60) == "LOW"

    def test_none(self):
        assert classify_severity(61) == "NONE"
        assert classify_severity(999) == "NONE"


# ---------------------------------------------------------------------------
# Tests: Reorder Calculation
# ---------------------------------------------------------------------------


class TestReorderCalculation:

    def test_normal_scenario(self):
        result = calculate_recommendation(
            product=_product(stock=200, demand=1000),
            forecast=_forecast(demand=900, confidence=0.85),
            supplier=_supplier(lead_time=14, reliability=90),
            signals=_signals(critical=0),
            today=TODAY,
        )

        assert isinstance(result, ReorderResult)
        assert result.product_name == "Widget-X"
        assert result.forecast_demand == 900
        assert result.daily_demand == 30.0
        assert result.days_until_stockout == 6
        assert result.severity == "CRITICAL"
        assert result.recommended_quantity > 0
        assert result.recommended_supplier_name == "Acme Parts"
        assert len(result.reasoning) > 0
        # New fields
        assert 0.0 <= result.recommendation_confidence <= 1.0
        assert result.financial_impact is not None
        assert result.financial_impact.stockout_risk == "CRITICAL"

    def test_zero_stock_is_critical(self):
        result = calculate_recommendation(
            product=_product(stock=0, demand=1000),
            forecast=_forecast(demand=900),
            supplier=_supplier(lead_time=7),
            signals=_signals(),
            today=TODAY,
        )

        assert result.days_until_stockout == 0
        assert result.severity == "CRITICAL"
        assert result.recommended_quantity > 0

    def test_abundant_stock_no_reorder(self):
        result = calculate_recommendation(
            product=_product(stock=5000, demand=100),
            forecast=_forecast(demand=120, confidence=0.9),
            supplier=_supplier(lead_time=3, reliability=95),
            signals=_signals(),
            today=TODAY,
        )

        assert result.days_until_stockout > 60
        assert result.severity == "NONE"

    def test_no_forecast_uses_avg_demand(self):
        result = calculate_recommendation(
            product=_product(stock=200, demand=600),
            forecast=None,
            supplier=_supplier(lead_time=7),
            signals=_signals(),
            today=TODAY,
        )

        assert result.forecast_demand == 600
        assert result.confidence == 0.5
        assert "No forecast available" in result.reasoning[0]

    def test_no_demand_data_graceful(self):
        result = calculate_recommendation(
            product=_product(stock=200, demand=0),
            forecast=None,
            supplier=_supplier(),
            signals=_signals(),
            today=TODAY,
        )

        assert result.severity == "NONE"
        assert result.recommended_quantity == 0.0
        assert "No demand data" in result.reasoning[0]
        assert result.recommendation_confidence == 0.0

    def test_no_supplier_uses_default(self):
        result = calculate_recommendation(
            product=_product(stock=100, demand=900),
            forecast=_forecast(demand=900),
            supplier=None,
            signals=_signals(),
            today=TODAY,
        )

        assert result.recommended_supplier_id is None
        assert result.supplier_lead_time_days == 7.0

    def test_low_reliability_increases_safety_stock(self):
        result_high = calculate_recommendation(
            product=_product(stock=300),
            forecast=_forecast(demand=900, confidence=0.8),
            supplier=_supplier(lead_time=10, reliability=95),
            signals=_signals(),
            today=TODAY,
        )

        result_low = calculate_recommendation(
            product=_product(stock=300),
            forecast=_forecast(demand=900, confidence=0.8),
            supplier=_supplier(lead_time=10, reliability=60),
            signals=_signals(),
            today=TODAY,
        )

        assert result_low.safety_stock > result_high.safety_stock

    def test_critical_signals_increase_safety_stock(self):
        result_calm = calculate_recommendation(
            product=_product(stock=300),
            forecast=_forecast(demand=900, confidence=0.8),
            supplier=_supplier(lead_time=10),
            signals=_signals(critical=0),
            today=TODAY,
        )

        result_alarm = calculate_recommendation(
            product=_product(stock=300),
            forecast=_forecast(demand=900, confidence=0.8),
            supplier=_supplier(lead_time=10),
            signals=_signals(critical=3),
            today=TODAY,
        )

        assert result_alarm.safety_stock > result_calm.safety_stock

    def test_order_date_before_stockout(self):
        result = calculate_recommendation(
            product=_product(stock=600, demand=600),
            forecast=_forecast(demand=600, confidence=0.9),
            supplier=_supplier(lead_time=10),
            signals=_signals(),
            today=TODAY,
        )

        stockout = date.fromisoformat(result.stockout_date)
        order_by = date.fromisoformat(result.recommended_order_date)
        assert order_by <= stockout

    def test_past_order_date_clamped_to_today(self):
        result = calculate_recommendation(
            product=_product(stock=30, demand=900),
            forecast=_forecast(demand=900),
            supplier=_supplier(lead_time=14),
            signals=_signals(),
            today=TODAY,
        )

        order_by = date.fromisoformat(result.recommended_order_date)
        assert order_by >= TODAY

    def test_reasoning_is_populated(self):
        result = calculate_recommendation(
            product=_product(stock=200),
            forecast=_forecast(demand=900),
            supplier=_supplier(),
            signals=_signals(critical=1),
            today=TODAY,
        )

        assert len(result.reasoning) >= 3
        combined = " ".join(result.reasoning)
        assert "Forecast demand" in combined
        assert "Current stock" in combined

    def test_stockout_date_format(self):
        result = calculate_recommendation(
            product=_product(stock=600, demand=600),
            forecast=_forecast(demand=600),
            supplier=_supplier(),
            signals=_signals(),
            today=TODAY,
        )

        parsed = date.fromisoformat(result.stockout_date)
        assert parsed >= TODAY


# ---------------------------------------------------------------------------
# Tests: Recommendation Confidence
# ---------------------------------------------------------------------------


class TestRecommendationConfidence:
    """Test the composite trust score calculation."""

    def test_perfect_inputs(self):
        """High forecast + high reliability + no signals → high confidence."""
        score = calculate_recommendation_confidence(
            forecast_confidence=0.95,
            supplier_reliability_pct=98.0,
            signal_critical_count=0,
        )
        assert score >= 0.85

    def test_low_forecast_reduces_confidence(self):
        """Low forecast confidence → lower recommendation confidence."""
        high = calculate_recommendation_confidence(0.9, 90.0, 0)
        low = calculate_recommendation_confidence(0.3, 90.0, 0)
        assert low < high

    def test_no_supplier_defaults(self):
        """No supplier → uses 0.5 default."""
        score = calculate_recommendation_confidence(0.8, None, 0)
        assert 0.0 <= score <= 1.0

    def test_critical_signals_reduce_confidence(self):
        """More critical signals → lower confidence."""
        calm = calculate_recommendation_confidence(0.8, 90.0, 0)
        alarm = calculate_recommendation_confidence(0.8, 90.0, 4)
        assert alarm < calm

    def test_clamped_to_0_1(self):
        """Score should always be 0.0 to 1.0."""
        score = calculate_recommendation_confidence(0.0, 0.0, 10)
        assert 0.0 <= score <= 1.0

    def test_confidence_in_recommendation(self):
        """recommendation_confidence should appear in the result."""
        result = calculate_recommendation(
            product=_product(stock=200),
            forecast=_forecast(demand=900, confidence=0.85),
            supplier=_supplier(reliability=90),
            signals=_signals(critical=0),
            today=TODAY,
        )
        # 0.85*0.5 + 0.9*0.3 + 1.0*0.2 = 0.425 + 0.27 + 0.2 = 0.895
        assert result.recommendation_confidence == 0.895


# ---------------------------------------------------------------------------
# Tests: Financial Impact
# ---------------------------------------------------------------------------


class TestFinancialImpact:
    """Test financial exposure estimation."""

    def test_with_price_data(self):
        """Should calculate revenue impact when unit_price is set."""
        impact = calculate_financial_impact(
            daily_demand=30.0,
            days_until_stockout=5,
            lead_time_days=14.0,
            unit_price=50.0,
            severity="CRITICAL",
        )
        # gap = 14 - 5 = 9 days, units_at_risk = 30*9 = 270
        assert impact.units_at_risk == 270.0
        assert impact.estimated_revenue_impact == 13500.0  # 270 * 50
        assert impact.has_price_data is True

    def test_without_price_data(self):
        """Revenue impact should be None when unit_price is 0."""
        impact = calculate_financial_impact(
            daily_demand=30.0,
            days_until_stockout=5,
            lead_time_days=14.0,
            unit_price=0.0,
            severity="HIGH",
        )
        assert impact.units_at_risk == 270.0
        assert impact.estimated_revenue_impact is None
        assert impact.has_price_data is False

    def test_no_stockout_risk(self):
        """If lead_time < days_until_stockout, no exposure."""
        impact = calculate_financial_impact(
            daily_demand=30.0,
            days_until_stockout=30,
            lead_time_days=7.0,
            unit_price=100.0,
            severity="MEDIUM",
        )
        assert impact.units_at_risk == 0.0
        assert impact.estimated_revenue_impact == 0.0

    def test_financial_in_recommendation(self):
        """Financial impact should appear in recommendation with pricing."""
        result = calculate_recommendation(
            product=_product(stock=200, demand=900, price=25.0),
            forecast=_forecast(demand=900),
            supplier=_supplier(lead_time=14),
            signals=_signals(),
            today=TODAY,
        )
        assert result.financial_impact.has_price_data is True
        assert result.financial_impact.units_at_risk >= 0

    def test_reasoning_includes_financial(self):
        """When price is set, reasoning should mention revenue."""
        result = calculate_recommendation(
            product=_product(stock=100, demand=900, price=50.0),
            forecast=_forecast(demand=900),
            supplier=_supplier(lead_time=14),
            signals=_signals(),
            today=TODAY,
        )
        combined = " ".join(result.reasoning)
        assert (
            "revenue at risk" in combined.lower() or "units at risk" in combined.lower()
        )


# ---------------------------------------------------------------------------
# Tests: Inventory Health Score
# ---------------------------------------------------------------------------


class TestInventoryHealth:
    """Test company-level health KPI."""

    def test_empty_recommendations(self):
        """No products → score 0, grade N/A."""
        health = calculate_inventory_health([])
        assert health["score"] == 0
        assert health["grade"] == "N/A"

    def test_healthy_company(self):
        """All products safe, high confidence → HEALTHY."""
        results = [
            calculate_recommendation(
                product=_product(stock=5000, demand=100),
                forecast=_forecast(demand=120, confidence=0.9),
                supplier=_supplier(lead_time=3, reliability=95),
                signals=_signals(),
                today=TODAY,
            )
            for _ in range(5)
        ]
        health = calculate_inventory_health(results)
        assert health["score"] >= 70
        assert health["grade"] in ("HEALTHY", "MODERATE")
        assert health["critical_count"] == 0

    def test_at_risk_company(self):
        """Multiple critical products → lower score."""
        results = [
            calculate_recommendation(
                product=_product(stock=50, demand=900),
                forecast=_forecast(demand=900, confidence=0.4),
                supplier=_supplier(lead_time=14, reliability=50),
                signals=_signals(critical=2),
                today=TODAY,
            )
            for _ in range(5)
        ]
        health = calculate_inventory_health(results)
        assert health["score"] < 60
        assert health["grade"] in ("AT_RISK", "CRITICAL")
        assert health["critical_count"] == 5

    def test_components_present(self):
        """Health breakdown should have all 4 components."""
        results = [
            calculate_recommendation(
                product=_product(stock=300),
                forecast=_forecast(demand=600),
                supplier=_supplier(),
                signals=_signals(),
                today=TODAY,
            )
        ]
        health = calculate_inventory_health(results)
        components = health["components"]
        assert "forecast_confidence" in components
        assert "stockout_safety" in components
        assert "signal_health" in components
        assert "supplier_reliability" in components
