"""
Unit tests for Phase E3: Signal Intelligence.

Tests cover:
  1. DemandSpikeDetector (6 tests)
  2. SupplierDegradationDetector (5 tests)
  3. WarehouseOverloadDetector (6 tests)
  4. TrendShiftDetector (7 tests)
  5. SignalEngine orchestration (6 tests)
  6. Health score computation (4 tests)
  7. API endpoints (8 tests)

Total: ~42 tests
"""

import json

from digital_twin.models import (
    DigitalTwin,
    MarketState,
    ProductState,
    SignalEvent,
    SupplierState,
    TwinStateHistory,
    WarehouseState,
)
from signals.detectors import (
    DemandSpikeDetector,
    SupplierDegradationDetector,
    TrendShiftDetector,
    WarehouseOverloadDetector,
)
from signals.engine import SignalEngine, _compute_health_score, _severity_label
from sqlalchemy.orm import Session
from tests.conftest import _auth_headers

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_twin_with_state(db: Session, **overrides) -> DigitalTwin:
    """Create a twin with controllable state for testing detectors."""
    twin = DigitalTwin(name="Signal Test", simulation_count=5)
    db.add(twin)
    db.flush()

    ps = ProductState(
        twin_id=twin.id,
        product_name=overrides.get("product", "Widget-A"),
        latest_demand=overrides.get("latest_demand", 10000),
        avg_demand=overrides.get("avg_demand", 8000),
        demand_trend=overrides.get("demand_trend", "Stable"),
        latest_stock=5000,
        simulation_count=5,
    )
    db.add(ps)

    ss = SupplierState(
        twin_id=twin.id,
        avg_delay=overrides.get("avg_delay", 3.0),
        max_delay_seen=overrides.get("max_delay_seen", 7.0),
        reliability_score=overrides.get("reliability_score", 57.14),
        supply_status_mode="Medium",
    )
    db.add(ss)

    for wh_id, util in [
        ("W1", overrides.get("w1_util", 0.5)),
        ("W2", overrides.get("w2_util", 0.3)),
        ("W3", overrides.get("w3_util", 0.2)),
    ]:
        ws = WarehouseState(
            twin_id=twin.id,
            warehouse_id=wh_id,
            utilization_pct=util,
            times_selected=1,
        )
        db.add(ws)

    ms = MarketState(
        twin_id=twin.id,
        trend_mode="Neutral",
        season_mode="Normal",
    )
    db.add(ms)

    db.commit()
    db.refresh(twin)
    return twin


# ===========================================================================
# 1. DemandSpikeDetector
# ===========================================================================


class TestDemandSpikeDetector:
    def test_spike_detected_above_threshold(self, db):
        """Demand 50% above average triggers spike signal."""
        twin = _create_twin_with_state(db, latest_demand=12000, avg_demand=8000)
        detector = DemandSpikeDetector()
        signals = detector.evaluate(twin, db)
        assert len(signals) == 1
        assert signals[0].source == "DemandSpike"
        assert signals[0].signal_type == "demand"

    def test_severity_formula(self, db):
        """Severity = spike_ratio - 1.0 (capped at 1.0)."""
        twin = _create_twin_with_state(db, latest_demand=12000, avg_demand=8000)
        detector = DemandSpikeDetector()
        signals = detector.evaluate(twin, db)
        assert abs(signals[0].severity - 0.5) < 0.01  # 12000/8000 - 1.0 = 0.5

    def test_no_spike_below_threshold(self, db):
        """Demand within 25% of average does not trigger."""
        twin = _create_twin_with_state(db, latest_demand=9000, avg_demand=8000)
        detector = DemandSpikeDetector()
        signals = detector.evaluate(twin, db)
        assert len(signals) == 0

    def test_exactly_at_threshold(self, db):
        """Demand exactly at 1.25× does not trigger (must be >)."""
        twin = _create_twin_with_state(db, latest_demand=10000, avg_demand=8000)
        detector = DemandSpikeDetector()
        signals = detector.evaluate(twin, db)
        assert len(signals) == 0

    def test_severity_capped_at_one(self, db):
        """Severity never exceeds 1.0 even for extreme spikes."""
        twin = _create_twin_with_state(db, latest_demand=20000, avg_demand=8000)
        detector = DemandSpikeDetector()
        signals = detector.evaluate(twin, db)
        assert signals[0].severity == 1.0

    def test_zero_avg_demand_skipped(self, db):
        """Products with zero average demand are skipped (avoid division by zero)."""
        twin = _create_twin_with_state(db, latest_demand=5000, avg_demand=0)
        detector = DemandSpikeDetector()
        signals = detector.evaluate(twin, db)
        assert len(signals) == 0


