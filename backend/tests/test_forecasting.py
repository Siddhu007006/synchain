"""
Forecasting test suite — Phase E2.

Tests:
  1. Pure computation functions (trend, season, supply risk, confidence, demand)
  2. ForecastEngine integration (twin→forecast pipeline)
  3. API endpoints (generate, list, summary)
  4. Backward compatibility (existing endpoints unaffected)
"""

from forecasting.engine import (
    ForecastEngine,
    ForecastInput,
    build_explanation,
    classify_supply_risk,
    compute_confidence,
    compute_forecast_demand,
    compute_season_factor,
    compute_trend_factor,
    generate_forecast_point,
)
from tests.conftest import _auth_headers

# DB fixtures provided by conftest.py


# ===========================================================================
# 1. Pure Computation Tests
# ===========================================================================


class TestTrendFactor:
    """Test trend factor computation."""

    def test_rising_h1(self):
        assert compute_trend_factor("Rising", 1) == 1.05

    def test_rising_h3(self):
        assert compute_trend_factor("Rising", 3) == 1.15

    def test_rising_h5(self):
        assert compute_trend_factor("Rising", 5) == 1.25

    def test_stable_h1(self):
        assert compute_trend_factor("Stable", 1) == 1.0

    def test_stable_h5(self):
        assert compute_trend_factor("Stable", 5) == 1.0

    def test_falling_h1(self):
        assert compute_trend_factor("Falling", 1) == 0.97

    def test_falling_h3(self):
        assert compute_trend_factor("Falling", 3) == 0.91

    def test_falling_h5(self):
        assert compute_trend_factor("Falling", 5) == 0.85

    def test_falling_clamps_above_0_1(self):
        """Extreme horizon shouldn't produce negative factor."""
        result = compute_trend_factor("Falling", 50)
        assert result >= 0.1

    def test_unknown_trend_defaults_stable(self):
        assert compute_trend_factor("Unknown", 3) == 1.0


class TestSeasonFactor:
    """Test season factor mapping."""

    def test_festival(self):
        assert compute_season_factor("Festival") == 1.15

    def test_normal(self):
        assert compute_season_factor("Normal") == 1.0

    def test_off_season(self):
        assert compute_season_factor("Off-season") == 0.85

    def test_unknown_defaults_to_1(self):
        assert compute_season_factor("Unknown") == 1.0


class TestSupplyRisk:
    """Test supply risk classification."""

    def test_high_risk(self):
        assert classify_supply_risk(30.0) == "High"

    def test_medium_risk(self):
        assert classify_supply_risk(65.0) == "Medium"

    def test_low_risk(self):
        assert classify_supply_risk(90.0) == "Low"

    def test_boundary_50(self):
        assert classify_supply_risk(50.0) == "Medium"

    def test_boundary_80(self):
        assert classify_supply_risk(80.0) == "Low"

    def test_zero_reliability(self):
        assert classify_supply_risk(0.0) == "High"

    def test_perfect_reliability(self):
        assert classify_supply_risk(100.0) == "Low"


class TestConfidence:
    """Test confidence score computation."""

    def test_max_confidence(self):
        """10+ sims, h=0 equivalent, stable trend, reliable supplier."""
        result = compute_confidence(
            simulation_count=15, horizon=0, trend="Stable", reliability=90.0
        )
        assert result == 1.0

    def test_base_scaling(self):
        """5 sims → base = 0.5."""
        result = compute_confidence(
            simulation_count=5, horizon=0, trend="Stable", reliability=90.0
        )
        # 0.5 + 0 + 0.05 + 0.05 = 0.6
        assert result == 0.6

    def test_horizon_penalty(self):
        """Each horizon costs -0.10."""
        h1 = compute_confidence(10, 1, "Stable", 90.0)
        h3 = compute_confidence(10, 3, "Stable", 90.0)
        assert h3 < h1
        assert abs(h1 - h3 - 0.20) < 0.001

    def test_unstable_trend_penalty(self):
        """Non-Stable trends get -0.05 instead of +0.05."""
        stable = compute_confidence(10, 1, "Stable", 90.0)
        rising = compute_confidence(10, 1, "Rising", 90.0)
        assert abs((stable - rising) - 0.10) < 0.001  # +0.05 vs -0.05

    def test_unreliable_supplier_penalty(self):
        """Reliability < 50 → -0.10 confidence."""
        reliable = compute_confidence(10, 1, "Stable", 90.0)
        unreliable = compute_confidence(10, 1, "Stable", 30.0)
        assert reliable > unreliable

    def test_clamp_min(self):
        """Confidence never goes below 0.1."""
        result = compute_confidence(1, 10, "Falling", 10.0)
        assert result == 0.1

    def test_clamp_max(self):
        """Confidence never exceeds 1.0."""
        result = compute_confidence(100, 0, "Stable", 100.0)
        assert result == 1.0


