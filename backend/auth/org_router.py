"""
Organization management API router (Phase E8).

Endpoints:
  POST   /orgs                        — Create new organization
  GET    /orgs                        — List user's organizations
  GET    /orgs/{slug}                 — Get org details
  PATCH  /orgs/{slug}                 — Update org
  GET    /orgs/{slug}/members         — List members
  POST   /orgs/{slug}/members         — Invite member
  PATCH  /orgs/{slug}/members/{uid}   — Change member role
  DELETE /orgs/{slug}/members/{uid}   — Remove member
"""

import logging
import re

from auth.dependencies import AuthContext, get_current_user
from auth.models import (
    ROLE_ADMIN,
    ROLE_HIERARCHY,
    ROLE_MEMBER,
    ROLE_OWNER,
    ROLE_VIEWER,
    Membership,
    Organization,
    User,
)
from auth.org_schemas import (
    CreateOrgRequest,
    InviteMemberRequest,
    MemberResponse,
    OrgListItem,
    OrgResponse,
    UpdateMemberRoleRequest,
    UpdateOrgRequest,
)
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger("synchain.orgs")

router = APIRouter(prefix="/orgs", tags=["Organizations"])


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-") or "org"


def _ensure_unique_slug(db: Session, base_slug: str) -> str:
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


def _get_member_count(db: Session, org_id: int) -> int:
    result = db.execute(
        select(func.count()).select_from(Membership).where(Membership.org_id == org_id)
    )
    return result.scalar() or 0


def _load_org_by_slug(db: Session, slug: str) -> Organization:
    org = db.execute(
        select(Organization).where(Organization.slug == slug)
    ).scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    return org


def _verify_membership(
    db: Session, user_id: int, org_id: int, min_role: str
) -> Membership:
    membership = db.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.org_id == org_id,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )
    if ROLE_HIERARCHY.get(membership.role, -1) < ROLE_HIERARCHY[min_role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires {min_role} role or higher (current: {membership.role})",
        )
    return membership


# ---------------------------------------------------------------------------
# POST /orgs
# ---------------------------------------------------------------------------