# ===========================================================================
# 2. SupplierDegradationDetector
# ===========================================================================


class TestSupplierDegradationDetector:
    def test_degradation_detected(self, db):
        """Reliability below 60 triggers degradation signal."""
        twin = _create_twin_with_state(db, reliability_score=40.0)
        detector = SupplierDegradationDetector()
        signals = detector.evaluate(twin, db)
        assert len(signals) == 1
        assert signals[0].source == "SupplierDegradation"

    def test_severity_formula(self, db):
        """Severity = (60 - score) / 60."""
        twin = _create_twin_with_state(db, reliability_score=30.0)
        detector = SupplierDegradationDetector()
        signals = detector.evaluate(twin, db)
        assert abs(signals[0].severity - 0.5) < 0.01

    def test_no_signal_when_healthy(self, db):
        """Score >= 60 does not trigger."""
        twin = _create_twin_with_state(db, reliability_score=80.0)
        detector = SupplierDegradationDetector()
        signals = detector.evaluate(twin, db)
        assert len(signals) == 0

    def test_exactly_at_threshold(self, db):
        """Score exactly 60 does not trigger (must be <)."""
        twin = _create_twin_with_state(db, reliability_score=60.0)
        detector = SupplierDegradationDetector()
        signals = detector.evaluate(twin, db)
        assert len(signals) == 0

    def test_payload_contents(self, db):
        """Payload contains all relevant supplier metrics."""
        twin = _create_twin_with_state(
            db, reliability_score=40.0, avg_delay=5.0, max_delay_seen=10.0
        )
        detector = SupplierDegradationDetector()
        signals = detector.evaluate(twin, db)
        p = signals[0].payload
        assert "reliability_score" in p
        assert "avg_delay" in p
        assert "max_delay_seen" in p


# ===========================================================================
# 3. WarehouseOverloadDetector
# ===========================================================================


class TestWarehouseOverloadDetector:
    def test_overload_detected(self, db):
        """Utilization > 85% triggers overload signal."""
        twin = _create_twin_with_state(db, w1_util=0.92)
        detector = WarehouseOverloadDetector()
        signals = detector.evaluate(twin, db)
        assert len(signals) == 1
        assert signals[0].payload["warehouse_id"] == "W1"

    def test_severity_formula(self, db):
        """Severity = (util - 0.85) / 0.15."""
        twin = _create_twin_with_state(db, w1_util=0.925)
        detector = WarehouseOverloadDetector()
        signals = detector.evaluate(twin, db)
        assert abs(signals[0].severity - 0.5) < 0.01

    def test_no_signal_below_threshold(self, db):
        """Utilization <= 85% does not trigger."""
        twin = _create_twin_with_state(db, w1_util=0.80)
        detector = WarehouseOverloadDetector()
        signals = detector.evaluate(twin, db)
        assert len(signals) == 0

    def test_multiple_warehouses(self, db):
        """Multiple overloaded warehouses emit multiple signals."""
        twin = _create_twin_with_state(db, w1_util=0.90, w2_util=0.95)
        detector = WarehouseOverloadDetector()
        signals = detector.evaluate(twin, db)
        assert len(signals) == 2

    def test_severity_capped_at_one(self, db):
        """Extreme utilization (>1.0) caps severity at 1.0."""
        twin = _create_twin_with_state(db, w1_util=1.2)
        detector = WarehouseOverloadDetector()
        signals = detector.evaluate(twin, db)
        assert signals[0].severity == 1.0

    def test_exactly_at_threshold(self, db):
        """Utilization exactly at 0.85 does not trigger (must be >)."""
        twin = _create_twin_with_state(db, w1_util=0.85)
        detector = WarehouseOverloadDetector()
        signals = detector.evaluate(twin, db)
        assert len(signals) == 0


