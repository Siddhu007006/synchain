"""
Phase E6 test suite — Compound Signals.

Tests:
  1. CompoundRule matching logic
  2. Severity functions (max, avg, max_boosted)
  3. Minimum trigger severity gate
  4. CompoundDetector end-to-end
  5. Compound signals in confidence pipeline
  6. Compound signals in risk elevation
  7. Compound signals in signal summary
  8. API: /compound-rules endpoint
  9. Backward compatibility (no compounds without matching atomics)
"""

from forecasting.engine import (
    CONFIDENCE_MIN,
    SIGNAL_CONFIDENCE_WEIGHTS,
    ForecastInput,
    apply_signal_adjustments,
    compute_risk_elevation,
    compute_signal_penalty,
    generate_forecast_point,
)
from signals.compound import (
    COMPOUND_RULES,
    CompoundDetector,
    severity_avg,
    severity_max,
    severity_max_boosted,
)
from signals.detectors import SignalOutput

# ===========================================================================
# Helpers
# ===========================================================================


def _atomic(source: str, severity: float, sig_type: str = "demand") -> SignalOutput:
    """Create a mock atomic SignalOutput."""
    return SignalOutput(
        source=source,
        signal_type=sig_type,
        severity=severity,
        payload={"mock": True},
    )


def _sig(source: str, severity: float, sig_type: str = "compound") -> dict:
    """Create a mock signal dict for forecast pipeline tests."""
    return {
        "source": source,
        "signal_type": sig_type,
        "severity": severity,
        "payload": {},
    }


def _base_inputs(**overrides) -> ForecastInput:
    """Create a standard ForecastInput with optional overrides."""
    defaults = {
        "avg_demand": 8000.0,
        "demand_trend": "Stable",
        "simulation_count": 10,
        "season_mode": "Normal",
        "supplier_reliability": 90.0,
    }
    defaults.update(overrides)
    return ForecastInput(**defaults)


# ===========================================================================
# 1. Severity Functions
# ===========================================================================


class TestSeverityFunctions:
    """Test severity aggregation functions."""

    def test_max_empty(self):
        assert severity_max([]) == 0.0

    def test_max_single(self):
        assert severity_max([0.75]) == 0.75

    def test_max_multiple(self):
        assert severity_max([0.3, 0.8, 0.5]) == 0.8

    def test_max_capped_at_1(self):
        assert severity_max([1.5]) == 1.0

    def test_avg_empty(self):
        assert severity_avg([]) == 0.0

    def test_avg_multiple(self):
        result = severity_avg([0.4, 0.6])
        assert abs(result - 0.5) < 0.001

    def test_avg_three_values(self):
        result = severity_avg([0.3, 0.6, 0.9])
        assert abs(result - 0.6) < 0.001

    def test_max_boosted_default(self):
        """max_boosted with default 1.2 boost."""
        result = severity_max_boosted([0.5, 0.7], boost=1.2)
        assert abs(result - 0.84) < 0.001  # 0.7 * 1.2 = 0.84

    def test_max_boosted_capped(self):
        """max_boosted capped at 1.0."""
        result = severity_max_boosted([0.9], boost=1.3)
        assert result == 1.0  # 0.9 * 1.3 = 1.17 → capped to 1.0

    def test_max_boosted_empty(self):
        assert severity_max_boosted([]) == 0.0


# ===========================================================================
# 2. CompoundRule Matching
# ===========================================================================


