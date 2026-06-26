"""
E8 Data isolation tests.

Verifies that:
  - Organization A cannot access Organization B's data
  - Simulations are scoped to the creating org
  - Digital Twins are scoped to the creating org
  - Cross-org access attempts return 404 (not 403, to avoid information leaks)
"""

from tests.conftest import _auth_headers, _register_user


class TestDataIsolation:
    """Verify that resources from one org are invisible to another."""

    def _setup_two_orgs(self, client):
        """Create two users in separate orgs."""
        org_a = _register_user(client, email="a@synchain.io", org_name="Org A")
        org_b = _register_user(client, email="b@synchain.io", org_name="Org B")
        return (
            _auth_headers(org_a["access_token"]),
            org_a,
            _auth_headers(org_b["access_token"]),
            org_b,
        )

    def test_twin_isolation(self, client):
        """Org B cannot see Org A's twins."""
        headers_a, data_a, headers_b, data_b = self._setup_two_orgs(client)

        # Org A creates a twin
        resp = client.post(
            "/api/v1/twins",
            json={"name": "A-Twin"},
            headers=headers_a,
        )
        assert resp.status_code == 200
        twin_id = resp.json()["id"]

        # Org A can see it
        resp = client.get(f"/api/v1/twins/{twin_id}", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["name"] == "A-Twin"

        # Org B cannot see it
        resp = client.get(f"/api/v1/twins/{twin_id}", headers=headers_b)
        assert resp.status_code == 404

    def test_twin_list_isolation(self, client):
        """Each org only sees its own twins."""
        headers_a, _, headers_b, _ = self._setup_two_orgs(client)

        client.post("/api/v1/twins", json={"name": "A-1"}, headers=headers_a)
        client.post("/api/v1/twins", json={"name": "A-2"}, headers=headers_a)
        client.post("/api/v1/twins", json={"name": "B-1"}, headers=headers_b)

        resp_a = client.get("/api/v1/twins", headers=headers_a)
        resp_b = client.get("/api/v1/twins", headers=headers_b)

        assert len(resp_a.json()) == 2
        assert len(resp_b.json()) == 1
        assert resp_b.json()[0]["name"] == "B-1"

    def test_simulation_isolation(self, client):
        """Org B cannot see Org A's simulations."""
        headers_a, _, headers_b, _ = self._setup_two_orgs(client)

        # Org A runs a simulation
        sim_resp = client.post(
            "/api/v1/simulate",
            json={
                "product": "Widget",
                "stock": 100,
                "warehouse": "W1",
                "demand": 50,
                "supplier_delay": 2,
                "market_trend": "Positive",
                "supply_status": "High",
                "season": "Normal",
            },
            headers=headers_a,
        )
        assert sim_resp.status_code in (200, 201), f"Simulate failed: {sim_resp.text}"
        sim_id = sim_resp.json()["simulation_id"]

        # Org A can access it
        resp = client.get(f"/api/v1/simulate/{sim_id}", headers=headers_a)
        assert resp.status_code == 200

        # Org B cannot access it
        resp = client.get(f"/api/v1/simulate/{sim_id}", headers=headers_b)
        assert resp.status_code == 404

    def test_simulation_list_isolation(self, client):
        """Simulation list is org-scoped."""
        headers_a, _, headers_b, _ = self._setup_two_orgs(client)

        # Both orgs run simulations
        for _ in range(3):
            resp = client.post(
                "/api/v1/simulate",
                json={
                    "product": "W",
                    "stock": 100,
                    "warehouse": "W1",
                    "demand": 50,
                    "supplier_delay": 2,
                    "market_trend": "Positive",
                    "supply_status": "High",
                    "season": "Normal",
                },
                headers=headers_a,
            )
            assert resp.status_code in (200, 201), f"Simulate A failed: {resp.text}"

        resp = client.post(
            "/api/v1/simulate",
            json={
                "product": "X",
                "stock": 50,
                "warehouse": "W2",
                "demand": 25,
                "supplier_delay": 1,
                "market_trend": "Negative",
                "supply_status": "Low",
                "season": "Festival",
            },
            headers=headers_b,
        )
        assert resp.status_code in (200, 201), f"Simulate B failed: {resp.text}"

        resp_a = client.get("/api/v1/simulations", headers=headers_a)
        resp_b = client.get("/api/v1/simulations", headers=headers_b)

        assert len(resp_a.json()) == 3
        assert len(resp_b.json()) == 1

    def test_cross_org_twin_delete_blocked(self, client):
        """Org B cannot delete Org A's twin."""
        headers_a, _, headers_b, _ = self._setup_two_orgs(client)

        resp = client.post(
            "/api/v1/twins", json={"name": "Protected"}, headers=headers_a
        )
        twin_id = resp.json()["id"]

        resp = client.delete(f"/api/v1/twins/{twin_id}", headers=headers_b)
        assert resp.status_code in (403, 404)

    def test_cross_org_scenario_blocked(self, client):
        """Org B cannot run scenarios on Org A's simulation."""
        headers_a, _, headers_b, _ = self._setup_two_orgs(client)

        sim_resp = client.post(
            "/api/v1/simulate",
            json={
                "product": "Q",
                "stock": 100,
                "warehouse": "W1",
                "demand": 50,
                "supplier_delay": 2,
                "market_trend": "Positive",
                "supply_status": "High",
                "season": "Normal",
            },
            headers=headers_a,
        )
        assert sim_resp.status_code in (200, 201), f"Simulate failed: {sim_resp.text}"
        sim_id = sim_resp.json()["simulation_id"]

        resp = client.get(f"/api/v1/simulate/{sim_id}/scenarios", headers=headers_b)
        assert resp.status_code == 404


class TestUnauthenticatedAccess:
    """Verify all protected endpoints reject unauthenticated requests."""

    def test_simulate_requires_auth(self, client, monkeypatch):
        from config import settings

        monkeypatch.setattr(settings, "debug", False)
        resp = client.post(
            "/api/v1/simulate",
            json={
                "product": "X",
                "stock": 100,
                "warehouse": "W1",
                "demand": 50,
                "supplier_delay": 2,
                "market_trend": "Positive",
                "supply_status": "High",
                "season": "Normal",
            },
        )
        assert resp.status_code in (401, 403)

    def test_twins_requires_auth(self, client, monkeypatch):
        from config import settings

        monkeypatch.setattr(settings, "debug", False)
        resp = client.get("/api/v1/twins")
        assert resp.status_code in (401, 403)

    def test_simulations_requires_auth(self, client, monkeypatch):
        from config import settings

        monkeypatch.setattr(settings, "debug", False)
        resp = client.get("/api/v1/simulations")
        assert resp.status_code in (401, 403)

    def test_health_is_public(self, client):
        """Health endpoints should remain public."""
        resp = client.get("/")
        assert resp.status_code == 200
        resp = client.get("/health")
        assert resp.status_code == 200
