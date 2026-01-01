"""
Dashboard service for managing audit data.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import date, datetime
import logging

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.dashboard_manager import dashboard_manager

logger = logging.getLogger(__name__)


def get_agent_audits(
    username: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    agent_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get agent audit records."""
    try:
        # Convert DataFrame to list of dicts
        df = dashboard_manager.load_agent_audit_data(
            username,
            start_date=start_date,
            end_date=end_date,
            agent_filter=agent_name
        )
        if df is not None and not df.empty:
            return df.to_dict('records')
        return []
    except Exception as e:
        logger.error(f"Error loading agent audits: {e}", exc_info=True)
        return []


def get_lite_audits(
    username: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List[Dict[str, Any]]:
    """Get lite audit records."""
    try:
        df = dashboard_manager.load_lite_audit_data(
            username,
            start_date=start_date,
            end_date=end_date
        )
        if df is not None and not df.empty:
            return df.to_dict('records')
        return []
    except Exception as e:
        logger.error(f"Error loading lite audits: {e}", exc_info=True)
        return []


def get_campaign_audits(
    username: str,
    campaign: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List[Dict[str, Any]]:
    """Get campaign audit records."""
    try:
        if campaign:
            df = dashboard_manager.load_campaign_audit_data(
                campaign,
                start_date,
                end_date,
                username
            )
            if df is not None and not df.empty:
                return df.to_dict('records')
            return []
        else:
            # Get all campaigns
            campaigns = dashboard_manager.get_available_campaigns(username)
            all_data = []
            for camp in campaigns:
                df = dashboard_manager.load_campaign_audit_data(
                    camp,
                    start_date,
                    end_date,
                    username
                )
                if df is not None and not df.empty:
                    all_data.extend(df.to_dict('records'))
            return all_data
    except Exception as e:
        logger.error(f"Error loading campaign audits: {e}", exc_info=True)
        return []


def clear_agent_audits(username: str) -> bool:
    """Clear all agent audit data for user."""
    try:
        dashboard_manager.clear_agent_audit_data(username)
        return True
    except Exception as e:
        logger.error(f"Error clearing agent audits: {e}", exc_info=True)
        return False


def clear_lite_audits(username: str) -> bool:
    """Clear all lite audit data for user."""
    try:
        dashboard_manager.clear_lite_audit_data(username)
        return True
    except Exception as e:
        logger.error(f"Error clearing lite audits: {e}", exc_info=True)
        return False


def clear_campaign_audits(username: str, campaign: Optional[str] = None) -> bool:
    """Clear campaign audit data."""
    try:
        if campaign:
            dashboard_manager.clear_campaign_audit_data(campaign, username)
        else:
            # Clear all campaigns
            campaigns = dashboard_manager.get_available_campaigns(username)
            for camp in campaigns:
                dashboard_manager.clear_campaign_audit_data(camp, username)
        return True
    except Exception as e:
        logger.error(f"Error clearing campaign audits: {e}", exc_info=True)
        return False


def get_available_campaigns(username: str) -> List[str]:
    """Get list of available campaigns."""
    try:
        return dashboard_manager.get_available_campaigns(username)
    except Exception as e:
        logger.error(f"Error getting campaigns: {e}", exc_info=True)
        return []

