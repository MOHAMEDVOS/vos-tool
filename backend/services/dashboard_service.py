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


def _filter_df_by_date(df, start_date: Optional[date], end_date: Optional[date]):
    if df is None or getattr(df, "empty", True):
        return df

    try:
        import pandas as pd

        ts_col = None
        for candidate in ["audit_timestamp", "Timestamp", "timestamp", "created_at"]:
            if candidate in df.columns:
                ts_col = candidate
                break

        if not ts_col:
            return df

        dt = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
        keep = dt.notna()
        if start_date:
            keep &= (dt.dt.date >= start_date)
        if end_date:
            keep &= (dt.dt.date <= end_date)
        return df.loc[keep]
    except Exception:
        return df


def get_agent_audits(
    username: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    agent_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get agent audit records."""
    try:
        # Convert DataFrame to list of dicts
        df = dashboard_manager.get_combined_agent_audit_data(username)
        if df is not None and not df.empty:
            if agent_name:
                if "Agent Name" in df.columns:
                    df = df[df["Agent Name"] == agent_name]
                elif "agent_name" in df.columns:
                    df = df[df["agent_name"] == agent_name]
            if start_date or end_date:
                df = _filter_df_by_date(df, start_date, end_date)
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
        df = dashboard_manager.get_combined_lite_audit_data(username)
        if df is not None and not df.empty and (start_date or end_date):
            df = _filter_df_by_date(df, start_date, end_date)
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
            dashboard_manager.clear_campaign_audit_data(username=username, campaign_name=campaign)
        else:
            # Clear all campaigns
            campaigns = dashboard_manager.get_available_campaigns(username)
            for camp in campaigns:
                dashboard_manager.clear_campaign_audit_data(username=username, campaign_name=camp)
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



def get_flagged_calls(
    username: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Return the combined agent+lite audits filtered to flagged rows (G12).

    Flagged logic mirrors app.py::get_actions_flagged_count:
      (Releasing=Yes OR Late Hello=Yes) with (Rebuttal in No/N/A)
      OR Rebuttal Detection = No
    """
    try:
        import pandas as pd
        agent_df = dashboard_manager.get_combined_agent_audit_data(username)
        lite_df = dashboard_manager.get_combined_lite_audit_data(username)

        def _drop_campaign_rows(df):
            """Exclude rows that belong to a campaign audit (have Campaign Name set)."""
            if df is None or df.empty:
                return df
            if "Campaign Name" in df.columns:
                return df[df["Campaign Name"].isna() | (df["Campaign Name"].astype(str).str.strip() == "")]
            return df

        agent_df = _drop_campaign_rows(agent_df)
        lite_df  = _drop_campaign_rows(lite_df)

        frames = [df for df in (agent_df, lite_df) if df is not None and not df.empty]
        if not frames:
            return []
        combined = pd.concat(frames, ignore_index=True)

        if start_date or end_date:
            combined = _filter_df_by_date(combined, start_date, end_date)

        if combined.empty:
            return []

        quality = (
            (combined.get("Releasing Detection", "No") == "Yes")
            | (combined.get("Late Hello Detection", "No") == "Yes")
        )

        if "Rebuttal Detection" in combined.columns:
            no_rebuttal = combined["Rebuttal Detection"].isin(["No", "N/A"])
            rebuttal_issue = combined["Rebuttal Detection"] == "No"
            # "No" stays "No" whether or not the owner ever objected -- the
            # column is strictly Yes/No. "Objection Gate" carries why, and a
            # "No" with no objection to rebut isn't a fair flag.
            # See docs/REBUTTAL_FALSE_FLAGS.md.
            if "Objection Gate" in combined.columns:
                no_objection = combined["Objection Gate"] == "no_objection"
                rebuttal_issue = rebuttal_issue & ~no_objection
        else:
            no_rebuttal = pd.Series([True] * len(combined), index=combined.index)
            rebuttal_issue = pd.Series([False] * len(combined), index=combined.index)

        # Long Voicemail / Dead Call rows carry a free-text label (e.g. "Voicemail 28s");
        # "No"/blank means not flagged. Mirror webapp isRowFlagged().
        if "Long VM/Dead Detection" in combined.columns:
            long_vals = combined["Long VM/Dead Detection"].fillna("").astype(str).str.strip()
            long_call = ~long_vals.isin(["", "No"])
        else:
            long_call = pd.Series([False] * len(combined), index=combined.index)

        flagged = combined[(quality & no_rebuttal) | rebuttal_issue | long_call]
        if flagged.empty:
            return []
        import json as _json
        return _json.loads(flagged.to_json(orient="records", force_ascii=False))
    except Exception as e:
        logger.error(f"get_flagged_calls failed: {e}", exc_info=True)
        return []


def get_flagged_count(username: str) -> int:
    """Cheap count used by the nav badge."""
    try:
        return len(get_flagged_calls(username))
    except Exception as e:
        logger.error(f"get_flagged_count failed: {e}", exc_info=True)
        return 0
