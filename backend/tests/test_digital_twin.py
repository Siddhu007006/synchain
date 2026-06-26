"""
Digital Twin test suite — Phase E1.

Tests:
  1. math_utils: EWMA, trend detection, reliability scoring
  2. TwinManager: CRUD, state updates, history logging
  3. API endpoints: twin CRUD, simulation→twin link, history
"""

from digital_twin.manager import TwinManager
from digital_twin.math_utils import (
    classify_trend,
    compute_reliability_score,
    compute_selection_rate,
    compute_utilization,
    ewma,
)

# DB fixtures provided by conftest.py
from tests.conftest import _auth_headers

# ===========================================================================
# 1. Math Utils Tests
# ===========================================================================


class TestEWMA:
    """Test EWMA smoothing function."""

    def test_first_data_point(self):
        """First point: returns current_value when old_avg is 0."""
        assert ewma(100.0, 0.0) == 100.0

    def test_smoothing(self):
        """EWMA smooths toward historical average."""
        # α=0.3: new = 0.3×200 + 0.7×100 = 60 + 70 = 130
        result = ewma(200.0, 100.0, alpha=0.3)
        assert result == 130.0

    def test_stability(self):
        """Same value repeated → stays the same."""
        assert ewma(50.0, 50.0) == 50.0

    def test_custom_alpha(self):
        """Custom alpha value works."""
        # α=0.5: new = 0.5×200 + 0.5×100 = 150
        result = ewma(200.0, 100.0, alpha=0.5)
        assert result == 150.0

    def test_convergence_over_iterations(self):
        """EWMA converges toward repeated value over multiple updates."""
        avg = 0.0
        for _ in range(20):
            avg = ewma(100.0, avg)
        # After 20 iterations, should be very close to 100
        assert 99.0 <= avg <= 100.1


class TestTrendClassification:
    """Test demand trend detection."""

    def test_rising(self):
        assert classify_trend(120.0, 100.0) == "Rising"

    def test_falling(self):
        assert classify_trend(80.0, 100.0) == "Falling"

    def test_stable(self):
        assert classify_trend(105.0, 100.0) == "Stable"

    def test_edge_rising_threshold(self):
        """Exactly at 1.10 boundary → Stable (not Rising)."""
        assert classify_trend(110.0, 100.0) == "Stable"

    def test_edge_falling_threshold(self):
        """Exactly at 0.90 boundary → Stable (not Falling)."""
        assert classify_trend(90.0, 100.0) == "Stable"

    def test_zero_avg(self):
        """Zero average → Stable (no division by zero)."""
        assert classify_trend(100.0, 0.0) == "Stable"


class TestReliabilityScore:
    def test_perfect_reliability(self):
        assert compute_reliability_score(0.0, 0.0) == 100.0

    def test_half_reliability(self):
        assert compute_reliability_score(5.0, 10.0) == 50.0

    def test_zero_reliability(self):
        assert compute_reliability_score(10.0, 10.0) == 0.0

    def test_never_negative(self):
        """Score can't go below 0."""
        assert compute_reliability_score(15.0, 10.0) == 0.0


class TestSelectionRate:
    def test_no_simulations(self):
        assert compute_selection_rate(0, 0) == 0.0

    def test_all_selected(self):
        assert compute_selection_rate(10, 10) == 1.0

    def test_partial(self):
        assert compute_selection_rate(3, 10) == 0.3


class TestUtilization:
    def test_zero_capacity(self):
        assert compute_utilization(100.0, 0.0) == 0.0

    def test_full_utilization(self):
        assert compute_utilization(10000.0, 10000.0) == 1.0

    def test_over_utilization(self):
        assert compute_utilization(15000.0, 10000.0) == 1.5


# ===========================================================================
# 2. TwinManager Unit Tests
# ===========================================================================