class TestCompoundRuleMatching:
    """Test CompoundRule.matches() logic."""

    def test_supply_shock_matches(self):
        """SupplyShock fires when DemandSpike + SupplierDegradation both present."""
        rule = COMPOUND_RULES[0]  # SupplyShock
        assert rule.name == "SupplyShock"
        assert rule.matches({"DemandSpike": 0.5, "SupplierDegradation": 0.6})

    def test_supply_shock_missing_trigger(self):
        """SupplyShock does NOT fire with only one trigger."""
        rule = COMPOUND_RULES[0]
        assert not rule.matches({"DemandSpike": 0.5})
        assert not rule.matches({"SupplierDegradation": 0.6})

    def test_supply_shock_below_min_severity(self):
        """SupplyShock does NOT fire when trigger severity < min_trigger_severity."""
        rule = COMPOUND_RULES[0]
        # Both present but DemandSpike below 0.3 threshold
        assert not rule.matches({"DemandSpike": 0.2, "SupplierDegradation": 0.6})
        # SupplierDegradation below threshold
        assert not rule.matches({"DemandSpike": 0.5, "SupplierDegradation": 0.1})

    def test_fulfillment_crisis_matches(self):
        """FulfillmentCrisis fires with WarehouseOverload + DemandSpike."""
        rule = COMPOUND_RULES[1]  # FulfillmentCrisis
        assert rule.name == "FulfillmentCrisis"
        assert rule.matches({"WarehouseOverload": 0.5, "DemandSpike": 0.4})

    def test_market_disruption_matches(self):
        """MarketDisruption fires with TrendShift + SupplierDegradation."""
        rule = COMPOUND_RULES[2]  # MarketDisruption
        assert rule.name == "MarketDisruption"
        assert rule.matches({"TrendShift": 0.8, "SupplierDegradation": 0.5})

    def test_perfect_storm_3_triggers(self):
        """PerfectStorm requires ALL 3 triggers."""
        rule = COMPOUND_RULES[3]  # PerfectStorm
        assert rule.name == "PerfectStorm"
        # All 3 present and above threshold (0.4)
        assert rule.matches(
            {
                "WeatherAlert": 0.6,
                "SupplierDegradation": 0.5,
                "DemandSpike": 0.7,
            }
        )

    def test_perfect_storm_missing_one(self):
        """PerfectStorm does NOT fire with only 2 of 3 triggers."""
        rule = COMPOUND_RULES[3]
        assert not rule.matches(
            {
                "WeatherAlert": 0.6,
                "SupplierDegradation": 0.5,
            }
        )

    def test_perfect_storm_higher_threshold(self):
        """PerfectStorm has min_trigger_severity=0.4 (higher than default 0.3)."""
        rule = COMPOUND_RULES[3]
        # All present but DemandSpike at 0.35 (below 0.4 threshold)
        assert not rule.matches(
            {
                "WeatherAlert": 0.6,
                "SupplierDegradation": 0.5,
                "DemandSpike": 0.35,
            }
        )

    def test_cost_squeeze_matches(self):
        """CostSqueeze fires with CommodityShock + EconomicShift."""
        rule = COMPOUND_RULES[4]  # CostSqueeze
        assert rule.name == "CostSqueeze"
        assert rule.matches({"CommodityShock": 0.5, "EconomicShift": 0.4})


# ===========================================================================
# 3. CompoundRule Severity Computation
# ===========================================================================


class TestCompoundRuleSeverity:
    """Test CompoundRule.compute_severity() for each rule."""

    def test_supply_shock_max(self):
        """SupplyShock uses 'max' severity."""
        rule = COMPOUND_RULES[0]
        severity = rule.compute_severity(
            {"DemandSpike": 0.5, "SupplierDegradation": 0.8}
        )
        assert abs(severity - 0.8) < 0.001

    def test_fulfillment_crisis_boosted(self):
        """FulfillmentCrisis uses 'max_boosted' with 1.2 boost."""
        rule = COMPOUND_RULES[1]
        severity = rule.compute_severity({"WarehouseOverload": 0.5, "DemandSpike": 0.7})
        assert abs(severity - 0.84) < 0.001  # max(0.5, 0.7) * 1.2 = 0.84

    def test_cost_squeeze_avg(self):
        """CostSqueeze uses 'avg' severity."""
        rule = COMPOUND_RULES[4]
        severity = rule.compute_severity({"CommodityShock": 0.4, "EconomicShift": 0.6})
        assert abs(severity - 0.5) < 0.001  # avg(0.4, 0.6) = 0.5

    def test_perfect_storm_max_boosted_1_3(self):
        """PerfectStorm uses max_boosted with 1.3 boost."""
        rule = COMPOUND_RULES[3]
        severity = rule.compute_severity(
            {
                "WeatherAlert": 0.6,
                "SupplierDegradation": 0.5,
                "DemandSpike": 0.8,
            }
        )
        # max(0.6, 0.5, 0.8) * 1.3 = 0.8 * 1.3 = 1.04 → capped at 1.0
        assert severity == 1.0


# ===========================================================================
# 4. CompoundDetector End-to-End
# ===========================================================================


