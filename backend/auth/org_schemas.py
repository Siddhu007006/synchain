"""
Pydantic schemas for organization endpoints (Phase E8).
"""

from datetime import datetime

from pydantic import BaseModel, Field


class CreateOrgRequest(BaseModel):
    """Input for POST /orgs."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Organization name"
    )


class UpdateOrgRequest(BaseModel):
    """Input for PATCH /orgs/{slug}."""

    name: str | None = Field(None, min_length=1, max_length=100)


class OrgResponse(BaseModel):
    """Organization detail response."""

    id: int
    name: str
    slug: str
    created_at: datetime
    member_count: int = 0

    model_config = {"from_attributes": True}


class OrgListItem(BaseModel):
    """Organization in list response."""

    id: int
    name: str
    slug: str
    role: str
    member_count: int = 0


class MemberResponse(BaseModel):
    """Organization member detail."""

    membership_id: int
    user_id: int
    email: str
    display_name: str
    role: str
    joined_at: datetime


class InviteMemberRequest(BaseModel):
    """Input for POST /orgs/{slug}/members."""

    email: str = Field(..., description="Email of user to invite")
    role: str = Field("member", description="Role to assign: admin | member | viewer")


class UpdateMemberRoleRequest(BaseModel):
    """Input for PATCH /orgs/{slug}/members/{user_id}."""

    role: str = Field(..., description="New role: admin | member | viewer")