class TestTwinManagerCRUD:
    """Test TwinManager create/read/list/delete."""

    def test_create_twin(self, db):
        mgr = TwinManager(db)
        twin = mgr.create_twin("Test Chain")
        assert twin.id is not None
        assert twin.name == "Test Chain"
        assert twin.simulation_count == 0

    def test_create_initializes_warehouse_states(self, db):
        mgr = TwinManager(db)
        twin = mgr.create_twin()
        assert len(twin.warehouse_states) == 3
        wh_ids = {ws.warehouse_id for ws in twin.warehouse_states}
        assert wh_ids == {"W1", "W2", "W3"}

    def test_create_initializes_supplier_state(self, db):
        mgr = TwinManager(db)
        twin = mgr.create_twin()
        assert twin.supplier_state is not None
        assert twin.supplier_state.reliability_score == 100.0

    def test_create_initializes_market_state(self, db):
        mgr = TwinManager(db)
        twin = mgr.create_twin()
        assert twin.market_state is not None
        assert twin.market_state.trend_mode == "Neutral"

    def test_get_twin(self, db):
        mgr = TwinManager(db)
        twin = mgr.create_twin("Lookup Test")
        found = mgr.get_twin(twin.id)
        assert found is not None
        assert found.name == "Lookup Test"

    def test_get_nonexistent_twin(self, db):
        mgr = TwinManager(db)
        assert mgr.get_twin(9999) is None

    def test_list_twins(self, db):
        mgr = TwinManager(db)
        mgr.create_twin("A")
        mgr.create_twin("B")
        twins = mgr.list_twins()
        assert len(twins) == 2

    def test_delete_twin(self, db):
        mgr = TwinManager(db)
        twin = mgr.create_twin("Delete Me")
        assert mgr.delete_twin(twin.id) is True
        assert mgr.get_twin(twin.id) is None

    def test_delete_nonexistent(self, db):
        mgr = TwinManager(db)
        assert mgr.delete_twin(9999) is False