# ===========================================================================
# 4. TrendShiftDetector
# ===========================================================================


class TestTrendShiftDetector:
    def _add_trend_change(
        self, db: Session, twin_id: int, product: str, old_t: str, new_t: str
    ):
        entry = TwinStateHistory(
            twin_id=twin_id,
            entity_type="product",
            entity_id=product,
            field_name="demand_trend",
            old_value=json.dumps(old_t),
            new_value=json.dumps(new_t),
        )
        db.add(entry)
        db.commit()

    def test_stable_to_rising(self, db):
        """Stable→Rising shift detected with severity 0.3."""
        twin = _create_twin_with_state(db)
        self._add_trend_change(db, twin.id, "Widget-A", "Stable", "Rising")
        detector = TrendShiftDetector()
        signals = detector.evaluate(twin, db)
        assert len(signals) == 1
        assert signals[0].severity == 0.3
        assert signals[0].payload["shift_type"] == "acceleration"

    def test_rising_to_falling_reversal(self, db):
        """Rising→Falling reversal has high severity 0.8."""
        twin = _create_twin_with_state(db)
        self._add_trend_change(db, twin.id, "Widget-A", "Rising", "Falling")
        detector = TrendShiftDetector()
        signals = detector.evaluate(twin, db)
        assert len(signals) == 1
        assert signals[0].severity == 0.8
        assert signals[0].payload["shift_type"] == "reversal"

    def test_falling_to_stable_deceleration(self, db):
        """Falling→Stable has low severity 0.2."""
        twin = _create_twin_with_state(db)
        self._add_trend_change(db, twin.id, "Widget-A", "Falling", "Stable")
        detector = TrendShiftDetector()
        signals = detector.evaluate(twin, db)
        assert len(signals) == 1
        assert signals[0].severity == 0.2

    def test_no_history_no_signal(self, db):
        """No trend changes in history → no signal."""
        twin = _create_twin_with_state(db)
        detector = TrendShiftDetector()
        signals = detector.evaluate(twin, db)
        assert len(signals) == 0

    def test_same_trend_no_signal(self, db):
        """Same old/new trend → no signal."""
        twin = _create_twin_with_state(db)
        self._add_trend_change(db, twin.id, "Widget-A", "Stable", "Stable")
        detector = TrendShiftDetector()
        signals = detector.evaluate(twin, db)
        assert len(signals) == 0

    def test_only_latest_per_product(self, db):
        """Multiple trend changes → only the latest per product is considered."""
        twin = _create_twin_with_state(db)
        self._add_trend_change(db, twin.id, "Widget-A", "Stable", "Rising")
        self._add_trend_change(db, twin.id, "Widget-A", "Rising", "Falling")
        detector = TrendShiftDetector()
        signals = detector.evaluate(twin, db)
        # Should use the latest change (Rising→Falling)
        assert len(signals) == 1
        assert signals[0].payload["old_trend"] == "Rising"
        assert signals[0].payload["new_trend"] == "Falling"

    def test_market_signal_type(self, db):
        """TrendShift has signal_type 'market'."""
        twin = _create_twin_with_state(db)
        self._add_trend_change(db, twin.id, "Widget-A", "Stable", "Rising")
        detector = TrendShiftDetector()
        signals = detector.evaluate(twin, db)
        assert signals[0].signal_type == "market"


# ===========================================================================
# 5. SignalEngine orchestration
# ===========================================================================