@router.post("/", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_org(
    req: CreateOrgRequest,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new organization. The creating user becomes the owner."""
    # Check duplicate name
    existing = db.execute(
        select(Organization).where(Organization.name == req.name)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization name already taken",
        )

    slug = _ensure_unique_slug(db, _slugify(req.name))
    org = Organization(name=req.name, slug=slug, created_by=auth.user.id)
    db.add(org)
    db.flush()

    membership = Membership(user_id=auth.user.id, org_id=org.id, role=ROLE_OWNER)
    db.add(membership)
    db.commit()

    logger.info("Organization created: %s by %s", org.slug, auth.user.email)

    return OrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        created_at=org.created_at,
        member_count=1,
    )


# ---------------------------------------------------------------------------
# GET /orgs
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[OrgListItem])
async def list_orgs(
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all organizations the current user belongs to."""
    memberships = (
        db.execute(select(Membership).where(Membership.user_id == auth.user.id))
        .scalars()
        .all()
    )

    result = []
    for m in memberships:
        org = db.execute(
            select(Organization).where(Organization.id == m.org_id)
        ).scalar_one_or_none()
        if org:
            result.append(
                OrgListItem(
                    id=org.id,
                    name=org.name,
                    slug=org.slug,
                    role=m.role,
                    member_count=_get_member_count(db, org.id),
                )
            )
    return result


# ---------------------------------------------------------------------------
# GET /orgs/{slug}
# ---------------------------------------------------------------------------


@router.get("/{slug}", response_model=OrgResponse)
async def get_org(
    slug: str,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get organization details. Requires viewer role or higher."""
    org = _load_org_by_slug(db, slug)
    _verify_membership(db, auth.user.id, org.id, ROLE_VIEWER)

    return OrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        created_at=org.created_at,
        member_count=_get_member_count(db, org.id),
    )


# ---------------------------------------------------------------------------
# PATCH /orgs/{slug}
# ---------------------------------------------------------------------------


@router.patch("/{slug}", response_model=OrgResponse)
async def update_org(
    slug: str,
    req: UpdateOrgRequest,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update organization. Requires admin role or higher."""
    org = _load_org_by_slug(db, slug)
    _verify_membership(db, auth.user.id, org.id, ROLE_ADMIN)

    if req.name is not None:
        # Check name uniqueness
        existing = db.execute(
            select(Organization).where(
                Organization.name == req.name,
                Organization.id != org.id,
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Organization name already taken",
            )
        org.name = req.name
        org.slug = _ensure_unique_slug(db, _slugify(req.name))

    db.commit()

    return OrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        created_at=org.created_at,
        member_count=_get_member_count(db, org.id),
    )


# ---------------------------------------------------------------------------
# GET /orgs/{slug}/members
# ---------------------------------------------------------------------------


@router.get("/{slug}/members", response_model=list[MemberResponse])
async def list_members(
    slug: str,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List organization members. Requires member role or higher."""
    org = _load_org_by_slug(db, slug)
    _verify_membership(db, auth.user.id, org.id, ROLE_MEMBER)

    memberships = (
        db.execute(select(Membership).where(Membership.org_id == org.id))
        .scalars()
        .all()
    )

    result = []
    for m in memberships:
        user = db.execute(select(User).where(User.id == m.user_id)).scalar_one_or_none()
        if user:
            result.append(
                MemberResponse(
                    membership_id=m.id,
                    user_id=user.id,
                    email=user.email,
                    display_name=user.display_name,
                    role=m.role,
                    joined_at=m.joined_at,
                )
            )
    return result


# ---------------------------------------------------------------------------
# POST /orgs/{slug}/members
# ---------------------------------------------------------------------------


@router.post(
    "/{slug}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    slug: str,
    req: InviteMemberRequest,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add a user to the organization. Requires admin role or higher.

    The invited user must already have a registered account.
    Cannot assign the owner role — ownership requires explicit transfer.
    """
    org = _load_org_by_slug(db, slug)
    _verify_membership(db, auth.user.id, org.id, ROLE_ADMIN)

    # Validate role
    if req.role not in {ROLE_ADMIN, ROLE_MEMBER, ROLE_VIEWER}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {req.role}. Must be admin, member, or viewer.",
        )

    # Find user by email
    user = db.execute(select(User).where(User.email == req.email)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Check existing membership
    existing = db.execute(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.org_id == org.id,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User is already a member"
        )

    membership = Membership(user_id=user.id, org_id=org.id, role=req.role)
    db.add(membership)
    db.commit()
    db.refresh(membership)

    logger.info("Member added: %s to %s (role: %s)", user.email, org.slug, req.role)

    return MemberResponse(
        membership_id=membership.id,
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role,
        joined_at=membership.joined_at,
    )


# ---------------------------------------------------------------------------
# PATCH /orgs/{slug}/members/{user_id}
# ---------------------------------------------------------------------------


@router.patch("/{slug}/members/{user_id}", response_model=MemberResponse)
async def update_member_role(
    slug: str,
    user_id: int,
    req: UpdateMemberRoleRequest,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change a member's role. Requires admin role or higher.

    Cannot change the owner's role — ownership transfer is a separate action.
    Cannot assign owner role via this endpoint.
    """
    org = _load_org_by_slug(db, slug)
    _verify_membership(db, auth.user.id, org.id, ROLE_ADMIN)

    if req.role not in {ROLE_ADMIN, ROLE_MEMBER, ROLE_VIEWER}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {req.role}. Must be admin, member, or viewer.",
        )

    target_membership = db.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.org_id == org.id,
        )
    ).scalar_one_or_none()

    if target_membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
        )

    if target_membership.role == ROLE_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot change the owner's role. Use ownership transfer instead.",
        )

    target_membership.role = req.role
    db.commit()

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()

    logger.info("Role updated: user %d -> %s in %s", user_id, req.role, org.slug)

    return MemberResponse(
        membership_id=target_membership.id,
        user_id=user_id,
        email=user.email if user else "",
        display_name=user.display_name if user else "",
        role=target_membership.role,
        joined_at=target_membership.joined_at,
    )


# ---------------------------------------------------------------------------
# DELETE /orgs/{slug}/members/{user_id}
# ---------------------------------------------------------------------------


@router.delete("/{slug}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    slug: str,
    user_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Remove a member from the organization. Requires admin role or higher.

    The owner cannot be removed. To leave as owner, transfer ownership first.
    """
    org = _load_org_by_slug(db, slug)
    _verify_membership(db, auth.user.id, org.id, ROLE_ADMIN)

    target_membership = db.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.org_id == org.id,
        )
    ).scalar_one_or_none()

    if target_membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
        )

    if target_membership.role == ROLE_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot remove the owner. Transfer ownership first.",
        )

    db.delete(target_membership)
    db.commit()

    logger.info("Member removed: user %d from %s", user_id, org.slug)
