"""
Metering API router (Phase E9).

Endpoints:
  GET /usage          — Usage summary (admin-only, org-scoped)
  GET /usage/breakdown — Detailed usage events
"""

import logging
from datetime import datetime

from auth.dependencies import AuthContext, get_current_user, require_role
from auth.models import ROLE_ADMIN
from database import get_db
from fastapi import APIRouter, Depends, Query
from metering.service import MeteringService
from sqlalchemy.orm import Session

logger = logging.getLogger("synchain.metering")

router = APIRouter(prefix="/usage", tags=["Usage & Metering"])


@router.get(
    "",
    dependencies=[Depends(require_role(ROLE_ADMIN))],
)
async def get_usage_summary(
    start: datetime | None = None,
    end: datetime | None = None,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get usage summary for the current organization.

    Returns total events and per-type counts. Requires admin role.
    """
    svc = MeteringService(db)
    return svc.get_usage(org_id=auth.org.id, start=start, end=end)


@router.get(
    "/breakdown",
    dependencies=[Depends(require_role(ROLE_ADMIN))],
)
async def get_usage_breakdown(
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=100, le=500),
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get detailed usage events for the current organization.

    Returns individual events ordered by timestamp descending.
    Requires admin role.
    """
    svc = MeteringService(db)
    return svc.get_breakdown(
        org_id=auth.org.id,
        start=start,
        end=end,
        limit=limit,
    )
