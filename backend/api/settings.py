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
    get_current_owner_user,
    get_current_settings_user,
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
async def get_settings(current_user: dict = Depends(get_current_settings_user)):
    """Get current user settings (Owner/Admin only — legacy has_settings_access)."""
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
    current_user: dict = Depends(get_current_settings_user)
):
    """Update current user settings (Owner/Admin only — legacy has_settings_access)."""
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
        users = get_all_users(
            caller_username=current_user["username"],
            caller_role=current_user["role"]
        )
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
    """Create new user (admin only).

    Role restrictions mirror old_app.py:850:
    - Owner may create Auditor or Admin (never another Owner).
    - Admin may only create Auditor.
    """
    caller_role = current_user["role"]
    requested_role = request.role or "Auditor"

    if caller_role == "Admin" and requested_role != "Auditor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins can only create Auditor users"
        )
    if caller_role == "Owner" and requested_role not in ("Auditor", "Admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owners can only create Auditor or Admin users"
        )

    try:
        success = create_user(
            username=request.username,
            password=request.password,
            role=requested_role,
            created_by=current_user["username"],
            daily_limit=request.daily_limit,
            readymode_username=request.readymode_username,
            readymode_password=request.readymode_password,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user"
            )

        user_data = get_user_settings(request.username)
        return UserInfo(
            username=request.username,
            role=requested_role,
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


def _assert_can_modify(caller: dict, target_username: str) -> None:
    """Enforce legacy tenancy rules for user modification (old_app.py:899, 1032).

    - Owner: can modify anyone except the protected 'Mohamed Abdo' account.
    - Admin: can only modify users they created (get_admin_created_users).
    Raises HTTP 403 on violation.
    """
    from lib.dashboard_manager import user_manager as _um
    caller_role = caller["role"]
    caller_username = caller["username"]

    if target_username == "Mohamed Abdo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The protected owner account cannot be modified"
        )

    if caller_role == "Owner":
        return  # Owner can modify anyone (except protected, checked above)

    # Admin: only own created users
    created = _um.get_admin_created_users(caller_username)
    if target_username not in created:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins can only modify users they created"
        )


@router.put("/users/{username}", response_model=UserInfo)
async def update_existing_user(
    username: str,
    request: UpdateUserRequest,
    current_user: dict = Depends(get_current_admin_user)
):
    """Update user (Owner or Admin — with tenancy check, mirrors old_app.py:1454-1745)."""
    _assert_can_modify(current_user, username)

    # Admins cannot promote users to Admin or Owner (role escalation guard)
    if current_user["role"] == "Admin" and request.role and request.role in ("Admin", "Owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins cannot promote users to Admin or Owner"
        )

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
    current_user: dict = Depends(get_current_admin_user)
):
    """Delete user (Owner or Admin — with tenancy check, mirrors old_app.py:1021-1053)."""
    _assert_can_modify(current_user, username)

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



# ---------------------------------------------------------------------------
# Application-wide persistent settings (gap G6)
# ---------------------------------------------------------------------------
# Wraps lib.app_settings_manager.app_settings so the React UI does not need to
# import it directly. Supported categories today: "audio", "detection".


ALLOWED_APP_CONFIG_CATEGORIES = {"audio", "detection"}


@router.get("/app-config/{category}")
async def get_app_config_category(
    category: str,
    _: dict = Depends(get_current_owner_user),
):
    """Return persistent app-wide settings for a category (owner-only)."""
    if category not in ALLOWED_APP_CONFIG_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown app-config category '{category}'",
        )
    try:
        from lib.app_settings_manager import app_settings
        return app_settings.get_category(category)
    except Exception as e:
        logger.error(f"get_app_config_category failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load app config",
        )


@router.put("/app-config/{category}")
async def update_app_config_category(
    category: str,
    updates: dict,
    _: dict = Depends(get_current_owner_user),
):
    """Update multiple keys in a persistent app-config category (owner-only)."""
    if category not in ALLOWED_APP_CONFIG_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown app-config category '{category}'",
        )
    try:
        from lib.app_settings_manager import app_settings
        ok = app_settings.update_category(category, updates)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist settings",
            )
        return {"success": True, "category": category, "values": app_settings.get_category(category)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_app_config_category failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update app config",
        )


# ---------------------------------------------------------------------------
# AssemblyAI key: owner-of-key can read their decrypted value (gap G9)
# ---------------------------------------------------------------------------


@router.get("/assemblyai-key/reveal")
async def reveal_assemblyai_key(current_user: dict = Depends(get_current_user)):
    """Return the decrypted AssemblyAI key for the CURRENT user only.

    Used by the React audit UI to perform client-visible key checks without
    the Streamlit-style direct lib.security_manager import.
    """
    try:
        user_settings = get_user_settings(current_user["username"])
        encrypted = user_settings.get("assemblyai_api_key_encrypted")
        if not encrypted:
            return {"has_key": False, "api_key": None}

        try:
            from lib.security_utils import security_manager
            decrypted = security_manager.decrypt_string(encrypted)
            return {"has_key": True, "api_key": decrypted}
        except Exception as decrypt_err:
            logger.error(f"AssemblyAI key decryption failed: {decrypt_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to decrypt API key",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"reveal_assemblyai_key failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reveal API key",
        )
