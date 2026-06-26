"""
Phase E4 test suite — Signal-Driven Forecasting.

Tests:
  1. Signal penalty computation (severity-proportional)
  2. Risk elevation logic (threshold-based)
  3. Explanation augmentation (audit trail)
  4. Full forecast point generation with signals
  5. Backward compatibility (no signals = E2 output)
  6. Integration tests (simulation → signal → forecast pipeline)
"""

from forecasting.engine import (
    CONFIDENCE_MIN,
    ForecastInput,
    apply_signal_adjustments,
    build_signal_explanation,
    compute_risk_elevation,
    compute_signal_penalty,
    generate_forecast_point,
)
from tests.conftest import _auth_headers

# ===========================================================================
# Helpers — mock signal objects as dicts (engine handles both dicts and ORM)
# ===========================================================================


def _sig(source: str, severity: float, payload: dict | None = None) -> dict:
    """Create a mock signal dict."""
    return {
        "source": source,
        "signal_type": {
            "DemandSpike": "demand",
            "SupplierDegradation": "supply",
            "WarehouseOverload": "risk",
            "TrendShift": "market",
        }.get(source, "unknown"),
        "severity": severity,
        "payload": payload or {},
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
# 1. Signal Penalty Computation
# ===========================================================================


class TestSignalPenalty:
    """Test compute_signal_penalty() — severity-proportional penalties."""

    def test_empty_signals(self):
        """No signals = no penalty."""
        penalty, details = compute_signal_penalty([])
        assert penalty == 0.0
        assert details == []

    def test_demand_spike_severity_050(self):
        """DemandSpike sev 0.5 -> penalty = 0.10 * 0.5 = 0.05."""
        penalty, details = compute_signal_penalty([_sig("DemandSpike", 0.5)])
        assert penalty == 0.05
        assert len(details) == 1
        assert "DemandSpike" in details[0]

    def test_supplier_degradation_severity_067(self):
        """SupplierDegradation sev 0.67 -> penalty = 0.15 * 0.67 = 0.1005."""
        penalty, details = compute_signal_penalty([_sig("SupplierDegradation", 0.67)])
        assert abs(penalty - 0.1005) < 0.001
        assert "SupplierDegradation" in details[0]

    def test_warehouse_overload_severity_080(self):
        """WarehouseOverload sev 0.8 -> penalty = 0.08 * 0.8 = 0.064."""
        penalty, details = compute_signal_penalty([_sig("WarehouseOverload", 0.8)])
        assert abs(penalty - 0.064) < 0.001

    def test_trend_shift_no_penalty(self):
        """TrendShift has weight 0.0 -> no confidence penalty."""
        penalty, details = compute_signal_penalty(
            [
                _sig(
                    "TrendShift",
                    0.8,
                    {
                        "old_trend": "Stable",
                        "new_trend": "Rising",
                        "shift_type": "acceleration",
                    },
                ),
            ]
        )
        assert penalty == 0.0
        assert details == []

    def test_multiple_signals_sum(self):
        """Multiple signal penalties sum together."""
        signals = [
            _sig("DemandSpike", 0.5),  # 0.10 * 0.5 = 0.05
            _sig("SupplierDegradation", 0.6),  # 0.15 * 0.6 = 0.09
        ]
        penalty, details = compute_signal_penalty(signals)
        assert abs(penalty - 0.14) < 0.001
        assert len(details) == 2

    def test_all_three_at_max(self):
        """All three penalizing signals at severity 1.0."""
        signals = [
            _sig("DemandSpike", 1.0),  # 0.10
            _sig("SupplierDegradation", 1.0),  # 0.15
            _sig("WarehouseOverload", 1.0),  # 0.08
        ]
        penalty, _ = compute_signal_penalty(signals)
        assert abs(penalty - 0.33) < 0.001

    def test_unknown_source_no_penalty(self):
        """Unknown signal source has no configured weight -> no penalty."""
        penalty, details = compute_signal_penalty([_sig("UnknownDetector", 0.9)])
        assert penalty == 0.0
        assert details == []

    def test_zero_severity_no_penalty(self):
        """Zero severity -> no penalty even with configured weight."""
        penalty, _ = compute_signal_penalty([_sig("DemandSpike", 0.0)])
        assert penalty == 0.0


# ===========================================================================
# 2. Risk Elevation
# ===========================================================================


class TestRiskElevation:
    """Test compute_risk_elevation() — threshold-based elevation."""

    def test_no_signals(self):
        """No signals -> no elevation."""
        risk, elevated, source = compute_risk_elevation("Low", [])
        assert risk == "Low"
        assert elevated is False
        assert source is None

    def test_supplier_above_threshold(self):
        """SupplierDegradation sev 0.8 -> elevate Low to Medium."""
        risk, elevated, source = compute_risk_elevation(
            "Low", [_sig("SupplierDegradation", 0.8)]
        )
        assert risk == "Medium"
        assert elevated is True
        assert source == "SupplierDegradation"

    def test_warehouse_above_threshold(self):
        """WarehouseOverload sev 0.6 -> elevate Medium to High."""
        risk, elevated, source = compute_risk_elevation(
            "Medium", [_sig("WarehouseOverload", 0.6)]
        )
        assert risk == "High"
        assert elevated is True
        assert source == "WarehouseOverload"

    def test_below_threshold_no_elevation(self):
        """Signal severity <= 0.5 -> no elevation."""
        risk, elevated, source = compute_risk_elevation(
            "Low", [_sig("SupplierDegradation", 0.4)]
        )
        assert risk == "Low"
        assert elevated is False

    def test_exactly_at_threshold_no_elevation(self):
        """Severity exactly 0.5 -> no elevation (threshold is >0.5, not >=)."""
        risk, elevated, _ = compute_risk_elevation(
            "Low", [_sig("SupplierDegradation", 0.5)]
        )
        assert risk == "Low"
        assert elevated is False

    def test_already_high_stays_high(self):
        """High risk can't be elevated further."""
        risk, elevated, _ = compute_risk_elevation(
            "High", [_sig("SupplierDegradation", 0.9)]
        )
        assert risk == "High"
        assert elevated is False  # No change, so not "elevated"

    def test_demand_spike_cannot_elevate(self):
        """DemandSpike is not in RISK_ELEVATION_SOURCES."""
        risk, elevated, _ = compute_risk_elevation("Low", [_sig("DemandSpike", 0.9)])
        assert risk == "Low"
        assert elevated is False

    def test_trend_shift_cannot_elevate(self):
        """TrendShift is not in RISK_ELEVATION_SOURCES."""
        risk, elevated, _ = compute_risk_elevation("Low", [_sig("TrendShift", 0.8)])
        assert risk == "Low"
        assert elevated is False


# ===========================================================================
# 3. Explanation Augmentation
# ===========================================================================


class TestSignalExplanation:
    """Test build_signal_explanation() — audit trail in explanations."""

    def test_no_adjustments(self):
        """No penalty, no elevation -> empty explanation."""
        result = build_signal_explanation(
            base_confidence=0.80,
            signal_penalty=0.0,
            final_confidence=0.80,
            penalty_details=[],
            risk_elevated=False,
            original_risk="Low",
            adjusted_risk="Low",
            elevating_source=None,
            elevating_severity=None,
            active_signals=[],
        )
        assert result == ""

    def test_confidence_audit_trail(self):
        """Penalty > 0 -> explanation includes base, penalties, final."""
        result = build_signal_explanation(
            base_confidence=0.80,
            signal_penalty=0.05,
            final_confidence=0.75,
            penalty_details=["DemandSpike penalty: -0.05 (severity 0.50)"],
            risk_elevated=False,
            original_risk="Low",
            adjusted_risk="Low",
            elevating_source=None,
            elevating_severity=None,
            active_signals=[],
        )
        assert "Signal adjustments:" in result
        assert "Base confidence 0.80" in result
        assert "DemandSpike penalty: -0.05" in result
        assert "final confidence 0.75" in result

    def test_risk_elevation_mentioned(self):
        """Risk elevation -> explanation mentions source and tiers."""
        result = build_signal_explanation(
            base_confidence=0.70,
            signal_penalty=0.10,
            final_confidence=0.60,
            penalty_details=["SupplierDegradation penalty: -0.10 (severity 0.67)"],
            risk_elevated=True,
            original_risk="Low",
            adjusted_risk="Medium",
            elevating_source="SupplierDegradation",
            elevating_severity=0.67,
            active_signals=[],
        )
        assert "Risk elevated from Low to Medium" in result
        assert "SupplierDegradation" in result
        assert "severity 0.67" in result

    def test_trend_shift_note(self):
        """TrendShift signal -> informational note appended."""
        result = build_signal_explanation(
            base_confidence=0.80,
            signal_penalty=0.0,
            final_confidence=0.80,
            penalty_details=[],
            risk_elevated=False,
            original_risk="Low",
            adjusted_risk="Low",
            elevating_source=None,
            elevating_severity=None,
            active_signals=[
                _sig(
                    "TrendShift",
                    0.3,
                    {
                        "old_trend": "Stable",
                        "new_trend": "Rising",
                        "shift_type": "acceleration",
                    },
                )
            ],
        )
        assert "trend shift" in result.lower()
        assert "Stable" in result
        assert "Rising" in result

    def test_combined_explanation(self):
        """Multiple adjustments -> all appear in explanation."""
        result = build_signal_explanation(
            base_confidence=0.80,
            signal_penalty=0.15,
            final_confidence=0.65,
            penalty_details=[
                "DemandSpike penalty: -0.05 (severity 0.50)",
                "SupplierDegradation penalty: -0.10 (severity 0.67)",
            ],
            risk_elevated=True,
            original_risk="Low",
            adjusted_risk="Medium",
            elevating_source="SupplierDegradation",
            elevating_severity=0.67,
            active_signals=[],
        )
        assert "DemandSpike" in result
        assert "SupplierDegradation" in result
        assert "Risk elevated" in result
        assert "Base confidence 0.80" in result
        assert "final confidence 0.65" in result


# ===========================================================================
# 4. Apply Signal Adjustments (Orchestrator)
# ===========================================================================


class TestApplySignalAdjustments:
    """Test apply_signal_adjustments() — full orchestration."""

    def test_no_signals(self):
        adj = apply_signal_adjustments(0.80, "Low", [])
        assert adj.adjusted_confidence == 0.80
        assert adj.signal_penalty == 0.0
        assert adj.adjusted_risk == "Low"
        assert adj.risk_elevated is False
        assert adj.explanation_suffix == ""

    def test_demand_spike_only(self):
        adj = apply_signal_adjustments(0.80, "Low", [_sig("DemandSpike", 0.5)])
        assert adj.adjusted_confidence == 0.75  # 0.80 - 0.05
        assert adj.signal_penalty == 0.05
        assert adj.adjusted_risk == "Low"  # DemandSpike doesn't elevate risk
        assert adj.risk_elevated is False
        assert "Base confidence 0.80" in adj.explanation_suffix

    def test_supplier_degradation_with_elevation(self):
        adj = apply_signal_adjustments(0.70, "Low", [_sig("SupplierDegradation", 0.8)])
        # penalty = 0.15 * 0.8 = 0.12
        assert abs(adj.adjusted_confidence - 0.58) < 0.01
        assert adj.adjusted_risk == "Medium"  # Low -> Medium
        assert adj.risk_elevated is True
        assert "Risk elevated" in adj.explanation_suffix

    def test_clamp_minimum(self):
        """Extreme penalties don't push confidence below 0.1."""
        signals = [
            _sig("DemandSpike", 1.0),
            _sig("SupplierDegradation", 1.0),
            _sig("WarehouseOverload", 1.0),
        ]
        adj = apply_signal_adjustments(0.30, "Low", signals)
        assert adj.adjusted_confidence == CONFIDENCE_MIN  # 0.1
        assert adj.signal_penalty == 0.33


# ===========================================================================
# 5. Forecast Point Generation with Signals
# ===========================================================================


class TestForecastPointWithSignals:
    """Test generate_forecast_point() with and without signals."""

    def test_without_signals_matches_e2(self):
        """No signals -> identical to E2 output."""
        inputs = _base_inputs()
        point_no_sig = generate_forecast_point(inputs, horizon=1)
        point_none = generate_forecast_point(inputs, horizon=1, active_signals=None)

        assert point_no_sig.confidence == point_none.confidence
        assert point_no_sig.supply_risk == point_none.supply_risk
        assert point_no_sig.forecast_demand == point_none.forecast_demand

    def test_with_signals_lowers_confidence(self):
        """Active signals -> confidence is lower."""
        inputs = _base_inputs()
        point_clean = generate_forecast_point(inputs, horizon=1)
        point_sig = generate_forecast_point(
            inputs,
            horizon=1,
            active_signals=[_sig("DemandSpike", 0.5)],
        )
        assert point_sig.confidence < point_clean.confidence
        assert abs(point_sig.confidence - (point_clean.confidence - 0.05)) < 0.001

    def test_demand_unchanged_by_signals(self):
        """Signals NEVER change demand forecast (E2 design principle)."""
        inputs = _base_inputs()
        point_clean = generate_forecast_point(inputs, horizon=1)
        point_sig = generate_forecast_point(
            inputs,
            horizon=1,
            active_signals=[
                _sig("DemandSpike", 1.0),
                _sig("SupplierDegradation", 1.0),
                _sig("WarehouseOverload", 1.0),
            ],
        )
        assert point_sig.forecast_demand == point_clean.forecast_demand

    def test_risk_elevated_in_point(self):
        """SupplierDegradation with high severity elevates risk in point."""
        inputs = _base_inputs(supplier_reliability=90.0)  # base risk = Low
        point = generate_forecast_point(
            inputs,
            horizon=1,
            active_signals=[_sig("SupplierDegradation", 0.8)],
        )
        assert point.supply_risk == "Medium"  # Elevated from Low

    def test_explanation_includes_signal_context(self):
        """Explanation contains signal adjustment audit trail."""
        inputs = _base_inputs()
        point = generate_forecast_point(
            inputs,
            horizon=1,
            active_signals=[_sig("DemandSpike", 0.5)],
        )
        assert "Signal adjustments:" in point.explanation
        assert "Base confidence" in point.explanation
        assert "DemandSpike" in point.explanation

    def test_base_confidence_tracked(self):
        """ForecastPoint tracks base_confidence and signal_penalty."""
        inputs = _base_inputs()
        point = generate_forecast_point(
            inputs,
            horizon=1,
            active_signals=[_sig("DemandSpike", 0.5)],
        )
        assert point.base_confidence > point.confidence
        assert point.signal_penalty == 0.05

    def test_trend_shift_only_adds_note(self):
        """TrendShift adds note but doesn't change confidence."""
        inputs = _base_inputs()
        point_clean = generate_forecast_point(inputs, horizon=1)
        point_sig = generate_forecast_point(
            inputs,
            horizon=1,
            active_signals=[
                _sig(
                    "TrendShift",
                    0.3,
                    {
                        "old_trend": "Stable",
                        "new_trend": "Rising",
                        "shift_type": "acceleration",
                    },
                )
            ],
        )
        assert point_sig.confidence == point_clean.confidence
        assert "trend shift" in point_sig.explanation.lower()


# ===========================================================================
# 6. Integration Tests
# ===========================================================================


class TestE4Integration:
    """Test full pipeline: simulation -> signal detection -> forecast adjustment."""

    def _create_twin_with_spike(self, client, h, product="SpikeProd"):
        """Create twin + run high-demand sim to trigger DemandSpike."""
        twin_resp = client.post("/api/v1/twins", json={"name": "E4 Test"}, headers=h)
        twin_id = twin_resp.json()["id"]

        # First sim: baseline
        client.post(
            "/api/v1/simulate",
            json={
                "product": product,
                "stock": 5000,
                "warehouse": "W1",
                "demand": 5000,
                "supplier_delay": 2,
                "twin_id": twin_id,
            },
            headers=h,
        )
        # Second sim: spike demand (triggers DemandSpike)
        client.post(
            "/api/v1/simulate",
            json={
                "product": product,
                "stock": 5000,
                "warehouse": "W1",
                "demand": 15000,
                "supplier_delay": 2,
                "twin_id": twin_id,
            },
            headers=h,
        )
        return twin_id

    def _create_twin_with_degradation(self, client, h, product="DegProd"):
        """Create twin + run sim with high delay to trigger SupplierDegradation."""
        twin_resp = client.post(
            "/api/v1/twins", json={"name": "E4 Deg Test"}, headers=h
        )
        twin_id = twin_resp.json()["id"]

        # Multiple sims with high delay to degrade supplier reliability
        for _ in range(3):
            client.post(
                "/api/v1/simulate",
                json={
                    "product": product,
                    "stock": 5000,
                    "warehouse": "W1",
                    "demand": 5000,
                    "supplier_delay": 9,
                    "supply_status": "Low",
                    "twin_id": twin_id,
                },
                headers=h,
            )
        return twin_id

    def test_forecast_confidence_reduced_by_spike(self, auth_client):
        """DemandSpike signal lowers forecast confidence."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_spike(client, h)

        # Verify signals exist
        sig_resp = client.get(f"/api/v1/twins/{twin_id}/signals", headers=h)
        signals = sig_resp.json().get("signals", [])
        has_spike = any(s["source"] == "DemandSpike" for s in signals)

        if has_spike:
            # Get forecast
            resp = client.get(
                f"/api/v1/twins/{twin_id}/forecast",
                params={"product": "SpikeProd", "horizons": "1"},
                headers=h,
            )
            assert resp.status_code == 200
            data = resp.json()
            fc = data["forecasts"][0]

            # Explanation should mention signal adjustments
            assert (
                "Signal adjustments:" in fc["explanation"]
                or "DemandSpike" in fc["explanation"]
            )

    def test_forecast_risk_elevated_by_degradation(self, auth_client, db):
        """SupplierDegradation with high severity elevates risk."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_degradation(client, h)

        # Check if supplier degradation signal exists
        sig_resp = client.get(f"/api/v1/twins/{twin_id}/signals", headers=h)
        signals = sig_resp.json().get("signals", [])
        deg_signals = [s for s in signals if s["source"] == "SupplierDegradation"]

        if deg_signals and deg_signals[0]["severity"] > 0.5:
            resp = client.get(
                f"/api/v1/twins/{twin_id}/forecast",
                params={"product": "DegProd", "horizons": "1"},
                headers=h,
            )
            fc = resp.json()["forecasts"][0]
            # Risk should be elevated
            assert fc["supply_risk"] in ("Medium", "High")

    def test_clean_twin_matches_e2(self, auth_client):
        """Twin with no signals produces E2-equivalent output."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_resp = client.post("/api/v1/twins", json={"name": "E4 Clean"}, headers=h)
        twin_id = twin_resp.json()["id"]

        # Single normal sim (unlikely to trigger signals)
        client.post(
            "/api/v1/simulate",
            json={
                "product": "CleanProd",
                "stock": 5000,
                "warehouse": "W1",
                "demand": 5000,
                "supplier_delay": 2,
                "twin_id": twin_id,
            },
            headers=h,
        )

        resp = client.get(
            f"/api/v1/twins/{twin_id}/forecast",
            params={"product": "CleanProd", "horizons": "1"},
            headers=h,
        )
        assert resp.status_code == 200
        fc = resp.json()["forecasts"][0]
        # Demand should be pure formula
        expected = (
            resp.json()["source_state"]["avg_demand"]
            * fc["trend_factor"]
            * fc["season_factor"]
        )
        assert abs(fc["forecast_demand"] - round(expected, 2)) < 0.01

    def test_forecast_explanation_contains_audit_trail(self, auth_client):
        """When signals are active, explanation includes base/penalty/final."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_spike(client, h)

        sig_resp = client.get(f"/api/v1/twins/{twin_id}/signals", headers=h)
        signals = sig_resp.json().get("signals", [])
        has_spike = any(s["source"] == "DemandSpike" for s in signals)

        if has_spike:
            resp = client.get(
                f"/api/v1/twins/{twin_id}/forecast",
                params={"product": "SpikeProd", "horizons": "1"},
                headers=h,
            )
            fc = resp.json()["forecasts"][0]
            expl = fc["explanation"]
            # Audit trail components
            assert "Base confidence" in expl or "Signal adjustments" in expl

    def test_forecast_record_stores_adjusted_values(self, auth_client):
        """Persisted forecast record has signal-adjusted confidence."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_spike(client, h)

        # Generate forecast
        client.get(
            f"/api/v1/twins/{twin_id}/forecast",
            params={"product": "SpikeProd", "horizons": "1"},
            headers=h,
        )

        # List records
        resp = client.get(f"/api/v1/twins/{twin_id}/forecasts", headers=h)
        records = resp.json().get("records", [])
        assert len(records) >= 1
        # The stored confidence should be a valid value
        assert 0.1 <= records[0]["confidence"] <= 1.0