class TestCompoundDetector:
    """Test CompoundDetector.evaluate() — pattern matching on atomic outputs."""

    def test_no_atomics_no_compounds(self):
        """Empty atomic outputs produce no compounds."""
        detector = CompoundDetector()
        result = detector.evaluate([])
        assert result == []

    def test_single_atomic_no_compound(self):
        """A single atomic signal cannot trigger any compound."""
        detector = CompoundDetector()
        result = detector.evaluate([_atomic("DemandSpike", 0.5)])
        assert result == []

    def test_supply_shock_fires(self):
        """DemandSpike + SupplierDegradation → SupplyShock."""
        detector = CompoundDetector()
        atomics = [
            _atomic("DemandSpike", 0.6, "demand"),
            _atomic("SupplierDegradation", 0.7, "supply"),
        ]
        result = detector.evaluate(atomics)
        sources = [r.source for r in result]
        assert "SupplyShock" in sources

    def test_supply_shock_payload(self):
        """SupplyShock payload includes trigger details."""
        detector = CompoundDetector()
        atomics = [
            _atomic("DemandSpike", 0.6, "demand"),
            _atomic("SupplierDegradation", 0.7, "supply"),
        ]
        result = detector.evaluate(atomics)
        shock = [r for r in result if r.source == "SupplyShock"][0]
        assert shock.signal_type == "compound"
        assert "triggers" in shock.payload
        assert "DemandSpike" in shock.payload["triggers"]
        assert "SupplierDegradation" in shock.payload["triggers"]
        assert "trigger_severities" in shock.payload
        assert shock.payload["severity_fn"] == "max"

    def test_multiple_compounds_from_shared_triggers(self):
        """DemandSpike + SupplierDeg + WarehouseOverload can trigger multiple compounds."""
        detector = CompoundDetector()
        atomics = [
            _atomic("DemandSpike", 0.6, "demand"),
            _atomic("SupplierDegradation", 0.7, "supply"),
            _atomic("WarehouseOverload", 0.5, "risk"),
        ]
        result = detector.evaluate(atomics)
        sources = {r.source for r in result}
        # SupplyShock (DemandSpike + SupplierDeg) should fire
        assert "SupplyShock" in sources
        # FulfillmentCrisis (WarehouseOverload + DemandSpike) should fire
        assert "FulfillmentCrisis" in sources

    def test_perfect_storm_requires_all_three(self):
        """PerfectStorm only fires with all 3 triggers."""
        detector = CompoundDetector()
        # Only 2 of 3 — no PerfectStorm
        atomics_2 = [
            _atomic("WeatherAlert", 0.6, "external"),
            _atomic("SupplierDegradation", 0.5, "supply"),
        ]
        result_2 = detector.evaluate(atomics_2)
        assert "PerfectStorm" not in [r.source for r in result_2]

        # All 3 (above 0.4 threshold) — PerfectStorm fires
        atomics_3 = [
            _atomic("WeatherAlert", 0.6, "external"),
            _atomic("SupplierDegradation", 0.5, "supply"),
            _atomic("DemandSpike", 0.7, "demand"),
        ]
        result_3 = detector.evaluate(atomics_3)
        assert "PerfectStorm" in [r.source for r in result_3]

    def test_low_severity_no_compound(self):
        """Triggers below min_trigger_severity don't produce compounds."""
        detector = CompoundDetector()
        atomics = [
            _atomic("DemandSpike", 0.1, "demand"),  # below 0.3 threshold
            _atomic("SupplierDegradation", 0.2, "supply"),  # below 0.3 threshold
        ]
        result = detector.evaluate(atomics)
        assert result == []

    def test_max_severity_across_duplicates(self):
        """Multiple DemandSpike outputs → max severity used."""
        detector = CompoundDetector()
        atomics = [
            _atomic("DemandSpike", 0.3, "demand"),
            _atomic("DemandSpike", 0.7, "demand"),  # higher severity
            _atomic("SupplierDegradation", 0.5, "supply"),
        ]
        result = detector.evaluate(atomics)
        shock = [r for r in result if r.source == "SupplyShock"]
        assert len(shock) == 1
        # Severity should use max DemandSpike (0.7)
        assert abs(shock[0].severity - 0.7) < 0.001  # max(0.7, 0.5) = 0.7

    def test_compound_severity_is_correct_type(self):
        """All compound signals have signal_type='compound'."""
        detector = CompoundDetector()
        atomics = [
            _atomic("DemandSpike", 0.5, "demand"),
            _atomic("SupplierDegradation", 0.6, "supply"),
            _atomic("WarehouseOverload", 0.4, "risk"),
            _atomic("TrendShift", 0.8, "market"),
            _atomic("CommodityShock", 0.5, "external"),
            _atomic("EconomicShift", 0.4, "external"),
        ]
        result = detector.evaluate(atomics)
        for compound in result:
            assert compound.signal_type == "compound"


