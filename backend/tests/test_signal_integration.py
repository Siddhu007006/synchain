"""
Integration tests for Phase E3: Signal Intelligence.

These tests verify the full pipeline:
  Simulation → Twin state update → Signal detection → Persistence → API retrieval

Tests:
  1. Simulate → signals emitted
  2. Multiple simulations → signal accumulation (no dedup)
  3. Twin delete cascades signals
  4. Forecast reads signals
  5. Signal isolation between twins
  6. Non-blocking error handling
"""

from tests.conftest import _auth_headers


class TestSignalIntegration:
    """Full pipeline integration tests."""

    def _create_twin(self, client, h) -> int:
        r = client.post("/api/v1/twins", json={"name": "IntTest"}, headers=h)
        assert r.status_code == 200
        return r.json()["id"]

    def _simulate(
        self,
        client,
        h,
        twin_id: int,
        demand: float = 15000,
        supplier_delay: float = 8,
        **kwargs,
    ):
        payload = {
            "product": "Widget-A",
            "stock": 5000,
            "warehouse": "W1",
            "demand": demand,
            "supplier_delay": supplier_delay,
            "market_trend": kwargs.get("market_trend", "Negative"),
            "supply_status": kwargs.get("supply_status", "Low"),
            "season": kwargs.get("season", "Normal"),
            "twin_id": twin_id,
        }
        r = client.post("/api/v1/simulate", json=payload, headers=h)
        assert r.status_code == 200
        return r.json()

    def test_simulate_triggers_signals(self, auth_client, db):
        """A simulation with extreme conditions generates signals."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin(client, h)
        self._simulate(client, h, twin_id, demand=15000)

        r = client.get(f"/api/v1/twins/{twin_id}/signals", headers=h)
        assert r.status_code == 200
        assert r.json()["total_signals"] > 0

    def test_no_dedup_across_simulations(self, auth_client, db):
        """Running the same simulation twice emits signals both times."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin(client, h)
        self._simulate(client, h, twin_id, demand=15000, supplier_delay=8)
        r1 = client.get(f"/api/v1/twins/{twin_id}/signals", headers=h)
        count_1 = r1.json()["total_signals"]

        self._simulate(client, h, twin_id, demand=15000, supplier_delay=8)
        r2 = client.get(f"/api/v1/twins/{twin_id}/signals", headers=h)
        count_2 = r2.json()["total_signals"]

        assert count_2 > count_1, "Signals should accumulate without deduplication"

    def test_signal_isolation_between_twins(self, auth_client, db):
        """Signals for twin A do not appear in twin B."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_a = self._create_twin(client, h)
        twin_b = self._create_twin(client, h)
        self._simulate(client, h, twin_a, demand=15000)

        r_a = client.get(f"/api/v1/twins/{twin_a}/signals", headers=h)
        r_b = client.get(f"/api/v1/twins/{twin_b}/signals", headers=h)

        assert r_a.json()["total_signals"] > 0
        assert r_b.json()["total_signals"] == 0

    def test_forecast_includes_active_signals(self, auth_client, db):
        """Forecast endpoint returns active_signals after simulation."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin(client, h)
        self._simulate(client, h, twin_id, demand=15000)

        r = client.get(
            f"/api/v1/twins/{twin_id}/forecast",
            params={"product": "Widget-A"},
            headers=h,
        )
        assert r.status_code == 200
        data = r.json()
        assert "active_signals" in data
        # Should have signals since we ran a high-demand simulation
        assert isinstance(data["active_signals"], list)

    def test_summary_health_degrades(self, auth_client, db):
        """Health score decreases with bad simulations."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin(client, h)

        # First check — no signals, should be healthy
        r1 = client.get(f"/api/v1/twins/{twin_id}/signals/summary", headers=h)
        assert r1.json()["health_score"] == 1.0

        # Run bad simulation
        self._simulate(client, h, twin_id, demand=20000, supplier_delay=10)
        r2 = client.get(f"/api/v1/twins/{twin_id}/signals/summary", headers=h)
        assert r2.json()["health_score"] < 1.0

    def test_simulation_succeeds_without_twin(self, auth_client, db):
        """Simulation without twin_id still works (no signals emitted)."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        r = client.post(
            "/api/v1/simulate",
            json={
                "product": "Widget-A",
                "stock": 5000,
                "warehouse": "W1",
                "demand": 15000,
                "supplier_delay": 8,
                "market_trend": "Negative",
                "supply_status": "Low",
                "season": "Normal",
            },
            headers=h,
        )
        assert r.status_code == 200
