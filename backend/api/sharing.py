"""
Dashboard sharing-group endpoints (gap G5).

Admin-only CRUD over DashboardManager's sharing config. Streamlit calls
these methods directly today; the React UI will use this router instead.
"""

import sys
from pathlib import Path
from typing import Dict, Any
import logging

from fastapi import APIRouter, Depends, HTTPException, status

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.dependencies import get_current_owner_user, get_current_user
from backend.models.schemas import (
    CreateSharingGroupRequest,
    UpdateSharingGroupRequest,
    GenericActionResponse,
)
from backend.services import sharing_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/config")
async def get_config(_: dict = Depends(get_current_owner_user)) -> Dict[str, Any]:
    """Admin view: groups + per-user dashboard modes."""
    return sharing_service.get_sharing_config()


@router.get("/groups")
async def list_groups(_: dict = Depends(get_current_owner_user)) -> Dict[str, Any]:
    return sharing_service.list_groups()


@router.post("/groups", response_model=GenericActionResponse)
async def create_group(
    req: CreateSharingGroupRequest,
    current_user: dict = Depends(get_current_owner_user),
):
    ok = sharing_service.create_group(
        group_name=req.group_name,
        members=req.members,
        created_by=current_user["username"],
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Group '{req.group_name}' could not be created (likely already exists)",
        )
    return GenericActionResponse(success=True, message=f"Group '{req.group_name}' created")


@router.put("/groups/{group_name}", response_model=GenericActionResponse)
async def update_group(
    group_name: str,
    req: UpdateSharingGroupRequest,
    _: dict = Depends(get_current_owner_user),
):
    ok = sharing_service.update_group(group_name, req.members)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group '{group_name}' not found",
        )
    return GenericActionResponse(success=True, message=f"Group '{group_name}' updated")


@router.delete("/groups/{group_name}", response_model=GenericActionResponse)
async def delete_group(
    group_name: str,
    _: dict = Depends(get_current_owner_user),
):
    ok = sharing_service.delete_group(group_name)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group '{group_name}' not found",
        )
    return GenericActionResponse(success=True, message=f"Group '{group_name}' deleted")


@router.post("/sync-modes")
async def sync_modes(_: dict = Depends(get_current_owner_user)) -> Dict[str, Any]:
    return sharing_service.sync_modes()


@router.get("/me/mode")
async def get_my_mode(current_user: dict = Depends(get_current_user)) -> Dict[str, str]:
    return {"mode": sharing_service.get_user_mode(current_user["username"])}