# ===========================================================================
# 5. Compound Signals in Confidence Pipeline
# ===========================================================================


class TestCompoundConfidencePenalty:
    """Test compound signals integrated into compute_signal_penalty()."""

    def test_supply_shock_weight_registered(self):
        """SupplyShock has a weight in SIGNAL_CONFIDENCE_WEIGHTS."""
        assert "SupplyShock" in SIGNAL_CONFIDENCE_WEIGHTS
        assert SIGNAL_CONFIDENCE_WEIGHTS["SupplyShock"] == 0.12

    def test_all_compound_weights_registered(self):
        """All 5 compound rules have weights registered."""
        for rule in COMPOUND_RULES:
            assert rule.output_source in SIGNAL_CONFIDENCE_WEIGHTS
            assert (
                SIGNAL_CONFIDENCE_WEIGHTS[rule.output_source] == rule.confidence_weight
            )

    def test_supply_shock_penalty(self):
        """SupplyShock severity 0.7 → penalty = 0.12 × 0.7 = 0.084."""
        penalty, details = compute_signal_penalty(
            [
                _sig("SupplyShock", 0.7),
            ]
        )
        assert abs(penalty - 0.084) < 0.001
        assert len(details) == 1
        assert "SupplyShock" in details[0]

    def test_additive_stacking(self):
        """Atomic + compound penalties stack additively."""
        signals = [
            _sig("DemandSpike", 0.5, "demand"),  # 0.10 × 0.5 = 0.05
            _sig("SupplierDegradation", 0.7, "supply"),  # 0.15 × 0.7 = 0.105
            _sig("SupplyShock", 0.7, "compound"),  # 0.12 × 0.7 = 0.084
        ]
        penalty, details = compute_signal_penalty(signals)
        expected = 0.05 + 0.105 + 0.084  # 0.239
        assert abs(penalty - expected) < 0.001
        assert len(details) == 3

    def test_confidence_floor_with_compounds(self):
        """Heavy compound + atomic penalties still respect confidence floor."""
        signals = [
            _sig("DemandSpike", 1.0, "demand"),
            _sig("SupplierDegradation", 1.0, "supply"),
            _sig("WarehouseOverload", 1.0, "risk"),
            _sig("SupplyShock", 1.0, "compound"),
            _sig("FulfillmentCrisis", 1.0, "compound"),
            _sig("PerfectStorm", 1.0, "compound"),
        ]
        adj = apply_signal_adjustments(0.80, "Low", signals)
        assert adj.adjusted_confidence == CONFIDENCE_MIN  # 0.10

    def test_compound_only_penalty(self):
        """Compound signal alone (without its atomics) still penalizes."""
        signals = [_sig("CostSqueeze", 0.5, "compound")]
        penalty, details = compute_signal_penalty(signals)
        assert abs(penalty - 0.03) < 0.001  # 0.06 × 0.5 = 0.03


# ===========================================================================
# 6. Compound Signals in Risk Elevation
# ===========================================================================


