"""
User-scoped API endpoints.

Provides aggregated "everything" payloads for the current user (and admin/owner access for other users).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any, Dict, Optional
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.dependencies import get_current_user, get_current_admin_user

from lib.database import get_db_manager
from lib.dashboard_manager import dashboard_manager, user_manager
from lib.quota_manager import quota_manager

from backend.services.dashboard_service import (
    get_agent_audits,
    get_lite_audits,
    get_campaign_audits,
    get_available_campaigns,
)


router = APIRouter()


def _safe_recent(items, limit: int = 50):
    try:
        return items[:limit]
    except Exception:
        return []


def _get_user_profile(username: str) -> Dict[str, Any]:
    user_data = user_manager.get_user(username) or {}
    role = user_manager.get_user_role(username)
    return {
        "username": username,
        "role": role,
        "daily_limit": user_data.get("daily_limit"),
        "readymode_user": user_data.get("readymode_user"),
        "has_assemblyai_key": bool(user_data.get("assemblyai_api_key_encrypted")),
    }


def _get_quota_and_usage(username: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    # Quota status
    try:
        if quota_manager:
            result["quota_status"] = quota_manager.get_user_quota_status(username)
        else:
            result["quota_status"] = {"managed": False}
    except Exception as e:
        result["quota_status"] = {"error": str(e)}

    # Daily usage info (download counters + quota integration)
    try:
        result["daily_usage"] = dashboard_manager.get_daily_usage_info(username)
    except Exception as e:
        result["daily_usage"] = {"error": str(e)}

    return result


def _get_dashboard_sharing(username: str) -> Dict[str, Any]:
    try:
        mode = dashboard_manager.get_user_dashboard_mode(username)
        data: Dict[str, Any] = {
            "mode": mode,
            "shared_users": dashboard_manager.get_shared_users(username),
        }
        if mode != "isolated":
            groups = dashboard_manager.get_sharing_groups() or {}
            data["group"] = groups.get(mode)
        return data
    except Exception as e:
        return {"error": str(e)}


def _get_phrase_stats() -> Dict[str, Any]:
    db = get_db_manager()
    if not db:
        return {"error": "Database not available"}

    def _count(table: str) -> Optional[int]:
        row = db.execute_query(f"SELECT COUNT(*) AS c FROM {table}", fetchone=True)
        if not row:
            return 0
        return int(row.get("c", 0))

    try:
        return {
            "repository_phrases": _count("repository_phrases"),
            "rebuttal_phrases": _count("rebuttal_phrases"),
            "pending_phrases": _count("pending_phrases"),
            "phrase_blacklist": _count("phrase_blacklist"),
        }
    except Exception as e:
        return {"error": str(e)}


def _get_learned_rebuttals_summary() -> Dict[str, Any]:
    db = get_db_manager()
    if db:
        try:
            total_row = db.execute_query(
                "SELECT COUNT(*)::bigint AS total FROM learned_rebuttals",
                fetchone=True,
            )
            by_cat = db.execute_query(
                "SELECT category, COUNT(*)::bigint AS count FROM learned_rebuttals GROUP BY category ORDER BY count DESC",
                fetch=True,
            )
            return {
                "total": int(total_row.get("total", 0)) if total_row else 0,
                "by_category": by_cat,
            }
        except Exception:
            # Fall through to JSON fallback
            pass

    # JSON fallback
    try:
        with open("dashboard_data/learned_rebuttals.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        learned = data.get("learned_phrases", {})
        total = 0
        by_category: Dict[str, int] = {}
        for category, phrases in learned.items():
            count = len(phrases) if isinstance(phrases, list) else 0
            total += count
            by_category[category] = count
        return {"total": total, "by_category": by_category, "source": "json_fallback"}
    except Exception as e:
        return {"error": str(e)}


def _get_subscription_info() -> Dict[str, Any]:
    db = get_db_manager()
    if not db:
        return {"error": "Database not available"}

    try:
        plan = db.execute_query(
            "SELECT * FROM subscription_data ORDER BY created_at DESC NULLS LAST LIMIT 1",
            fetchone=True,
        )
        if plan and "payment_history" in plan and isinstance(plan["payment_history"], str):
            # Keep as-is; caller can parse if needed.
            pass

        active_clients = db.execute_query(
            "SELECT * FROM client_subscriptions WHERE is_active = TRUE ORDER BY created_at DESC NULLS LAST LIMIT 200",
            fetch=True,
        )

        return {
            "subscription_data": plan,
            "active_client_subscriptions": active_clients,
        }
    except Exception as e:
        return {"error": str(e)}


def _get_audits(username: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    try:
        agent = get_agent_audits(username)
        result["agent"] = {"total": len(agent), "recent": _safe_recent(agent)}
    except Exception as e:
        result["agent"] = {"error": str(e)}

    try:
        lite = get_lite_audits(username)
        result["lite"] = {"total": len(lite), "recent": _safe_recent(lite)}
    except Exception as e:
        result["lite"] = {"error": str(e)}

    try:
        campaigns = get_available_campaigns(username)
        campaign_records = get_campaign_audits(username)
        result["campaign"] = {
            "campaigns": campaigns,
            "total": len(campaign_records),
            "recent": _safe_recent(campaign_records),
        }
    except Exception as e:
        result["campaign"] = {"error": str(e)}

    return result


def _get_everything_payload(username: str) -> Dict[str, Any]:
    return {
        "user": _get_user_profile(username),
        "quota_and_usage": _get_quota_and_usage(username),
        "dashboard_sharing": _get_dashboard_sharing(username),
        "audits": _get_audits(username),
        "phrase_stats": _get_phrase_stats(),
        "learned_rebuttals": _get_learned_rebuttals_summary(),
        "subscriptions": _get_subscription_info(),
    }


@router.get("/me/everything")
async def get_my_everything(current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """Return aggregated data for the current user."""
    return _get_everything_payload(current_user["username"])


@router.get("/{username}/everything")
async def get_user_everything(
    username: str,
    current_user: dict = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Return aggregated data for any user (admin/owner only)."""
    if not user_manager.get_user(username):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return _get_everything_payload(username)