class TestForecastDemand:
    """Test pure demand computation (no supply contamination)."""

    def test_basic_calculation(self):
        result = compute_forecast_demand(8000.0, 1.05, 1.15)
        # 8000 × 1.05 × 1.15 = 9660.0
        assert result == 9660.0

    def test_stable_normal(self):
        result = compute_forecast_demand(8000.0, 1.0, 1.0)
        assert result == 8000.0

    def test_falling_off_season(self):
        result = compute_forecast_demand(8000.0, 0.97, 0.85)
        # 8000 × 0.97 × 0.85 = 6596.0
        assert result == 6596.0

    def test_no_supply_contamination(self):
        """Demand doesn't change based on supply — it shouldn't."""
        demand_a = compute_forecast_demand(8000.0, 1.05, 1.15)
        demand_b = compute_forecast_demand(8000.0, 1.05, 1.15)
        assert demand_a == demand_b


class TestExplanation:
    """Test explanation generation."""

    def test_contains_base_demand(self):
        text = build_explanation(
            "Widget-A",
            1,
            8000.0,
            9660.0,
            1.05,
            "Rising",
            1.15,
            "Festival",
            "Medium",
            65.0,
            0.70,
            7,
        )
        assert "8,000.0" in text

    def test_contains_product_name(self):
        text = build_explanation(
            "Widget-A",
            1,
            8000.0,
            9660.0,
            1.05,
            "Rising",
            1.15,
            "Festival",
            "Medium",
            65.0,
            0.70,
            7,
        )
        assert "Widget-A" in text

    def test_contains_supply_risk(self):
        text = build_explanation(
            "Widget-A",
            1,
            8000.0,
            9660.0,
            1.05,
            "Rising",
            1.15,
            "Festival",
            "High",
            30.0,
            0.50,
            3,
        )
        assert "Supply risk: High" in text

    def test_contains_confidence(self):
        text = build_explanation(
            "Widget-A",
            1,
            8000.0,
            9660.0,
            1.05,
            "Rising",
            1.15,
            "Festival",
            "Medium",
            65.0,
            0.70,
            7,
        )
        assert "Confidence: 0.70" in text


class TestForecastPoint:
    """Test generate_forecast_point integration."""

    def test_rising_festival_reliable(self):
        inputs = ForecastInput(
            avg_demand=8000.0,
            demand_trend="Rising",
            simulation_count=10,
            season_mode="Festival",
            supplier_reliability=90.0,
        )
        point = generate_forecast_point(inputs, horizon=1)
        # demand = 8000 × 1.05 × 1.15 = 9660.0
        assert point.forecast_demand == 9660.0
        assert point.trend_factor == 1.05
        assert point.season_factor == 1.15
        assert point.supply_risk == "Low"
        assert point.confidence > 0.5

    def test_stable_normal_unreliable(self):
        inputs = ForecastInput(
            avg_demand=5000.0,
            demand_trend="Stable",
            simulation_count=3,
            season_mode="Normal",
            supplier_reliability=30.0,
        )
        point = generate_forecast_point(inputs, horizon=1)
        # demand = 5000 × 1.0 × 1.0 = 5000.0 (no supply inflation!)
        assert point.forecast_demand == 5000.0
        assert point.supply_risk == "High"
        assert point.confidence < 0.5  # low sims + unreliable


# ===========================================================================
# 2. ForecastEngine Integration Tests
# ===========================================================================


