"""
Pydantic schemas for auth endpoints (Phase E8).

Covers:
  - Registration (input + response)
  - Login (input + token response)
  - Token refresh
  - User profile
  - API key management
"""

from datetime import datetime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    """Input for POST /auth/register."""

    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Password (min 8 chars)")
    display_name: str = Field("", description="Display name")
    org_name: str = Field("", description="Organization name (auto-generated if empty)")


class RegisterResponse(BaseModel):
    """Response from POST /auth/register."""

    user_id: int
    email: str
    org_id: int
    org_slug: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """Input for POST /auth/login."""

    email: str = Field(..., description="User email")
    password: str = Field(..., description="Password")
    org_id: int | None = Field(
        None, description="Org to log into (defaults to primary)"
    )


class TokenResponse(BaseModel):
    """JWT token pair response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    org_id: int
    org_slug: str


# ---------------------------------------------------------------------------
# Token Refresh
# ---------------------------------------------------------------------------


class RefreshRequest(BaseModel):
    """Input for POST /auth/refresh."""

    refresh_token: str = Field(..., description="Refresh token")
    org_id: int | None = Field(None, description="Org to refresh into")


# ---------------------------------------------------------------------------
# User Profile
# ---------------------------------------------------------------------------


class UserProfile(BaseModel):
    """Response from GET /auth/me."""

    id: int
    email: str
    display_name: str
    is_active: bool
    created_at: datetime
    organizations: list["UserOrgSummary"]

    model_config = {"from_attributes": True}


class UserOrgSummary(BaseModel):
    """Organization summary within user profile."""

    org_id: int
    org_name: str
    org_slug: str
    role: str


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------


class CreateAPIKeyRequest(BaseModel):
    """Input for POST /auth/api-keys."""

    name: str = Field("Default", description="Key label")
    scopes: list[str] = Field(default_factory=list, description="Permission scopes")


class APIKeyResponse(BaseModel):
    """Response from POST /auth/api-keys — includes the full key (shown once)."""

    id: int
    name: str
    key: str = Field(..., description="Full API key (shown ONCE)")
    key_prefix: str
    scopes: list[str]
    created_at: datetime


class APIKeyListItem(BaseModel):
    """API key in list response (no full key)."""

    id: int
    name: str
    key_prefix: str
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