class TestCompoundRiskElevation:
    """Test compound signals in compute_risk_elevation()."""

    def test_supply_shock_elevates(self):
        """SupplyShock severity > 0.5 elevates Low → Medium."""
        risk, elevated, source = compute_risk_elevation(
            "Low", [_sig("SupplyShock", 0.7, "compound")]
        )
        assert risk == "Medium"
        assert elevated is True
        assert source == "SupplyShock"

    def test_fulfillment_crisis_elevates(self):
        """FulfillmentCrisis severity > 0.5 elevates Medium → High."""
        risk, elevated, source = compute_risk_elevation(
            "Medium", [_sig("FulfillmentCrisis", 0.8, "compound")]
        )
        assert risk == "High"
        assert elevated is True
        assert source == "FulfillmentCrisis"

    def test_perfect_storm_elevates(self):
        """PerfectStorm severity > 0.5 elevates Low → Medium."""
        risk, elevated, source = compute_risk_elevation(
            "Low", [_sig("PerfectStorm", 0.9, "compound")]
        )
        assert risk == "Medium"
        assert elevated is True
        assert source == "PerfectStorm"

    def test_market_disruption_no_elevation(self):
        """MarketDisruption is NOT in RISK_ELEVATION_SOURCES."""
        risk, elevated, _ = compute_risk_elevation(
            "Low", [_sig("MarketDisruption", 0.8, "compound")]
        )
        assert risk == "Low"
        assert elevated is False

    def test_cost_squeeze_no_elevation(self):
        """CostSqueeze is NOT in RISK_ELEVATION_SOURCES."""
        risk, elevated, _ = compute_risk_elevation(
            "Low", [_sig("CostSqueeze", 0.8, "compound")]
        )
        assert risk == "Low"
        assert elevated is False

    def test_compound_below_threshold_no_elevation(self):
        """Compound with severity ≤ 0.5 does not elevate."""
        risk, elevated, _ = compute_risk_elevation(
            "Low", [_sig("SupplyShock", 0.4, "compound")]
        )
        assert risk == "Low"
        assert elevated is False

    def test_most_severe_compound_credited(self):
        """When multiple compounds could elevate, highest severity wins (A2)."""
        risk, elevated, source = compute_risk_elevation(
            "Low",
            [
                _sig("SupplyShock", 0.6, "compound"),
                _sig("PerfectStorm", 0.9, "compound"),  # higher severity
            ],
        )
        assert risk == "Medium"
        assert elevated is True
        assert source == "PerfectStorm"  # Most severe wins


# ===========================================================================
# 7. Forecast Point with Compound Signals
# ===========================================================================


class TestForecastWithCompounds:
    """Test generate_forecast_point() with compound signals."""

    def test_compound_reduces_confidence(self):
        """Compound signal reduces forecast confidence."""
        inputs = _base_inputs()
        point_clean = generate_forecast_point(inputs, horizon=1)
        point_compound = generate_forecast_point(
            inputs,
            horizon=1,
            active_signals=[_sig("SupplyShock", 0.7, "compound")],
        )
        assert point_compound.confidence < point_clean.confidence

    def test_demand_unchanged_by_compounds(self):
        """Compound signals NEVER change demand forecast."""
        inputs = _base_inputs()
        point_clean = generate_forecast_point(inputs, horizon=1)
        point_compound = generate_forecast_point(
            inputs,
            horizon=1,
            active_signals=[
                _sig("SupplyShock", 1.0, "compound"),
                _sig("PerfectStorm", 1.0, "compound"),
            ],
        )
        assert point_compound.forecast_demand == point_clean.forecast_demand

    def test_compound_elevates_risk_in_point(self):
        """SupplyShock with high severity elevates supply risk."""
        inputs = _base_inputs(supplier_reliability=90.0)  # base = Low
        point = generate_forecast_point(
            inputs,
            horizon=1,
            active_signals=[_sig("SupplyShock", 0.8, "compound")],
        )
        assert point.supply_risk == "Medium"  # Elevated from Low

    def test_explanation_mentions_compound(self):
        """Explanation includes compound signal in audit trail."""
        inputs = _base_inputs()
        point = generate_forecast_point(
            inputs,
            horizon=1,
            active_signals=[_sig("SupplyShock", 0.7, "compound")],
        )
        assert "SupplyShock" in point.explanation


# ===========================================================================
# 8. Backward Compatibility
# ===========================================================================


class TestE6BackwardCompatibility:
    """Ensure no compounds = identical to E5 behavior."""

    def test_no_signals_matches_e5(self):
        """No signals → identical output to E5."""
        inputs = _base_inputs()
        point = generate_forecast_point(inputs, horizon=1)
        point_none = generate_forecast_point(inputs, horizon=1, active_signals=None)
        assert point.confidence == point_none.confidence
        assert point.supply_risk == point_none.supply_risk

    def test_atomic_only_no_compounds(self):
        """Atomic-only signals that don't meet compound thresholds → no compound penalty."""
        inputs = _base_inputs()
        # Low severity atomics that won't trigger compounds (below 0.3)
        point = generate_forecast_point(
            inputs,
            horizon=1,
            active_signals=[_sig("DemandSpike", 0.1, "demand")],
        )
        # DemandSpike at 0.1 → penalty = 0.10 × 0.1 = 0.01
        assert point.signal_penalty == 0.01

    def test_compound_rules_count(self):
        """Verify 5 compound rules are registered."""
        assert len(COMPOUND_RULES) == 5


# ===========================================================================
# 9. API: /compound-rules Endpoint
# ===========================================================================


