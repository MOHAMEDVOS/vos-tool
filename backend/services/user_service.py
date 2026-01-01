"""
User management service.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.dashboard_manager import user_manager

logger = logging.getLogger(__name__)


def get_user(username: str) -> Optional[Dict[str, Any]]:
    """Get user data."""
    try:
        return user_manager.get_user(username)
    except Exception as e:
        logger.error(f"Error getting user: {e}", exc_info=True)
        return None


def get_all_users() -> List[Dict[str, Any]]:
    """Get all users (admin only)."""
    try:
        users = user_manager.get_all_users()
        # Remove sensitive data
        result = []
        for username, user_data in users.items():
            result.append({
                "username": username,
                "role": user_manager.get_user_role(username),
                "daily_limit": user_data.get("daily_limit"),
                "readymode_user": user_data.get("readymode_user")
            })
        return result
    except Exception as e:
        logger.error(f"Error getting all users: {e}", exc_info=True)
        return []


def create_user(
    username: str,
    password: str,
    role: str = "Auditor",
    daily_limit: Optional[int] = None,
    readymode_username: Optional[str] = None,
    readymode_password: Optional[str] = None,
    assemblyai_api_key_encrypted: Optional[str] = None
) -> bool:
    """Create new user."""
    try:
        user_data = {
            "app_pass": password,
            "role": role,
            "daily_limit": daily_limit or 5000,
            "created_by": username,
            "readymode_user": readymode_username,
            "readymode_pass": readymode_password,
            "assemblyai_api_key_encrypted": assemblyai_api_key_encrypted
        }
        
        return user_manager.add_user(username, user_data, username)
    except Exception as e:
        logger.error(f"Error creating user: {e}", exc_info=True)
        return False


def update_user(
    username: str,
    updated_by: str,
    password: Optional[str] = None,
    role: Optional[str] = None,
    daily_limit: Optional[int] = None,
    readymode_username: Optional[str] = None,
    readymode_password: Optional[str] = None,
    assemblyai_api_key: Optional[str] = None,
) -> bool:
    """Update user."""
    try:
        user_data = {}
        if password:
            user_data["app_pass"] = password
        if role:
            user_data["role"] = role
        if daily_limit is not None:
            user_data["daily_limit"] = daily_limit
        if readymode_username:
            user_data["readymode_user"] = readymode_username
        if readymode_password:
            user_data["readymode_pass"] = readymode_password
        # Pass plaintext key; dashboard_manager handles encryption into
        # assemblyai_api_key_encrypted when updating storage
        if assemblyai_api_key is not None:
            user_data["assemblyai_api_key"] = assemblyai_api_key
        
        return user_manager.update_user(username, user_data, updated_by)
    except Exception as e:
        logger.error(f"Error updating user: {e}", exc_info=True)
        return False


def delete_user(username: str, deleted_by: str) -> bool:
    """Delete user."""
    try:
        return user_manager.remove_user(username, deleted_by)
    except Exception as e:
        logger.error(f"Error deleting user: {e}", exc_info=True)
        return False


def get_user_settings(username: str) -> Dict[str, Any]:
    """Get user settings."""
    try:
        user_data = user_manager.get_user(username)
        if not user_data:
            return {}
        
        # Decrypt AssemblyAI API key if it exists
        assemblyai_api_key = None
        if user_data.get("assemblyai_api_key_encrypted"):
            try:
                from lib.security_utils import security_manager
                if security_manager:
                    assemblyai_api_key = security_manager.decrypt_string(
                        user_data["assemblyai_api_key_encrypted"]
                    )
            except Exception as e:
                logger.error(f"Error decrypting AssemblyAI API key for user {username}: {e}")
        
        return {
            "daily_limit": user_data.get("daily_limit"),
            "readymode_user": user_data.get("readymode_user"),
            "role": user_manager.get_user_role(username),
            # Expose both encrypted and decrypted forms for internal callers.
            # API schemas generally only surface the encrypted flag / status.
            "assemblyai_api_key_encrypted": user_data.get("assemblyai_api_key_encrypted"),
            "assemblyai_api_key": assemblyai_api_key,
        }
    except Exception as e:
        logger.error(f"Error getting user settings: {e}", exc_info=True)
        return {}


def update_user_settings(
    username: str,
    daily_limit: Optional[int] = None,
    readymode_username: Optional[str] = None,
    readymode_password: Optional[str] = None,
    assemblyai_api_key: Optional[str] = None,
) -> bool:
    """Update user settings."""
    try:
        user_data = {}
        if daily_limit is not None:
            user_data["daily_limit"] = daily_limit
        if readymode_username:
            user_data["readymode_user"] = readymode_username
        if readymode_password:
            user_data["readymode_pass"] = readymode_password
        # Pass plaintext key; dashboard_manager handles encryption into
        # assemblyai_api_key_encrypted at the storage layer.
        if assemblyai_api_key is not None:
            user_data["assemblyai_api_key"] = assemblyai_api_key
        
        return user_manager.update_user(username, user_data, username)
    except Exception as e:
        logger.error(f"Error updating user settings: {e}", exc_info=True)
        return False