class TestSignalEngine:
    def test_evaluate_persists_signals(self, db):
        """Engine evaluate() persists signals to signal_events table."""
        twin = _create_twin_with_state(
            db,
            latest_demand=12000,
            avg_demand=8000,
            reliability_score=40.0,
        )
        engine = SignalEngine(db)
        events = engine.evaluate(twin)
        assert len(events) >= 2  # DemandSpike + SupplierDegradation at minimum

    def test_no_signals_for_healthy_twin(self, db):
        """Healthy twin state emits zero signals."""
        twin = _create_twin_with_state(
            db,
            latest_demand=8000,
            avg_demand=8000,
            reliability_score=90.0,
        )
        engine = SignalEngine(db)
        events = engine.evaluate(twin)
        assert len(events) == 0

    def test_list_signals_filtering(self, db):
        """list_signals supports filtering by type and severity."""
        twin = _create_twin_with_state(
            db,
            latest_demand=12000,
            avg_demand=8000,
            reliability_score=40.0,
        )
        engine = SignalEngine(db)
        engine.evaluate(twin)
        db.commit()

        all_signals = engine.list_signals(twin.id)
        demand_only = engine.list_signals(twin.id, signal_type="demand")
        high_only = engine.list_signals(twin.id, min_severity=0.4)

        assert len(demand_only) <= len(all_signals)
        assert all(s.signal_type == "demand" for s in demand_only)
        assert all(s.severity >= 0.4 for s in high_only)

    def test_summary_returns_dict(self, db):
        """get_summary returns properly structured dict."""
        twin = _create_twin_with_state(
            db,
            latest_demand=12000,
            avg_demand=8000,
            reliability_score=40.0,
        )
        engine = SignalEngine(db)
        engine.evaluate(twin)
        db.commit()

        summary = engine.get_summary(twin.id)
        assert "total_signals" in summary
        assert "by_type" in summary
        assert "by_severity" in summary
        assert "health_score" in summary
        assert 0.0 <= summary["health_score"] <= 1.0

    def test_active_signals_for_product(self, db):
        """get_active_signals_for_product returns relevant signals."""
        twin = _create_twin_with_state(
            db,
            latest_demand=12000,
            avg_demand=8000,
            reliability_score=40.0,
        )
        engine = SignalEngine(db)
        engine.evaluate(twin)
        db.commit()

        signals = engine.get_active_signals_for_product(twin.id, "Widget-A")
        # Should include demand signal for Widget-A AND supply signal (twin-wide)
        assert len(signals) >= 2

    def test_empty_twin_no_errors(self, db):
        """Engine handles twin with no state gracefully."""
        twin = DigitalTwin(name="Empty")
        db.add(twin)
        db.commit()
        db.refresh(twin)

        engine = SignalEngine(db)
        events = engine.evaluate(twin)
        assert len(events) == 0


# ===========================================================================
# 6. Health score computation
# ===========================================================================


class TestHealthScore:
    def test_no_signals_is_healthy(self, db):
        """No signals → health_score = 1.0."""
        assert _compute_health_score([]) == 1.0

    def test_all_critical_signals(self, db):
        """All severity=1.0 → health_score near 0.0."""
        twin = _create_twin_with_state(db)
        events = []
        for i in range(5):
            e = SignalEvent(
                twin_id=twin.id,
                source="test",
                signal_type="demand",
                severity=1.0,
                payload="{}",
            )
            db.add(e)
            events.append(e)
        db.commit()
        score = _compute_health_score(events)
        assert score == 0.0

    def test_mixed_severity_signals(self, db):
        """Mixed severities produce intermediate health score."""
        twin = _create_twin_with_state(db)
        events = []
        for sev in [0.2, 0.5, 0.8]:
            e = SignalEvent(
                twin_id=twin.id,
                source="test",
                signal_type="demand",
                severity=sev,
                payload="{}",
            )
            db.add(e)
            events.append(e)
        db.commit()
        score = _compute_health_score(events)
        assert 0.0 < score < 1.0

    def test_severity_labels(self, db):
        """Severity label classification boundaries."""
        assert _severity_label(0.0) == "info"
        assert _severity_label(0.29) == "info"
        assert _severity_label(0.3) == "warning"
        assert _severity_label(0.69) == "warning"
        assert _severity_label(0.7) == "critical"
        assert _severity_label(1.0) == "critical"


