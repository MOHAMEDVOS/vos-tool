"""
Dashboard sharing-group service (gap G5).

Wraps DashboardManager's sharing-group methods.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any
import logging

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.dashboard_manager import dashboard_manager

logger = logging.getLogger(__name__)


def get_sharing_config() -> Dict[str, Any]:
    """Full sharing config (groups + per-user dashboard_mode)."""
    try:
        return dashboard_manager._load_sharing_config()
    except Exception as e:
        logger.error(f"get_sharing_config failed: {e}", exc_info=True)
        return {"sharing_groups": {}, "user_dashboard_mode": {}}


def list_groups() -> Dict[str, Any]:
    """Just the groups dict for UIs that don't need user modes."""
    return get_sharing_config().get("sharing_groups", {})


def create_group(group_name: str, members: List[str], created_by: str) -> bool:
    try:
        return dashboard_manager.create_sharing_group(group_name, members, created_by)
    except Exception as e:
        logger.error(f"create_group failed: {e}", exc_info=True)
        return False


def update_group(group_name: str, new_members: List[str]) -> bool:
    try:
        return dashboard_manager.update_sharing_group(group_name, new_members)
    except Exception as e:
        logger.error(f"update_group failed: {e}", exc_info=True)
        return False


def delete_group(group_name: str) -> bool:
    try:
        return dashboard_manager.remove_sharing_group(group_name)
    except Exception as e:
        logger.error(f"delete_group failed: {e}", exc_info=True)
        return False


def sync_modes() -> Dict[str, Any]:
    """Force-sync user dashboard modes from current group memberships."""
    try:
        success, message, count = dashboard_manager.sync_group_user_modes()
        return {"success": success, "message": message, "updated_count": count}
    except Exception as e:
        logger.error(f"sync_modes failed: {e}", exc_info=True)
        return {"success": False, "message": str(e), "updated_count": 0}


def get_user_mode(username: str) -> str:
    try:
        return dashboard_manager.get_user_dashboard_mode(username)
    except Exception as e:
        logger.error(f"get_user_mode failed: {e}", exc_info=True)
        return "isolated"
