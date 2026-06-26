"""
FastAPI dependencies for authentication and authorization (Phase E8).

Provides:
  - get_current_user:  Decodes JWT or API key, loads user from DB
  - get_current_org:   Resolves the active organization from the token
  - AuthContext:       Dataclass combining user, org, role, and membership
  - require_role:      Dependency factory that enforces minimum role level

Design Decision: Role is loaded from the database on every request,
NOT from the JWT token. This prevents stale authorization when roles
change between token refreshes.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from auth.models import (
    ROLE_HIERARCHY,
    VALID_ROLES,
    APIKey,
    Membership,
    Organization,
    User,
)
from auth.security import decode_token
from database import get_db
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger("synchain.auth")

# HTTPBearer extracts the token from Authorization: Bearer <token>
_bearer_scheme = HTTPBearer(auto_error=False)


# Valid API key scopes
VALID_SCOPES = {"read", "write", "admin"}
ALL_SCOPES = list(VALID_SCOPES)  # JWT users get all scopes


@dataclass
class AuthContext:
    """
    Combined authentication and authorization context.

    Injected into endpoint handlers as a single dependency.
    Contains the authenticated user, active organization,
    the user's role in that org, membership record, and scopes.

    Scopes:
      - JWT-authenticated users: all scopes (read, write, admin)
      - API key users: only the scopes stored in the api_keys.scopes column
    """

    user: User
    org: Organization
    role: str
    membership: Membership
    scopes: list[str] | None = None  # None = all scopes (JWT)


def _get_org_header(request: Request) -> int | None:
    """Extract X-Org-Id header if present."""
    org_id_str = request.headers.get("X-Org-Id")
    if org_id_str:
        try:
            return int(org_id_str)
        except ValueError:
            return None
    return None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthContext:
    """
    Authenticate a request via JWT token or API key.

    Authentication flow:
      1. Check Authorization: Bearer <jwt_token>
      2. If no Bearer token, check Authorization: Bearer sc_live_<api_key>
      3. Decode token / verify API key
      4. Load user from DB
      5. Resolve org_id (from token, X-Org-Id header, or user's primary org)
      6. Load role from memberships table (NOT from token)

    Returns an AuthContext dataclass.
    Raises 401 if authentication fails, 403 if user is inactive.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # SECURITY: DEBUG bypass removed in Phase E9
    # All requests must provide valid JWT token or API key
    # Tests use auth_client fixture from conftest.py to get real tokens
    if credentials is None:
        raise credentials_exception

    token = credentials.credentials
    user_id: int | None = None
    token_org_id: int | None = None

    # --- Try JWT first ---
    if not token.startswith("sc_live_"):
        payload = decode_token(token)
        if payload is None:
            raise credentials_exception

        try:
            user_id = int(payload["sub"])
            token_org_id = payload.get("org")
        except (KeyError, ValueError):
            raise credentials_exception

    # --- Try API key ---
    else:
        api_key_hash = __import__(
            "auth.security", fromlist=["hash_api_key"]
        ).hash_api_key(token)
        stmt = select(APIKey).where(
            APIKey.key_hash == api_key_hash,
            APIKey.is_active == True,  # noqa: E712
        )
        api_key_record = db.execute(stmt).scalar_one_or_none()

        if api_key_record is None:
            raise credentials_exception

        # Check expiration
        if api_key_record.expires_at and api_key_record.expires_at < datetime.now(
            timezone.utc
        ):
            raise credentials_exception

        user_id = api_key_record.user_id
        token_org_id = api_key_record.org_id

        # Update last_used_at
        api_key_record.last_used_at = datetime.now(timezone.utc)
        db.commit()

    # --- Load user ---
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    # --- Resolve org_id ---
    # Priority: X-Org-Id header > token org_id > first membership
    header_org_id = _get_org_header(request)
    org_id = header_org_id or token_org_id

    if org_id is None:
        # Fall back to user's first membership
        first_membership = db.execute(
            select(Membership).where(Membership.user_id == user_id).limit(1)
        ).scalar_one_or_none()
        if first_membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no organization membership",
            )
        org_id = first_membership.org_id

    # --- Load membership (role from DB, not token) ---
    membership = db.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.org_id == org_id,
        )
    ).scalar_one_or_none()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this organization",
        )

    # --- Load org ---
    org = db.execute(
        select(Organization).where(Organization.id == org_id)
    ).scalar_one_or_none()

    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # --- Determine scopes ---
    # JWT users get all scopes; API key users get stored scopes
    scopes = ALL_SCOPES  # default: full access for JWT
    if token.startswith("sc_live_"):
        # Re-fetch the API key record scopes
        api_key_hash_val = __import__(
            "auth.security", fromlist=["hash_api_key"]
        ).hash_api_key(token)
        ak = db.execute(
            select(APIKey).where(APIKey.key_hash == api_key_hash_val)
        ).scalar_one_or_none()
        if ak and ak.scopes:
            try:
                scopes = json.loads(ak.scopes)
            except (json.JSONDecodeError, TypeError):
                scopes = ALL_SCOPES

    # Set user context for structured logging
    try:
        from logging_config import org_id_var, user_id_var

        user_id_var.set(user.id)
        org_id_var.set(org.id)
    except ImportError:
        pass

    # Expose user_id on request.state so rate limiter can key by user
    request.state.user_id = user.id

    return AuthContext(
        user=user,
        org=org,
        role=membership.role,
        membership=membership,
        scopes=scopes,
    )


def require_scope(scope: str):
    """
    Dependency factory that enforces API key scopes.

    JWT-authenticated users always pass (they have all scopes).
    API key users must have the required scope in their scopes list.

    Usage:
        @router.post("/endpoint", dependencies=[Depends(require_scope("write"))])
    """
    if scope not in VALID_SCOPES:
        raise ValueError(f"Invalid scope: {scope}. Must be one of {VALID_SCOPES}")

    async def _check_scope(auth: AuthContext = Depends(get_current_user)):
        if auth.scopes is not None and scope not in auth.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key missing required scope: {scope}",
            )

    return _check_scope


def require_role(min_role: str):
    """
    Dependency factory that enforces a minimum role level.

    Usage:
        @router.post("/twins", dependencies=[Depends(require_role("member"))])
        async def create_twin(auth: AuthContext = Depends(get_current_user)):
            ...

    Or inline:
        async def create_twin(
            auth: AuthContext = Depends(get_current_user),
            _: None = Depends(require_role("member")),
        ):
            ...
    """
    if min_role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {min_role}. Must be one of {VALID_ROLES}")

    min_level = ROLE_HIERARCHY[min_role]

    async def _check_role(auth: AuthContext = Depends(get_current_user)):
        user_level = ROLE_HIERARCHY.get(auth.role, -1)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {min_role} role or higher (current: {auth.role})",
            )

    return _check_role
