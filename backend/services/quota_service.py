"""
Quota management service (gaps G3 + G4).

Wraps tools.quota_redistribution.get_redistribution_manager() and
lib.dashboard_manager.user_manager.set_admin_limits_as_owner().
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional
import logging

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.quota_redistribution import get_redistribution_manager
from lib.quota_manager import quota_manager
from lib.dashboard_manager import user_manager

logger = logging.getLogger(__name__)


def _redistribution():
    return get_redistribution_manager(quota_manager)


def get_redistribution_options(admin_username: str) -> Dict[str, Any]:
    try:
        return _redistribution().get_redistribution_options(admin_username)
    except Exception as e:
        logger.error(f"get_redistribution_options failed: {e}", exc_info=True)
        return {"error": str(e)}


def preview_redistribution(admin_username: str, new_allocations: Dict[str, int]) -> Dict[str, Any]:
    try:
        return _redistribution().calculate_redistribution_impact(admin_username, new_allocations)
    except Exception as e:
        logger.error(f"preview_redistribution failed: {e}", exc_info=True)
        return {"valid": False, "error": str(e)}


def apply_redistribution(admin_username: str, new_allocations: Dict[str, int]) -> Dict[str, Any]:
    try:
        success, message = _redistribution().apply_redistribution(admin_username, new_allocations)
        return {"success": success, "message": message}
    except Exception as e:
        logger.error(f"apply_redistribution failed: {e}", exc_info=True)
        return {"success": False, "message": str(e)}


def suggest_optimal(admin_username: str) -> Dict[str, Any]:
    try:
        return _redistribution().suggest_optimal_redistribution(admin_username)
    except Exception as e:
        logger.error(f"suggest_optimal failed: {e}", exc_info=True)
        return {"error": str(e)}


def set_admin_limits(
    admin_username: str,
    max_users: int,
    daily_quota: int,
    owner_username: str,
) -> Dict[str, Any]:
    """Owner-only. Maps to user_manager.set_admin_limits_as_owner().

    Validates target is an existing Admin (old_app.py:1295-1304 dropdown filtered to Admins).
    """
    target_role = user_manager.get_user_role(admin_username)
    if target_role != "Admin":
        return {
            "success": False,
            "message": f"'{admin_username}' is not an Admin user (role: {target_role or 'not found'})"
        }
    try:
        success, message = user_manager.set_admin_limits_as_owner(
            admin_username, max_users, daily_quota, owner_username
        )
        return {"success": success, "message": message}
    except Exception as e:
        logger.error(f"set_admin_limits failed: {e}", exc_info=True)
        return {"success": False, "message": str(e)}


def get_all_admin_limits() -> Dict[str, Any]:
    try:
        return quota_manager.get_all_admin_limits()
    except Exception as e:
        logger.error(f"get_all_admin_limits failed: {e}", exc_info=True)
        return {}


def get_user_quota_status(username: str) -> Dict[str, Any]:
    """Convenience getter used by the dashboard UI."""
    try:
        return quota_manager.get_user_quota_status(username)
    except Exception as e:
        logger.error(f"get_user_quota_status failed: {e}", exc_info=True)
        return {"error": str(e)}