class TestForecastEngine:
    """Test ForecastEngine with real DB."""

    def _create_twin_with_sim(self, client, h, product="Widget-A", demand=8000):
        """Helper: create twin + run simulation to populate state."""
        twin_resp = client.post(
            "/api/v1/twins", json={"name": "Forecast Test"}, headers=h
        )
        twin_id = twin_resp.json()["id"]

        client.post(
            "/api/v1/simulate",
            json={
                "product": product,
                "stock": 5000,
                "warehouse": "W1",
                "demand": demand,
                "supplier_delay": 3,
                "market_trend": "Positive",
                "supply_status": "Medium",
                "season": "Festival",
                "twin_id": twin_id,
            },
            headers=h,
        )
        return twin_id

    def test_generate_returns_forecasts(self, db, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_sim(client, h)
        engine = ForecastEngine(db)
        result = engine.generate(twin_id, "Widget-A", [1, 3, 5])
        assert result is not None
        assert len(result["forecasts"]) == 3
        assert result["source_state"]["avg_demand"] == 8000.0

    def test_generate_nonexistent_twin(self, db):
        engine = ForecastEngine(db)
        assert engine.generate(9999, "Widget-A", [1]) is None

    def test_generate_nonexistent_product(self, db, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_sim(client, h)
        engine = ForecastEngine(db)
        assert engine.generate(twin_id, "NoSuchProduct", [1]) is None

    def test_records_persisted(self, db, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_sim(client, h)
        engine = ForecastEngine(db)
        engine.generate(twin_id, "Widget-A", [1, 3])
        records = engine.list_records(twin_id)
        assert len(records) == 2

    def test_summary_without_forecasts(self, db, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_sim(client, h)
        engine = ForecastEngine(db)
        summaries = engine.get_summary(twin_id)
        assert len(summaries) == 1
        assert summaries[0]["latest_forecast"] is None

    def test_summary_with_forecasts(self, db, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_sim(client, h)
        engine = ForecastEngine(db)
        engine.generate(twin_id, "Widget-A", [1])
        summaries = engine.get_summary(twin_id)
        assert summaries[0]["latest_forecast"] is not None
        assert summaries[0]["latest_forecast"]["forecast_demand"] > 0


# ===========================================================================
# 3. API Endpoint Tests
# ===========================================================================


class TestForecastAPI:
    """Test forecast REST endpoints."""

    def _create_twin_with_sim(self, client, h, product="Widget-X", demand=8000):
        twin_resp = client.post(
            "/api/v1/twins", json={"name": "API Forecast"}, headers=h
        )
        twin_id = twin_resp.json()["id"]
        client.post(
            "/api/v1/simulate",
            json={
                "product": product,
                "stock": 5000,
                "warehouse": "W1",
                "demand": demand,
                "supplier_delay": 3,
                "market_trend": "Positive",
                "supply_status": "Medium",
                "season": "Festival",
                "twin_id": twin_id,
            },
            headers=h,
        )
        return twin_id

    def test_generate_forecast(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_sim(client, h)
        resp = client.get(
            f"/api/v1/twins/{twin_id}/forecast",
            params={"product": "Widget-X"},
            headers=h,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["twin_id"] == twin_id
        assert body["product"] == "Widget-X"
        assert len(body["forecasts"]) == 3  # default horizons 1,3,5
        assert body["source_state"]["avg_demand"] == 8000.0

    def test_generate_forecast_custom_horizons(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_sim(client, h)
        resp = client.get(
            f"/api/v1/twins/{twin_id}/forecast",
            params={"product": "Widget-X", "horizons": "1,2"},
            headers=h,
        )
        assert resp.status_code == 200
        assert len(resp.json()["forecasts"]) == 2

    def test_generate_forecast_missing_product(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_sim(client, h)
        resp = client.get(
            f"/api/v1/twins/{twin_id}/forecast",
            params={"product": "NoProduct"},
            headers=h,
        )
        assert resp.status_code == 404

    def test_generate_forecast_invalid_twin(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        resp = client.get(
            "/api/v1/twins/9999/forecast",
            params={"product": "Widget-X"},
            headers=h,
        )
        assert resp.status_code == 404

    def test_generate_forecast_invalid_horizons(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_sim(client, h)
        resp = client.get(
            f"/api/v1/twins/{twin_id}/forecast",
            params={"product": "Widget-X", "horizons": "abc"},
            headers=h,
        )
        assert resp.status_code == 422  # ValidationError

    def test_demand_not_contaminated_by_supply(self, auth_client):
        """Core E2 design: supply risk doesn't inflate demand."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_sim(client, h)
        resp = client.get(
            f"/api/v1/twins/{twin_id}/forecast",
            params={"product": "Widget-X", "horizons": "1"},
            headers=h,
        )
        body = resp.json()
        fc = body["forecasts"][0]
        # Demand = avg_demand × trend × season. No supply term.
        expected = (
            body["source_state"]["avg_demand"]
            * fc["trend_factor"]
            * fc["season_factor"]
        )
        assert abs(fc["forecast_demand"] - round(expected, 2)) < 0.01

    def test_supply_risk_is_separate_field(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_sim(client, h)
        resp = client.get(
            f"/api/v1/twins/{twin_id}/forecast",
            params={"product": "Widget-X", "horizons": "1"},
            headers=h,
        )
        fc = resp.json()["forecasts"][0]
        assert "supply_risk" in fc
        assert fc["supply_risk"] in ["Low", "Medium", "High"]

    def test_list_forecast_records(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_sim(client, h)
        # Generate forecasts first
        client.get(
            f"/api/v1/twins/{twin_id}/forecast",
            params={"product": "Widget-X"},
            headers=h,
        )
        # List them
        resp = client.get(f"/api/v1/twins/{twin_id}/forecasts", headers=h)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_records"] == 3  # horizons 1,3,5

    def test_list_records_filter_by_product(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_sim(client, h, product="Widget-A")
        self._create_sim_for_twin(client, h, twin_id, "Widget-B")
        client.get(
            f"/api/v1/twins/{twin_id}/forecast",
            params={"product": "Widget-A"},
            headers=h,
        )
        client.get(
            f"/api/v1/twins/{twin_id}/forecast",
            params={"product": "Widget-B"},
            headers=h,
        )
        resp = client.get(
            f"/api/v1/twins/{twin_id}/forecasts",
            params={"product": "Widget-A"},
            headers=h,
        )
        assert resp.status_code == 200
        for r in resp.json()["records"]:
            assert r["product_name"] == "Widget-A"

    def _create_sim_for_twin(self, client, h, twin_id, product):
        client.post(
            "/api/v1/simulate",
            json={
                "product": product,
                "stock": 3000,
                "warehouse": "W2",
                "demand": 6000,
                "supplier_delay": 2,
                "twin_id": twin_id,
            },
            headers=h,
        )

    def test_forecast_summary(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_sim(client, h)
        # Generate forecast first
        client.get(
            f"/api/v1/twins/{twin_id}/forecast",
            params={"product": "Widget-X"},
            headers=h,
        )
        resp = client.get(f"/api/v1/twins/{twin_id}/forecast/summary", headers=h)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["products"]) == 1
        assert body["products"][0]["latest_forecast"] is not None

    def test_forecast_summary_read_only(self, auth_client):
        """Summary should NOT generate new forecasts."""
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        twin_id = self._create_twin_with_sim(client, h)
        # Call summary without generating forecasts first
        resp = client.get(f"/api/v1/twins/{twin_id}/forecast/summary", headers=h)
        assert resp.status_code == 200
        body = resp.json()
        # No latest_forecast because none were generated
        assert body["products"][0]["latest_forecast"] is None

    def test_forecast_summary_invalid_twin(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        resp = client.get("/api/v1/twins/9999/forecast/summary", headers=h)
        assert resp.status_code == 404


# ===========================================================================
# 4. Backward Compatibility
# ===========================================================================


class TestBackwardCompatibility:
    """Verify E2 doesn't break existing endpoints."""

    def test_simulate_without_twin(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        resp = client.post(
            "/api/v1/simulate",
            json={
                "product": "Widget-Legacy",
                "stock": 3000,
                "warehouse": "W2",
                "demand": 6000,
                "supplier_delay": 2,
            },
            headers=h,
        )
        assert resp.status_code == 200

    def test_health_endpoint(self, auth_client):
        client, data = auth_client
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_simulations_list(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        resp = client.get("/api/v1/simulations", headers=h)
        assert resp.status_code == 200

    def test_twin_crud_still_works(self, auth_client):
        client, data = auth_client
        h = _auth_headers(data["access_token"])
        resp = client.post("/api/v1/twins", json={"name": "Compat Test"}, headers=h)
        assert resp.status_code == 200
        twin_id = resp.json()["id"]
        resp = client.get(f"/api/v1/twins/{twin_id}", headers=h)
        assert resp.status_code == 200
        resp = client.delete(f"/api/v1/twins/{twin_id}", headers=h)
        assert resp.status_code == 200
