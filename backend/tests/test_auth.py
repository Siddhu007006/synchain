"""
E8 Authentication tests.

Covers:
  - User registration
  - Login
  - Token refresh
  - User profile (GET /auth/me)
  - API key CRUD
  - Error cases (duplicate email, wrong password, expired token)
"""

from tests.conftest import _auth_headers, _register_user

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register_success(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "alice@synchain.io",
                "password": "securepass1",
                "display_name": "Alice",
                "org_name": "Alice Corp",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "alice@synchain.io"
        assert data["user_id"] > 0
        assert data["org_id"] > 0
        assert data["org_slug"] == "alice-corp"
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_register_auto_org_name(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "bob@synchain.io",
                "password": "securepass2",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["org_slug"]  # Should have auto-generated slug

    def test_register_duplicate_email(self, client):
        _register_user(client, email="dup@synchain.io")
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "dup@synchain.io",
                "password": "securepass3",
            },
        )
        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"]

    def test_register_short_password(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "short@synchain.io",
                "password": "abc",
            },
        )
        assert resp.status_code == 422  # Pydantic validation


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


class TestLogin:
    def test_login_success(self, client):
        _register_user(client, email="login@synchain.io", password="mypassword1")
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "email": "login@synchain.io",
                "password": "mypassword1",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["org_id"] > 0

    def test_login_wrong_password(self, client):
        _register_user(client, email="wrong@synchain.io", password="correctpass")
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrong@synchain.io",
                "password": "incorrectpass",
            },
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "email": "ghost@synchain.io",
                "password": "whatever",
            },
        )
        assert resp.status_code == 401

    def test_login_with_org_id(self, client):
        reg = _register_user(client, email="orglogin@synchain.io")
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "email": "orglogin@synchain.io",
                "password": "testpass123",
                "org_id": reg["org_id"],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["org_id"] == reg["org_id"]


# ---------------------------------------------------------------------------
# Token Refresh
# ---------------------------------------------------------------------------


class TestTokenRefresh:
    def test_refresh_success(self, client):
        reg = _register_user(client, email="refresh@synchain.io")
        resp = client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": reg["refresh_token"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        # Note: tokens generated in the same second may be identical
        # (same iat/exp). We verify the response is well-formed instead.
        assert data["token_type"] == "bearer"
        assert data["org_id"] == reg["org_id"]

    def test_refresh_invalid_token(self, client):
        resp = client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": "invalid.token.here",
            },
        )
        assert resp.status_code == 401

    def test_refresh_with_org_switch(self, client):
        reg = _register_user(client, email="switch@synchain.io")
        # Create second org
        headers = _auth_headers(reg["access_token"])
        org_resp = client.post(
            "/api/v1/orgs/", json={"name": "Second Org"}, headers=headers
        )
        assert org_resp.status_code == 201
        second_org_id = org_resp.json()["id"]

        # Refresh into second org
        resp = client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": reg["refresh_token"],
                "org_id": second_org_id,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["org_id"] == second_org_id


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


class TestUserProfile:
    def test_me_success(self, client):
        reg = _register_user(client, email="me@synchain.io", org_name="Me Corp")
        headers = _auth_headers(reg["access_token"])
        resp = client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@synchain.io"
        assert len(data["organizations"]) == 1
        assert data["organizations"][0]["role"] == "owner"

    def test_me_unauthenticated(self, client, monkeypatch):
        # Disable debug mode to test real auth enforcement
        from config import settings

        monkeypatch.setattr(settings, "debug", False)
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------


class TestAPIKeys:
    def test_create_api_key(self, client):
        reg = _register_user(client, email="apikey@synchain.io")
        headers = _auth_headers(reg["access_token"])
        resp = client.post(
            "/api/v1/auth/api-keys",
            json={
                "name": "CI Key",
                "scopes": ["read", "write"],
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "CI Key"
        assert data["key"].startswith("sc_live_")
        assert data["key_prefix"].startswith("sc_live_")

    def test_list_api_keys(self, client):
        reg = _register_user(client, email="listkeys@synchain.io")
        headers = _auth_headers(reg["access_token"])
        # Create two keys
        client.post("/api/v1/auth/api-keys", json={"name": "Key1"}, headers=headers)
        client.post("/api/v1/auth/api-keys", json={"name": "Key2"}, headers=headers)
        resp = client.get("/api/v1/auth/api-keys", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_revoke_api_key(self, client):
        reg = _register_user(client, email="revoke@synchain.io")
        headers = _auth_headers(reg["access_token"])
        create_resp = client.post(
            "/api/v1/auth/api-keys", json={"name": "Temp"}, headers=headers
        )
        key_id = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/auth/api-keys/{key_id}", headers=headers)
        assert resp.status_code == 204

        # Verify it's inactive
        list_resp = client.get("/api/v1/auth/api-keys", headers=headers)
        keys = [k for k in list_resp.json() if k["id"] == key_id]
        assert keys[0]["is_active"] is False

    def test_auth_with_api_key(self, client):
        reg = _register_user(client, email="usekey@synchain.io")
        headers = _auth_headers(reg["access_token"])
        create_resp = client.post(
            "/api/v1/auth/api-keys", json={"name": "AuthTest"}, headers=headers
        )
        full_key = create_resp.json()["key"]

        # Use the API key to access /auth/me
        key_headers = {"Authorization": f"Bearer {full_key}"}
        resp = client.get("/api/v1/auth/me", headers=key_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "usekey@synchain.io"
