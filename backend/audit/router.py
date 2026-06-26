"""
Audit log API router (Phase E9).

Endpoints:
  GET /audit — List audit events (admin-only, org-scoped)

Read-only — audit records are created by the service layer,
not directly via API.
"""

import json
import logging

from audit.service import AuditService
from auth.dependencies import AuthContext, get_current_user, require_role
from auth.models import ROLE_ADMIN
from database import get_db
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

logger = logging.getLogger("synchain.audit")

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get(
    "",
    dependencies=[Depends(require_role(ROLE_ADMIN))],
)
async def list_audit_events(
    action: str | None = None,
    resource_type: str | None = None,
    user_id: int | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List audit events for the current organization.

    Requires admin role or higher. Filterable by action,
    resource_type, and user_id. Ordered by timestamp descending.
    """
    svc = AuditService(db)
    events = svc.list_events(
        org_id=auth.org.id,
        action=action,
        resource_type=resource_type,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
    total = svc.count_events(auth.org.id)

    return {
        "total": total,
        "events": [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "user_id": e.user_id,
                "org_id": e.org_id,
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "details": json.loads(e.details) if e.details else None,
                "ip_address": e.ip_address,
                "request_id": e.request_id,
            }
            for e in events
        ],
    }