class TestTwinManagerStateUpdate:
    """Test TwinManager.update_state_from_simulation."""

    def _sim_input(self, **overrides):
        base = {
            "product": "Widget-A",
            "stock": 5000,
            "warehouse": "W1",
            "demand": 8000,
            "supplier_delay": 4.0,
            "market_trend": "Positive",
            "supply_status": "Medium",
            "season": "Festival",
            "twin_id": None,
        }
        base.update(overrides)
        return base

    def _sim_result(self, **overrides):
        base = {
            "demand_forecast": 9600.0,
            "recommended_inventory": 10560.0,
            "selected_warehouse": "W1",
            "route": "R1",
            "risk": "Medium",
            "strategy": "Increase stock",
            "agent_breakdown": [],
            "overall_confidence": 0.72,
            "explanation": "Test explanation",
        }
        base.update(overrides)
        return base

    def test_first_simulation_creates_product_state(self, db):
        mgr = TwinManager(db)
        twin = mgr.create_twin()
        mgr.update_state_from_simulation(twin.id, self._sim_input(), self._sim_result())
        db.refresh(twin)
        assert len(twin.product_states) == 1
        ps = twin.product_states[0]
        assert ps.product_name == "Widget-A"
        assert ps.latest_demand == 8000
        assert ps.avg_demand == 8000  # first point

    def test_simulation_count_increments(self, db):
        mgr = TwinManager(db)
        twin = mgr.create_twin()
        mgr.update_state_from_simulation(twin.id, self._sim_input(), self._sim_result())
        db.refresh(twin)
        assert twin.simulation_count == 1

    def test_ewma_updates_avg_demand(self, db):
        mgr = TwinManager(db)
        twin = mgr.create_twin()

        # Sim 1: demand=8000 → avg=8000
        mgr.update_state_from_simulation(
            twin.id, self._sim_input(demand=8000), self._sim_result()
        )
        db.refresh(twin)
        ps = twin.product_states[0]
        assert ps.avg_demand == 8000.0

        # Sim 2: demand=10000 → avg = 0.3*10000 + 0.7*8000 = 3000 + 5600 = 8600
        mgr.update_state_from_simulation(
            twin.id, self._sim_input(demand=10000), self._sim_result()
        )
        db.refresh(twin)
        ps = twin.product_states[0]
        assert ps.avg_demand == 8600.0

    def test_warehouse_selection_tracked(self, db):
        mgr = TwinManager(db)
        twin = mgr.create_twin()
        mgr.update_state_from_simulation(
            twin.id,
            self._sim_input(),
            self._sim_result(selected_warehouse="W2"),
        )
        db.refresh(twin)
        w2 = next(ws for ws in twin.warehouse_states if ws.warehouse_id == "W2")
        assert w2.times_selected == 1

    def test_supplier_delay_ewma(self, db):
        mgr = TwinManager(db)
        twin = mgr.create_twin()
        mgr.update_state_from_simulation(
            twin.id, self._sim_input(supplier_delay=10.0), self._sim_result()
        )
        db.refresh(twin)
        assert twin.supplier_state.avg_delay == 10.0
        assert twin.supplier_state.max_delay_seen == 10.0

    def test_market_state_updates(self, db):
        mgr = TwinManager(db)
        twin = mgr.create_twin()
        mgr.update_state_from_simulation(
            twin.id,
            self._sim_input(market_trend="Positive"),
            self._sim_result(overall_confidence=0.85),
        )
        db.refresh(twin)
        assert twin.market_state.trend_mode == "Positive"
        assert twin.market_state.avg_confidence == 0.85

    def test_history_logged(self, db):
        mgr = TwinManager(db)
        twin = mgr.create_twin()
        mgr.update_state_from_simulation(twin.id, self._sim_input(), self._sim_result())
        entries = mgr.get_history(twin.id)
        # Should have multiple history entries (product, warehouse, supplier, market)
        assert len(entries) > 0
        entity_types = {e.entity_type for e in entries}
        assert "product" in entity_types
        assert "warehouse" in entity_types

    def test_nonexistent_twin_returns_none(self, db):
        mgr = TwinManager(db)
        result = mgr.update_state_from_simulation(9999, {}, {})
        assert result is None

    def test_multiple_products_tracked_separately(self, db):
        mgr = TwinManager(db)
        twin = mgr.create_twin()
        mgr.update_state_from_simulation(
            twin.id,
            self._sim_input(product="Widget-A"),
            self._sim_result(),
        )
        mgr.update_state_from_simulation(
            twin.id,
            self._sim_input(product="Widget-B"),
            self._sim_result(),
        )
        db.refresh(twin)
        assert len(twin.product_states) == 2
        names = {ps.product_name for ps in twin.product_states}
        assert names == {"Widget-A", "Widget-B"}


# ===========================================================================
# 3. API Endpoint Tests
# ===========================================================================


