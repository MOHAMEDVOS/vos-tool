"""
Settings API endpoints.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional, List
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.schemas import (
    UserSettings,
    CreateUserRequest,
    UpdateUserRequest,
    UserListResponse,
    UserInfo
)
from backend.core.dependencies import (
    get_current_user,
    get_current_admin_user,
    get_current_owner_user
)
from backend.services.user_service import (
    get_user_settings,
    update_user_settings,
    get_all_users,
    create_user,
    update_user,
    delete_user
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=UserSettings)
async def get_settings(current_user: dict = Depends(get_current_user)):
    """Get current user settings."""
    try:
        settings = get_user_settings(current_user["username"])
        return UserSettings(**settings)
    except Exception as e:
        logger.error(f"Error getting settings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get settings"
        )


@router.put("/assemblyai-key")
async def update_assemblyai_key(
    api_key_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Update user's AssemblyAI API key."""
    try:
        if "api_key" not in api_key_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key is required"
            )
        
        success = update_user_settings(
            username=current_user["username"],
            assemblyai_api_key=api_key_data["api_key"]
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update API key"
            )
        
        return {"status": "success", "message": "API key updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating AssemblyAI API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update API key"
        )


@router.get("/assemblyai-key", response_model=dict)
async def check_assemblyai_key(current_user: dict = Depends(get_current_user)):
    """Check if user has an AssemblyAI API key set."""
    try:
        settings = get_user_settings(current_user["username"])
        has_key = bool(settings.get("assemblyai_api_key_encrypted"))
        return {"has_key": has_key}
    except Exception as e:
        logger.error(f"Error checking AssemblyAI API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check API key status"
        )


@router.put("/", response_model=UserSettings)
async def update_settings(
    settings: UserSettings,
    current_user: dict = Depends(get_current_user)
):
    """Update current user settings."""
    try:
        success = update_user_settings(
            current_user["username"],
            daily_limit=settings.daily_limit,
            readymode_username=settings.readymode_username,
            readymode_password=settings.readymode_password
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update settings"
            )
        return get_user_settings(current_user["username"])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating settings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update settings"
        )


@router.get("/users", response_model=UserListResponse)
async def list_users(current_user: dict = Depends(get_current_admin_user)):
    """Get list of all users (admin only)."""
    try:
        users = get_all_users()
        user_infos = [
            UserInfo(
                username=u["username"],
                role=u["role"],
                daily_limit=u.get("daily_limit")
            )
            for u in users
        ]
        return UserListResponse(users=user_infos, total=len(user_infos))
    except Exception as e:
        logger.error(f"Error listing users: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )


@router.post("/users", response_model=UserInfo)
async def create_new_user(
    request: CreateUserRequest,
    current_user: dict = Depends(get_current_admin_user)
):
    """Create new user (admin only)."""
    try:
        success = create_user(
            request.username,
            request.password,
            request.role,
            current_user["username"],
            request.daily_limit,
            request.readymode_username,
            request.readymode_password
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user"
            )
        
        user_data = get_user_settings(request.username)
        return UserInfo(
            username=request.username,
            role=request.role,
            daily_limit=user_data.get("daily_limit")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )


@router.put("/users/{username}", response_model=UserInfo)
async def update_existing_user(
    username: str,
    request: UpdateUserRequest,
    current_user: dict = Depends(get_current_owner_user)
):
    """Update user (owner only)."""
    try:
        success = update_user(
            username,
            current_user["username"],
            password=request.password,
            role=request.role,
            daily_limit=request.daily_limit,
            readymode_username=request.readymode_username,
            readymode_password=request.readymode_password
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update user"
            )
        
        user_data = get_user_settings(username)
        from lib.dashboard_manager import user_manager
        return UserInfo(
            username=username,
            role=user_manager.get_user_role(username),
            daily_limit=user_data.get("daily_limit")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@router.delete("/users/{username}")
async def delete_existing_user(
    username: str,
    current_user: dict = Depends(get_current_owner_user)
):
    """Delete user (owner only)."""
    try:
        success = delete_user(username, current_user["username"])
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete user"
            )
        return {"message": f"User {username} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )

