"""
Auth API router (Phase E8).

Endpoints:
  POST /auth/register  — Create user + default org
  POST /auth/login     — Returns JWT access + refresh tokens
  POST /auth/refresh   — Returns new access token
  GET  /auth/me        — Current user profile
  POST /auth/api-keys  — Create API key
  GET  /auth/api-keys  — List user's API keys
  DELETE /auth/api-keys/{id} — Revoke API key
"""

import json
import logging
import re

from auth.dependencies import AuthContext, get_current_user, require_role
from auth.models import ROLE_ADMIN, ROLE_OWNER, APIKey, Membership, Organization, User
from auth.schemas import (
    APIKeyListItem,
    APIKeyResponse,
    CreateAPIKeyRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserOrgSummary,
    UserProfile,
)
from auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    hash_password,
    verify_password,
)
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from rate_limiter import rate_limit
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger("synchain.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _slugify(name: str) -> str:
    """Convert an org name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "org"


def _ensure_unique_slug(db: Session, base_slug: str) -> str:
    """Make a slug unique by appending a counter if needed."""
    slug = base_slug
    counter = 1
    while (
        db.execute(
            select(Organization).where(Organization.slug == slug)
        ).scalar_one_or_none()
        is not None
    ):
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("auth"))],
)
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user and create their default organization.

    The user becomes the owner of the new organization.
    Returns JWT tokens for immediate use.
    """
    # Check duplicate email
    existing = db.execute(
        select(User).where(User.email == req.email)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create user
    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        display_name=req.display_name or req.email.split("@")[0],
    )
    db.add(user)
    db.flush()  # Get user.id

    # Create default org
    org_name = req.org_name or f"{user.display_name}'s Organization"
    slug = _ensure_unique_slug(db, _slugify(org_name))

    org = Organization(
        name=org_name,
        slug=slug,
        created_by=user.id,
    )
    db.add(org)
    db.flush()  # Get org.id

    # Create membership (owner)
    membership = Membership(
        user_id=user.id,
        org_id=org.id,
        role=ROLE_OWNER,
    )
    db.add(membership)
    db.commit()

    logger.info("User registered: %s (org: %s)", user.email, org.slug)

    return RegisterResponse(
        user_id=user.id,
        email=user.email,
        org_id=org.id,
        org_slug=org.slug,
        access_token=create_access_token(user.id, org.id),
        refresh_token=create_refresh_token(user.id),
    )


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


@router.post(
    "/login", response_model=TokenResponse, dependencies=[Depends(rate_limit("auth"))]
)
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with email + password.

    Returns JWT access and refresh tokens.
    If org_id is specified, the token is scoped to that org.
    Otherwise, the user's first org is used.
    """
    user = db.execute(select(User).where(User.email == req.email)).scalar_one_or_none()
    if user is None or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    # Resolve org
    if req.org_id:
        membership = db.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.org_id == req.org_id,
            )
        ).scalar_one_or_none()
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a member of this organization",
            )
        org_id = req.org_id
    else:
        membership = db.execute(
            select(Membership).where(Membership.user_id == user.id).limit(1)
        ).scalar_one_or_none()
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no organization membership",
            )
        org_id = membership.org_id

    org = db.execute(
        select(Organization).where(Organization.id == org_id)
    ).scalar_one_or_none()

    logger.info("User logged in: %s (org: %d)", user.email, org_id)

    return TokenResponse(
        access_token=create_access_token(user.id, org_id),
        refresh_token=create_refresh_token(user.id),
        org_id=org_id,
        org_slug=org.slug if org else "unknown",
    )


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


@router.post(
    "/refresh", response_model=TokenResponse, dependencies=[Depends(rate_limit("auth"))]
)
async def refresh_token(req: RefreshRequest, db: Session = Depends(get_db)):
    """
    Exchange a refresh token for a new access token.

    Optionally switch to a different org by providing org_id.
    """
    payload = decode_token(req.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = int(payload["sub"])
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    # Resolve org
    if req.org_id:
        membership = db.execute(
            select(Membership).where(
                Membership.user_id == user_id,
                Membership.org_id == req.org_id,
            )
        ).scalar_one_or_none()
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a member of this organization",
            )
        org_id = req.org_id
    else:
        membership = db.execute(
            select(Membership).where(Membership.user_id == user_id).limit(1)
        ).scalar_one_or_none()
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no organization membership",
            )
        org_id = membership.org_id

    org = db.execute(
        select(Organization).where(Organization.id == org_id)
    ).scalar_one_or_none()

    return TokenResponse(
        access_token=create_access_token(user_id, org_id),
        refresh_token=create_refresh_token(user_id),
        org_id=org_id,
        org_slug=org.slug if org else "unknown",
    )


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserProfile)
async def get_me(
    auth: AuthContext = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Return the current user's profile with all org memberships."""
    memberships = (
        db.execute(select(Membership).where(Membership.user_id == auth.user.id))
        .scalars()
        .all()
    )

    orgs_summary = []
    for m in memberships:
        org = db.execute(
            select(Organization).where(Organization.id == m.org_id)
        ).scalar_one_or_none()
        if org:
            orgs_summary.append(
                UserOrgSummary(
                    org_id=org.id,
                    org_name=org.name,
                    org_slug=org.slug,
                    role=m.role,
                )
            )

    return UserProfile(
        id=auth.user.id,
        email=auth.user.email,
        display_name=auth.user.display_name,
        is_active=auth.user.is_active,
        created_at=auth.user.created_at,
        organizations=orgs_summary,
    )


# ---------------------------------------------------------------------------
# POST /auth/api-keys
# ---------------------------------------------------------------------------


@router.post(
    "/api-keys",
    response_model=APIKeyResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(ROLE_ADMIN))],
)
async def create_api_key_endpoint(
    req: CreateAPIKeyRequest,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new API key for programmatic access.

    Requires admin role or higher.
    The full key is returned ONCE in this response — it cannot be retrieved later.
    """
    full_key, key_hash, key_prefix = generate_api_key()

    api_key = APIKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=req.name,
        user_id=auth.user.id,
        org_id=auth.org.id,
        scopes=json.dumps(req.scopes),
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    logger.info(
        "API key created: %s (user: %s, org: %s)",
        key_prefix,
        auth.user.email,
        auth.org.slug,
    )

    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key=full_key,
        key_prefix=key_prefix,
        scopes=req.scopes,
        created_at=api_key.created_at,
    )


# ---------------------------------------------------------------------------
# GET /auth/api-keys
# ---------------------------------------------------------------------------


@router.get("/api-keys", response_model=list[APIKeyListItem])
async def list_api_keys(
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all API keys for the current user in the current org."""
    keys = (
        db.execute(
            select(APIKey).where(
                APIKey.user_id == auth.user.id,
                APIKey.org_id == auth.org.id,
            )
        )
        .scalars()
        .all()
    )

    return [
        APIKeyListItem(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            is_active=k.is_active,
            last_used_at=k.last_used_at,
            created_at=k.created_at,
        )
        for k in keys
    ]


# ---------------------------------------------------------------------------
# DELETE /auth/api-keys/{key_id}
# ---------------------------------------------------------------------------


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke an API key (soft delete — marks as inactive)."""
    api_key = db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.user_id == auth.user.id,
            APIKey.org_id == auth.org.id,
        )
    ).scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    api_key.is_active = False
    db.commit()

    logger.info("API key revoked: %s (user: %s)", api_key.key_prefix, auth.user.email)
