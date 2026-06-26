"""
Shared test fixtures for all backend tests.

Uses a single test database for API tests to avoid dependency override
conflicts when multiple test files override get_db.

Phase E8: Added auth_client, register_user, and auth_headers fixtures
for authenticated endpoint testing.

Phase E9 Security Hardening: Removed DEBUG bypass, all tests now use real JWT tokens.
"""

import pytest
from config import settings
from database import Base, get_db
from main import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Disable rate limiting for testing (keeps tests fast)
settings.rate_limit_enabled = False

# DO NOT set settings.debug = True
# Tests must use real authentication like production
# Use auth_client fixture for authenticated requests

# Single shared test database for all API tests
TEST_DB_URL = "sqlite:///./test_shared.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


# Apply override once, globally
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test, drop after."""
    # Drop all tables first to ensure clean state
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    """Provide a clean DB session for unit tests."""
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """Provide a sync test client."""
    from starlette.testclient import TestClient

    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Phase E8: Auth test helpers
# ---------------------------------------------------------------------------


def _register_user(
    client, email="test@synchain.io", password="testpass123", org_name="Test Org"
):
    """Helper: register a user and return the full response dict."""
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": email.split("@")[0],
            "org_name": org_name,
        },
    )
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    return resp.json()


def _auth_headers(token):
    """Helper: create Authorization header dict from a token."""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_client(client):
    """
    Provide an authenticated test client.

    Returns a tuple of (client, auth_data) where auth_data contains
    user_id, org_id, org_slug, access_token, refresh_token.
    """
    data = _register_user(client)
    return client, data


@pytest.fixture
def auth_headers_fixture(auth_client):
    """Provide just the auth headers dict for convenience."""
    client, data = auth_client
    return _auth_headers(data["access_token"])
