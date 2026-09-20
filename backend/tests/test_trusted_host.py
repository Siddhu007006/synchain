"""
Phase 1 MR #1: TrustedHostMiddleware.

Verifies that when an explicit allowed_hosts allowlist is configured,
requests with a non-matching Host header are rejected, while requests
with an allowed Host (or the wildcard default) are accepted.

These tests build isolated apps so they do not depend on or mutate the
shared application's middleware stack.
"""

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.testclient import TestClient


def _build_app(allowed_hosts):
    """Build a minimal app guarded by TrustedHostMiddleware."""
    app = FastAPI()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    @app.get("/live")
    def live():
        return {"status": "alive"}

    return app


class TestTrustedHost:
    """TrustedHostMiddleware host enforcement."""

    def test_allowed_host_accepted(self):
        """A request whose Host is in the allowlist is accepted."""
        app = _build_app(["api.synchain.local"])
        client = TestClient(app)
        resp = client.get("/live", headers={"Host": "api.synchain.local"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "alive"}

    def test_untrusted_host_rejected(self):
        """A request whose Host is not in the allowlist is rejected with 400."""
        app = _build_app(["api.synchain.local"])
        client = TestClient(app)
        resp = client.get("/live", headers={"Host": "evil.example.com"})
        assert resp.status_code == 400
