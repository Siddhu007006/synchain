"""
SQLAlchemy 2.0 models for the multi-tenant auth layer (Phase E8).

Tables:
  - users:          Registered user accounts
  - organizations:  Tenant containers
  - memberships:    User-to-org association with role
  - api_keys:       Programmatic access credentials

Design Notes:
  - Role is stored in `memberships`, NOT in JWT tokens.
    This avoids stale authorization when roles change between token refreshes.
  - API keys are hashed with bcrypt and never stored in plaintext.
    Only the key_prefix (first 8 chars) is stored for identification.
  - Organization slugs are URL-safe, lowercase, unique identifiers.
"""

from datetime import datetime

from database import Base
from sqlalchemy import ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship


class User(Base):
    """Registered user account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[str]
    display_name: Mapped[str] = mapped_column(default="")
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superadmin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list["APIKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Organization(Base):
    """Tenant container — all data is scoped to an organization."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(unique=True)
    slug: Mapped[str] = mapped_column(unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="org", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list["APIKey"]] = relationship(
        back_populates="org", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Role constants — used by Membership.role and permission guards
# ---------------------------------------------------------------------------
# Hierarchy: owner > admin > member > viewer
ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
ROLE_VIEWER = "viewer"

VALID_ROLES = {ROLE_OWNER, ROLE_ADMIN, ROLE_MEMBER, ROLE_VIEWER}

# Numeric hierarchy for comparison (higher = more privileged)
ROLE_HIERARCHY = {
    ROLE_VIEWER: 0,
    ROLE_MEMBER: 1,
    ROLE_ADMIN: 2,
    ROLE_OWNER: 3,
}


class Membership(Base):
    """User-to-organization association with role-based access."""

    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    role: Mapped[str] = mapped_column(default=ROLE_MEMBER)
    joined_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="memberships")
    org: Mapped["Organization"] = relationship(back_populates="memberships")

    __table_args__ = (UniqueConstraint("user_id", "org_id", name="uq_user_org"),)


class APIKey(Base):
    """
    Programmatic access credential.

    The full key is returned ONCE at creation, then only the key_hash
    and key_prefix are stored. The prefix (e.g., "sc_live_") allows
    users to identify keys without exposing the secret.
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    key_hash: Mapped[str]
    key_prefix: Mapped[str] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(default="Default")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    scopes: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    is_active: Mapped[bool] = mapped_column(default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(default=None)

    user: Mapped["User"] = relationship(back_populates="api_keys")
    org: Mapped["Organization"] = relationship(back_populates="api_keys")
