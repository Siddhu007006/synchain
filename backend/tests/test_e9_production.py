"""
E9 test suite: Middleware, Rate Limiting, Audit, Metering, Health, Scopes.

Tests the production-readiness infrastructure added in Phase E9.
"""

import json

import pytest
from config import settings
from fastapi.testclient import TestClient
from main import app


@pytest.fixture(autouse=True)
def _disable_debug(monkeypatch):
    """Ensure debug mode is off for E9 tests."""
    monkeypatch.setattr(settings, "debug", False)


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def auth_client(client):
    """Register a user and return (client, headers, user_data)."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "e9test@synchain.local",
            "password": "testpass123",
            "display_name": "E9 Tester",
        },
    )
    assert reg.status_code == 201
    data = reg.json()
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    return client, headers, data


# ===================================================================
# E9.2 — Middleware Tests
# ===================================================================


class TestMiddleware:
    """Verify request ID, timing, and security header middleware."""

    def test_request_id_generated(self, client):
        """Every response should have X-Request-Id header."""
        resp = client.get("/live")
        assert "X-Request-Id" in resp.headers
        # Should be a UUID-like string
        req_id = resp.headers["X-Request-Id"]
        assert len(req_id) == 36  # UUID format

    def test_request_id_passthrough(self, client):
        """Client-provided X-Request-Id should be echoed back."""
        custom_id = "my-custom-request-id-12345"
        resp = client.get("/live", headers={"X-Request-Id": custom_id})
        assert resp.headers["X-Request-Id"] == custom_id

    def test_response_time_header(self, client):
        """X-Response-Time header should be present."""
        resp = client.get("/live")
        assert "X-Response-Time" in resp.headers
        assert resp.headers["X-Response-Time"].endswith("ms")

    def test_security_headers(self, client):
        """Security headers should be present on every response."""
        resp = client.get("/live")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["X-XSS-Protection"] == "0"
        assert "strict-origin" in resp.headers["Referrer-Policy"]


# ===================================================================
# E9.3 — Rate Limiting Tests
# ===================================================================


class TestRateLimiting:
    """Verify sliding window rate limiter."""

    def test_rate_limiter_store_allows(self):
        """Requests within limit should be allowed."""
        from rate_limiter import SlidingWindowStore

        store = SlidingWindowStore()
        allowed, remaining, retry = store.is_allowed("test_key", 5, 60)
        assert allowed is True
        assert remaining == 4

    def test_rate_limiter_store_blocks(self):
        """Requests exceeding limit should be blocked."""
        from rate_limiter import SlidingWindowStore

        store = SlidingWindowStore()
        for _ in range(5):
            store.is_allowed("block_key", 5, 60)
        allowed, remaining, retry = store.is_allowed("block_key", 5, 60)
        assert allowed is False
        assert remaining == 0
        assert retry > 0

    def test_rate_limiter_per_key_isolation(self):
        """Different keys should have independent limits."""
        from rate_limiter import SlidingWindowStore

        store = SlidingWindowStore()
        for _ in range(5):
            store.is_allowed("user_a", 5, 60)
        # user_a exhausted
        allowed_a, _, _ = store.is_allowed("user_a", 5, 60)
        assert allowed_a is False
        # user_b should be fine
        allowed_b, _, _ = store.is_allowed("user_b", 5, 60)
        assert allowed_b is True

    def test_rate_limiter_clear(self):
        """Store clear should reset all data."""
        from rate_limiter import SlidingWindowStore

        store = SlidingWindowStore()
        for _ in range(5):
            store.is_allowed("clear_key", 5, 60)
        store.clear()
        allowed, _, _ = store.is_allowed("clear_key", 5, 60)
        assert allowed is True


# ===================================================================
# E9.5 — Audit Logging Tests
# ===================================================================


class TestAuditLogging:
    """Verify audit service and API endpoint."""

    def test_audit_log_creation(self, auth_client):
        """Simulations should create audit events."""
        client, headers, data = auth_client
        # Run a simulation (triggers audit)
        resp = client.post(
            "/api/v1/simulate",
            json={
                "product": "AuditTest",
                "stock": 100,
                "warehouse": "W1",
                "demand": 50,
                "supplier_delay": 2,
                "market_trend": "Positive",
                "supply_status": "High",
                "season": "Normal",
            },
            headers=headers,
        )
        assert resp.status_code in (200, 201)

        # Check audit events via API (user is owner = admin-level)
        audit_resp = client.get("/api/v1/audit", headers=headers)
        assert audit_resp.status_code == 200
        events = audit_resp.json()["events"]
        assert len(events) > 0
        assert any(e["action"] == "simulation.create" for e in events)

    def test_audit_event_fields(self, auth_client):
        """Audit events should have all required fields."""
        client, headers, data = auth_client
        client.post(
            "/api/v1/simulate",
            json={
                "product": "FieldTest",
                "stock": 100,
                "warehouse": "W1",
                "demand": 50,
                "supplier_delay": 2,
                "market_trend": "Neutral",
                "supply_status": "Medium",
                "season": "Normal",
            },
            headers=headers,
        )

        audit_resp = client.get("/api/v1/audit", headers=headers)
        events = audit_resp.json()["events"]
        event = next(e for e in events if e["action"] == "simulation.create")
        assert event["user_id"] is not None
        assert event["org_id"] is not None
        assert event["resource_type"] == "Simulation"
        assert event["resource_id"] is not None

    def test_audit_requires_admin(self, client):
        """Audit endpoint should require authentication."""
        resp = client.get("/api/v1/audit")
        assert resp.status_code == 401

    def test_audit_filter_by_action(self, auth_client):
        """Audit events should be filterable by action."""
        client, headers, _ = auth_client
        # Create a simulation to generate audit data
        client.post(
            "/api/v1/simulate",
            json={
                "product": "FilterTest",
                "stock": 100,
                "warehouse": "W1",
                "demand": 50,
                "supplier_delay": 2,
                "market_trend": "Positive",
                "supply_status": "High",
                "season": "Normal",
            },
            headers=headers,
        )

        resp = client.get("/api/v1/audit?action=simulation.create", headers=headers)
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert all(e["action"] == "simulation.create" for e in events)


# ===================================================================
# E9.6 — Health Check Tests
# ===================================================================


class TestHealthChecks:
    """Verify enhanced health probes."""

    def test_health_endpoint(self, client):
        """Health should return component status."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "degraded")
        assert "components" in data
        assert "database" in data["components"]
        assert "uptime_seconds" in data

    def test_ready_endpoint(self, client):
        """Readiness probe should return ready status."""
        resp = client.get("/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"

    def test_live_endpoint(self, client):
        """Liveness probe should always return alive."""
        resp = client.get("/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"


# ===================================================================
# E9.10 — Metering Tests
# ===================================================================


class TestMetering:
    """Verify usage metering service and API."""

    def test_metering_records_simulation(self, auth_client):
        """Simulations should generate metering events."""
        client, headers, _ = auth_client
        client.post(
            "/api/v1/simulate",
            json={
                "product": "MeterTest",
                "stock": 100,
                "warehouse": "W1",
                "demand": 50,
                "supplier_delay": 2,
                "market_trend": "Positive",
                "supply_status": "High",
                "season": "Normal",
            },
            headers=headers,
        )

        usage_resp = client.get("/api/v1/usage", headers=headers)
        assert usage_resp.status_code == 200
        data = usage_resp.json()
        assert data["total_events"] > 0
        assert "simulation.run" in data["by_type"]

    def test_metering_breakdown(self, auth_client):
        """Usage breakdown should list individual events."""
        client, headers, _ = auth_client
        client.post(
            "/api/v1/simulate",
            json={
                "product": "BreakdownTest",
                "stock": 100,
                "warehouse": "W1",
                "demand": 50,
                "supplier_delay": 2,
                "market_trend": "Neutral",
                "supply_status": "Medium",
                "season": "Normal",
            },
            headers=headers,
        )

        resp = client.get("/api/v1/usage/breakdown", headers=headers)
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) > 0
        assert events[0]["event_type"] == "simulation.run"

    def test_metering_requires_admin(self, client):
        """Metering endpoints should require authentication."""
        resp = client.get("/api/v1/usage")
        assert resp.status_code == 401


# ===================================================================
# E9.4 — Scope Enforcement Tests
# ===================================================================


class TestScopeEnforcement:
    """Verify API key scope enforcement."""

    def test_jwt_user_has_all_scopes(self, auth_client):
        """JWT-authenticated users should have all scopes."""
        client, headers, _ = auth_client
        # JWT users can access all endpoints
        resp = client.get("/api/v1/simulations", headers=headers)
        assert resp.status_code == 200

    def test_scope_constants_valid(self):
        """Valid scopes should include read, write, admin."""
        from auth.dependencies import VALID_SCOPES

        assert "read" in VALID_SCOPES
        assert "write" in VALID_SCOPES
        assert "admin" in VALID_SCOPES


# ===================================================================
# E9.1 — Structured Logging Tests
# ===================================================================


class TestStructuredLogging:
    """Verify logging configuration."""

    def test_json_formatter(self):
        """JSON formatter should produce valid JSON."""
        import logging

        from logging_config import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "Test message"
        assert parsed["level"] == "INFO"
        assert "timestamp" in parsed
        assert "request_id" in parsed

    def test_context_vars_default(self):
        """Context vars should have safe defaults."""
        from logging_config import org_id_var, request_id_var, user_id_var

        assert request_id_var.get() == "-"
        assert user_id_var.get() is None
        assert org_id_var.get() is None

    def test_setup_logging_text(self):
        """Text logging setup should not crash."""
        from logging_config import setup_logging

        setup_logging(log_level="DEBUG", log_format="text")

    def test_setup_logging_json(self):
        """JSON logging setup should not crash."""
        from logging_config import setup_logging

        setup_logging(log_level="INFO", log_format="json")
