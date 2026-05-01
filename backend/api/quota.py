"""
Quota management endpoints (gaps G3 + G4).

- Admin: redistribution options/preview/apply/suggest for users they created.
- Owner: set admin-level limits (max_users, daily_quota).
"""

import sys
from pathlib import Path
from typing import Dict, Any
import logging

from fastapi import APIRouter, Depends, HTTPException, status

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.dependencies import (
    get_current_user,
    get_current_admin_user,
    get_current_owner_user,
)
from backend.models.schemas import QuotaAllocations, AdminLimitsRequest, GenericActionResponse
from backend.services import quota_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status")
async def get_my_quota_status(current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """Current user's own quota status."""
    return quota_service.get_user_quota_status(current_user["username"])


@router.get("/redistribution")
async def get_redistribution(current_user: dict = Depends(get_current_admin_user)) -> Dict[str, Any]:
    """Admin view: current allocations for users the admin created."""
    return quota_service.get_redistribution_options(current_user["username"])


@router.post("/redistribution/preview")
async def preview_redistribution(
    req: QuotaAllocations,
    current_user: dict = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Validate a proposed redistribution without applying it."""
    return quota_service.preview_redistribution(current_user["username"], req.allocations)


@router.post("/redistribution/apply")
async def apply_redistribution(
    req: QuotaAllocations,
    current_user: dict = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Apply a previously-previewed redistribution."""
    result = quota_service.apply_redistribution(current_user["username"], req.allocations)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "Redistribution failed"),
        )
    return result


@router.get("/redistribution/suggest")
async def suggest_redistribution(current_user: dict = Depends(get_current_admin_user)) -> Dict[str, Any]:
    """Return system-suggested optimal allocations based on usage patterns."""
    return quota_service.suggest_optimal(current_user["username"])


@router.get("/admin-limits")
async def get_all_admin_limits(current_user: dict = Depends(get_current_owner_user)) -> Dict[str, Any]:
    """Owner view: see all admin limits and usage."""
    return quota_service.get_all_admin_limits()


@router.put("/admin-limits", response_model=GenericActionResponse)
async def set_admin_limits(
    req: AdminLimitsRequest,
    current_user: dict = Depends(get_current_owner_user),
):
    """Owner-only: set an Admin's max_users and daily_quota pool."""
    result = quota_service.set_admin_limits(
        admin_username=req.admin_username,
        max_users=req.max_users,
        daily_quota=req.daily_quota,
        owner_username=current_user["username"],
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "Failed to set admin limits"),
        )
    return GenericActionResponse(success=True, message=result.get("message"))