class TestTwinAPI:
    """Test Digital Twin REST endpoints."""

    def test_create_twin(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        resp = client.post("/api/v1/twins", json={"name": "Test Chain"}, headers=h)
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Test Chain"
        assert body["simulation_count"] == 0
        assert "id" in body

    def test_list_twins(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        client.post("/api/v1/twins", json={"name": "Chain A"}, headers=h)
        client.post("/api/v1/twins", json={"name": "Chain B"}, headers=h)
        resp = client.get("/api/v1/twins", headers=h)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_twin_detail(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        create_resp = client.post(
            "/api/v1/twins", json={"name": "Detail Test"}, headers=h
        )
        twin_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/twins/{twin_id}", headers=h)
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Detail Test"
        assert len(body["warehouse_states"]) == 3
        assert body["supplier_state"] is not None
        assert body["market_state"] is not None

    def test_get_nonexistent_twin(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        resp = client.get("/api/v1/twins/9999", headers=h)
        assert resp.status_code == 404

    def test_delete_twin(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        create_resp = client.post(
            "/api/v1/twins", json={"name": "Delete Me"}, headers=h
        )
        twin_id = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/twins/{twin_id}", headers=h)
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
        # Verify gone
        get_resp = client.get(f"/api/v1/twins/{twin_id}", headers=h)
        assert get_resp.status_code == 404

    def test_simulate_with_twin_updates_state(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        # Create twin
        twin_resp = client.post("/api/v1/twins", json={"name": "Sim Test"}, headers=h)
        twin_id = twin_resp.json()["id"]

        # Run simulation linked to twin
        sim_payload = {
            "product": "Widget-X",
            "stock": 5000,
            "warehouse": "W1",
            "demand": 8000,
            "supplier_delay": 3,
            "market_trend": "Positive",
            "supply_status": "Medium",
            "season": "Festival",
            "twin_id": twin_id,
        }
        sim_resp = client.post("/api/v1/simulate", json=sim_payload, headers=h)
        assert sim_resp.status_code == 200

        # Check twin state was updated
        twin_detail = client.get(f"/api/v1/twins/{twin_id}", headers=h).json()
        assert twin_detail["simulation_count"] == 1
        assert len(twin_detail["product_states"]) == 1
        assert twin_detail["product_states"][0]["product_name"] == "Widget-X"

    def test_simulate_without_twin_still_works(self, auth_client):
        """Backward compatibility: no twin_id → L2 mode."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        sim_payload = {
            "product": "Widget-Y",
            "stock": 3000,
            "warehouse": "W2",
            "demand": 6000,
            "supplier_delay": 2,
        }
        resp = client.post("/api/v1/simulate", json=sim_payload, headers=h)
        assert resp.status_code == 200

    def test_simulate_with_invalid_twin_returns_404(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        sim_payload = {
            "product": "Widget-Z",
            "stock": 1000,
            "warehouse": "W1",
            "demand": 5000,
            "supplier_delay": 1,
            "twin_id": 9999,
        }
        resp = client.post("/api/v1/simulate", json=sim_payload, headers=h)
        assert resp.status_code == 404

    def test_twin_history(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        # Create twin + run simulation
        twin_resp = client.post(
            "/api/v1/twins", json={"name": "History Test"}, headers=h
        )
        twin_id = twin_resp.json()["id"]
        client.post(
            "/api/v1/simulate",
            json={
                "product": "Widget-H",
                "stock": 2000,
                "warehouse": "W1",
                "demand": 5000,
                "supplier_delay": 2,
                "twin_id": twin_id,
            },
            headers=h,
        )

        # Get history
        resp = client.get(f"/api/v1/twins/{twin_id}/history", headers=h)
        assert resp.status_code == 200
        body = resp.json()
        assert body["twin_id"] == twin_id
        assert body["total_entries"] > 0
        assert len(body["entries"]) > 0

    def test_ewma_convergence_via_api(self, auth_client):
        """Run 5 simulations and verify EWMA converges."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_resp = client.post("/api/v1/twins", json={"name": "EWMA Test"}, headers=h)
        twin_id = twin_resp.json()["id"]

        demands = [8000, 8500, 7800, 8200, 8100]
        for d in demands:
            client.post(
                "/api/v1/simulate",
                json={
                    "product": "Widget-E",
                    "stock": 5000,
                    "warehouse": "W1",
                    "demand": d,
                    "supplier_delay": 3,
                    "twin_id": twin_id,
                },
                headers=h,
            )

        twin_detail = client.get(f"/api/v1/twins/{twin_id}", headers=h).json()
        assert twin_detail["simulation_count"] == 5
        ps = twin_detail["product_states"][0]
        # avg_demand should be between min and max
        assert 7800 <= ps["avg_demand"] <= 8500
        assert ps["demand_trend"] in ["Rising", "Stable", "Falling"]