# ===========================================================================
# 7. API endpoints
# ===========================================================================


class TestSignalAPI:
    def _setup_twin_with_signals(self, client, h) -> int:
        """Create twin, run simulations that trigger signals, return twin_id."""
        r = client.post("/api/v1/twins", json={"name": "Signal API Test"}, headers=h)
        twin_id = r.json()["id"]

        # High demand spike simulation
        client.post(
            "/api/v1/simulate",
            json={
                "product": "TestProduct",
                "stock": 5000,
                "warehouse": "W1",
                "demand": 15000,
                "supplier_delay": 8,
                "market_trend": "Negative",
                "supply_status": "Low",
                "season": "Festival",
                "twin_id": twin_id,
            },
            headers=h,
        )
        return twin_id

    def test_list_signals_endpoint(self, auth_client):
        """GET /signals returns signal list."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._setup_twin_with_signals(client, h)
        r = client.get(f"/api/v1/twins/{twin_id}/signals", headers=h)
        assert r.status_code == 200
        body = r.json()
        assert "signals" in body
        assert "total_signals" in body

    def test_filter_by_type(self, auth_client):
        """GET /signals?signal_type=supply filters correctly."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._setup_twin_with_signals(client, h)
        r = client.get(
            f"/api/v1/twins/{twin_id}/signals",
            params={"signal_type": "supply"},
            headers=h,
        )
        assert r.status_code == 200
        for s in r.json()["signals"]:
            assert s["signal_type"] == "supply"

    def test_filter_by_severity(self, auth_client):
        """GET /signals?min_severity=0.5 filters correctly."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._setup_twin_with_signals(client, h)
        r = client.get(
            f"/api/v1/twins/{twin_id}/signals", params={"min_severity": 0.5}, headers=h
        )
        assert r.status_code == 200
        for s in r.json()["signals"]:
            assert s["severity"] >= 0.5

    def test_signal_summary_endpoint(self, auth_client):
        """GET /signals/summary returns health score and counts."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._setup_twin_with_signals(client, h)
        r = client.get(f"/api/v1/twins/{twin_id}/signals/summary", headers=h)
        assert r.status_code == 200
        body = r.json()
        assert "health_score" in body
        assert "by_type" in body
        assert "by_severity" in body
        assert 0.0 <= body["health_score"] <= 1.0

    def test_forecast_includes_signals(self, auth_client):
        """GET /forecast now includes active_signals field."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._setup_twin_with_signals(client, h)
        r = client.get(
            f"/api/v1/twins/{twin_id}/forecast",
            params={"product": "TestProduct"},
            headers=h,
        )
        assert r.status_code == 200
        body = r.json()
        assert "active_signals" in body

    def test_invalid_twin_404(self, auth_client):
        """Invalid twin_id returns 404 for signals."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        r = client.get("/api/v1/twins/9999/signals", headers=h)
        assert r.status_code == 404

    def test_invalid_twin_summary_404(self, auth_client):
        """Invalid twin_id returns 404 for signal summary."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        r = client.get("/api/v1/twins/9999/signals/summary", headers=h)
        assert r.status_code == 404

    def test_empty_twin_signals(self, auth_client):
        """Twin with no simulations returns empty signal list."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        r = client.post("/api/v1/twins", json={"name": "Empty"}, headers=h)
        twin_id = r.json()["id"]
        r = client.get(f"/api/v1/twins/{twin_id}/signals", headers=h)
        assert r.status_code == 200
        assert r.json()["total_signals"] == 0
