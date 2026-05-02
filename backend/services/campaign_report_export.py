"""
Orchestrates campaign report export: Google Sheet creation.
Uses service account credentials. File is shared with the logged-in user.
"""

import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.dashboard_manager import dashboard_manager
from lib.google_workspace import (
    get_service_account_credentials,
    build_drive,
    build_sheets,
    create_spreadsheet,
    share_file_with_user,
)

logger = logging.getLogger(__name__)


def generate_campaign_report(
    username: str,
    campaign_name: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    1. Fetch audit rows for the campaign.
    2. Build a styled Google Sheet with the data.
    3. Share the file with the logged-in user.
    4. Return { sheet_url }.
    """
    from backend.core.config import settings

    folder_id = settings.GOOGLE_REPORT_DRIVE_FOLDER_ID
    if not folder_id:
        raise ValueError("GOOGLE_REPORT_DRIVE_FOLDER_ID is not configured")

    # --- Load service account credentials ---
    creds = get_service_account_credentials()
    drive = build_drive(creds)
    sheets_svc = build_sheets(creds)

    # --- Fetch audit data ---
    df = dashboard_manager.load_campaign_audit_data(campaign_name, start_date, end_date, username)
    if df is None or df.empty:
        raise ValueError(f"No audit data found for campaign '{campaign_name}'")

    raw_rows = df.to_dict("records")

    def is_flagged(r):
        return (
            r.get('Releasing Detection') == 'Yes' or
            r.get('Late Hello Detection') == 'Yes' or
            r.get('Rebuttal Detection') == 'No'
        )

    rows = []
    for r in raw_rows:
        audit_type = r.get('Audit Type') or r.get('audit_type')
        if audit_type in ('Heavy Audit', 'Heavy', 'Agent Audit'):
            rows.append(r)
        else:
            if is_flagged(r):
                rows.append(r)

    if not rows:
        raise ValueError(f"No flagged audit data found for campaign '{campaign_name}'")

    # --- Create Sheet ---
    logger.info(f"Creating Sheet for campaign '{campaign_name}' ({len(rows)} rows)")
    sheet_id, sheet_url = create_spreadsheet(drive, sheets_svc, name=campaign_name, rows=rows, folder_id=folder_id)

    # --- Share with the logged-in user ---
    logger.info(f"Sharing sheet with {username}")
    share_file_with_user(drive, sheet_id, username)

    logger.info(f"Campaign report generated: sheet={sheet_url}")
    return {"sheet_url": sheet_url}
