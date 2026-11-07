"""
Dashboard service for managing audit data.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import date
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


def delete_agent_audit_results(username: str, agent_name: str) -> dict:
    """Delete one agent's Agent Audit results from the caller's shared dashboard."""
    return dashboard_manager.delete_agent_audit_results(username, agent_name)


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



def is_call_flagged(row: Dict[str, Any]) -> bool:
    """Per-row "is this call flagged" predicate (G12).

    This is the single source of truth for flagged-call logic -- both
    get_flagged_calls (below) and campaign_report_export._is_flagged call
    this function, so the main dashboard and the campaign export can never
    silently disagree about which rows are flagged again.

    Flagged if:
      (Releasing Detection == Yes OR Late Hello Detection == Yes)
        AND Rebuttal Detection in (No, N/A)
      OR Rebuttal Detection == No, unless the Objection Gate marks the miss
        as not a fair flag (no_objection / owner_ended_call / unusable)
      OR Long VM/Dead Detection carries a non-blank, non-"No" label
      OR Wrong Dispo Detection == Yes

    Accepts a row dict either from `DataFrame.to_dict('records')` (missing
    cell values show up as float NaN) or from a JSON round-trip (missing
    values are None) -- both are treated the same. A column that isn't in
    the row at all is treated the same as a blank value for that column,
    mirroring the old `column in df.columns` checks this replaced.
    """

    def _missing(value: Any) -> bool:
        return value is None or (isinstance(value, float) and value != value)

    def _get(column: str) -> Any:
        value = row.get(column)
        return None if _missing(value) else value

    quality = _get("Releasing Detection") == "Yes" or _get("Late Hello Detection") == "Yes"

    if "Rebuttal Detection" in row:
        rebuttal = _get("Rebuttal Detection")
        no_rebuttal = rebuttal in ("No", "N/A")
        rebuttal_issue = rebuttal == "No"
        # "No" stays "No" whether or not the owner ever objected -- the
        # column is strictly Yes/No. "Objection Gate" carries why, and a
        # "No" that wasn't a fair miss isn't a fair flag. Only these three
        # verdicts are excluded -- "unparseable" (no speaker labels, but
        # real content) and "no_attempt" stay flagged, since there's no
        # way to confirm those are unfair. See
        # analyzer/objection_gate.py and docs/REBUTTAL_FALSE_FLAGS.md.
        if "Objection Gate" in row:
            not_a_fair_miss = _get("Objection Gate") in (
                "no_objection", "owner_ended_call", "unusable"
            )
            rebuttal_issue = rebuttal_issue and not not_a_fair_miss
    else:
        no_rebuttal = True
        rebuttal_issue = False

    # Long Voicemail / Dead Call rows carry a free-text label (e.g. "Voicemail 28s");
    # "No"/blank means not flagged. Mirror webapp isRowFlagged().
    if "Long VM/Dead Detection" in row:
        long_val = str(_get("Long VM/Dead Detection") or "").strip()
        long_call = long_val not in ("", "No")
    else:
        long_call = False

    # Homeowner clearly asked not to be called again, but the agent logged a
    # disposition other than "DNC - Decision Maker" (lib/wrong_dispo_detector.py).
    wrong_dispo_issue = _get("Wrong Dispo Detection") == "Yes"

    return (quality and no_rebuttal) or rebuttal_issue or long_call or wrong_dispo_issue


def get_flagged_calls(
    username: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Return the combined agent+lite audits filtered to flagged rows (G12).

    Row-level flagged logic lives in is_call_flagged() above; see its
    docstring for the exact rule. campaign_report_export._is_flagged calls
    the same function so the two stay in agreement.
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

        import json as _json
        records = _json.loads(combined.to_json(orient="records", force_ascii=False))
        return [r for r in records if is_call_flagged(r)]
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