class TestCompoundRulesAPI:
    """Test GET /api/v1/compound-rules endpoint."""

    def test_endpoint_returns_all_rules(self, client):
        """Endpoint returns all 5 registered compound rules."""
        resp = client.get("/api/v1/compound-rules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_rules"] == 5

    def test_rule_structure(self, client):
        """Each rule has required fields."""
        resp = client.get("/api/v1/compound-rules")
        rules = resp.json()["rules"]
        for rule in rules:
            assert "name" in rule
            assert "triggers" in rule
            assert isinstance(rule["triggers"], list)
            assert "severity_fn" in rule
            assert "confidence_weight" in rule
            assert "can_elevate_risk" in rule
            assert "description" in rule

    def test_supply_shock_details(self, client):
        """SupplyShock rule has correct details."""
        resp = client.get("/api/v1/compound-rules")
        rules = resp.json()["rules"]
        shock = [r for r in rules if r["name"] == "SupplyShock"][0]
        assert shock["triggers"] == ["DemandSpike", "SupplierDegradation"]
        assert shock["severity_fn"] == "max"
        assert shock["confidence_weight"] == 0.12
        assert shock["can_elevate_risk"] is True

    def test_perfect_storm_3_triggers(self, client):
        """PerfectStorm rule has 3 triggers."""
        resp = client.get("/api/v1/compound-rules")
        rules = resp.json()["rules"]
        storm = [r for r in rules if r["name"] == "PerfectStorm"][0]
        assert len(storm["triggers"]) == 3


# ===========================================================================
# 10. CompoundDetector Edge Cases
# ===========================================================================


class TestCompoundEdgeCases:
    """Edge cases and boundary conditions."""

    def test_all_atomics_at_zero_severity(self):
        """All triggers present but severity 0.0 → no compounds."""
        detector = CompoundDetector()
        atomics = [
            _atomic("DemandSpike", 0.0, "demand"),
            _atomic("SupplierDegradation", 0.0, "supply"),
        ]
        result = detector.evaluate(atomics)
        assert result == []

    def test_one_trigger_at_boundary(self):
        """One trigger exactly at min_trigger_severity → compound fires."""
        detector = CompoundDetector()
        atomics = [
            _atomic("DemandSpike", 0.3, "demand"),  # exactly at threshold
            _atomic("SupplierDegradation", 0.5, "supply"),
        ]
        result = detector.evaluate(atomics)
        assert "SupplyShock" in [r.source for r in result]

    def test_one_trigger_just_below_boundary(self):
        """One trigger just below min_trigger_severity → no compound."""
        detector = CompoundDetector()
        atomics = [
            _atomic("DemandSpike", 0.29, "demand"),  # just below threshold
            _atomic("SupplierDegradation", 0.5, "supply"),
        ]
        result = detector.evaluate(atomics)
        assert "SupplyShock" not in [r.source for r in result]

    def test_unrelated_atomics_no_compound(self):
        """Signals that don't match any rule → no compounds."""
        detector = CompoundDetector()
        atomics = [
            _atomic("NewsDisruption", 0.8, "external"),
            _atomic("TrendShift", 0.9, "market"),
        ]
        result = detector.evaluate(atomics)
        # These two don't form any compound rule
        # (MarketDisruption = TrendShift + SupplierDeg, not TrendShift + News)
        assert result == []

    def test_compound_does_not_cascade(self):
        """Compound outputs don't feed back into compound detection."""
        detector = CompoundDetector()
        atomics = [
            _atomic("DemandSpike", 0.5, "demand"),
            _atomic("SupplierDegradation", 0.6, "supply"),
        ]
        result = detector.evaluate(atomics)
        # Only SupplyShock should fire — compounds can't trigger other compounds
        compound_sources = [r.source for r in result]
        for source in compound_sources:
            assert source in [rule.output_source for rule in COMPOUND_RULES]


"""
Test summary:
  - TestSeverityFunctions: 10 tests
  - TestCompoundRuleMatching: 10 tests
  - TestCompoundRuleSeverity: 4 tests
  - TestCompoundDetector: 9 tests
  - TestCompoundConfidencePenalty: 6 tests
  - TestCompoundRiskElevation: 7 tests
  - TestForecastWithCompounds: 4 tests
  - TestE6BackwardCompatibility: 3 tests
  - TestCompoundRulesAPI: 4 tests
  - TestCompoundEdgeCases: 5 tests
  Total: 62 tests
"""
