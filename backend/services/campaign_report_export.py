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
from backend.services.campaign_report_doc import create_campaign_doc
from backend.services.dashboard_service import is_call_flagged
from lib.google_workspace import (
    get_service_account_credentials,
    build_docs,
    build_drive,
    build_sheets,
    create_spreadsheet,
    share_file_with_user,
)

logger = logging.getLogger(__name__)


def _is_flagged(row: Dict[str, Any]) -> bool:
    # Delegates to dashboard_service.is_call_flagged so the campaign export
    # always matches the main dashboard's flagged-call logic exactly --
    # see that function's docstring for the full rule.
    return is_call_flagged(row)


def _select_report_rows(raw_rows: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    rows = []
    for row in raw_rows:
        audit_type = row.get('Audit Type') or row.get('audit_type')
        is_heavy_audit = audit_type in ('Heavy Audit', 'Heavy', 'Agent Audit')
        if is_heavy_audit or _is_flagged(row):
            rows.append(row)
    return rows


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
    4. Fill a copy of the Doc template with the campaign's numbers (the Sheet is still returned if this fails).
    5. Return { sheet_url, doc_url }.
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

    rows = _select_report_rows(raw_rows)

    if not rows:
        raise ValueError(f"No flagged audit data found for campaign '{campaign_name}'")

    # --- Create Sheet ---
    logger.info(f"Creating Sheet for campaign '{campaign_name}' ({len(rows)} rows)")
    sheet_id, sheet_url = create_spreadsheet(drive, sheets_svc, name=campaign_name, rows=rows, folder_id=folder_id)

    # --- Share with the logged-in user ---
    logger.info(f"Sharing sheet with {username}")
    share_file_with_user(drive, sheet_id, username)

    doc_url = None
    try:
        scan = dashboard_manager.get_campaign_disposition_scan(campaign_name, username, start_date, end_date)
        doc_url = create_campaign_doc(
            drive, build_docs(creds),
            template_id=settings.GOOGLE_DOC_TEMPLATE_ID, folder_id=folder_id, campaign=campaign_name,
            start_date=start_date, end_date=end_date, rows=rows, scan=scan, sheet_url=sheet_url,
            dialer=str(rows[0].get("Dialer Name") or ""),
        )
        share_file_with_user(drive, doc_url.split("/d/")[1].split("/")[0], username)
    except Exception:
        logger.error(f"Campaign doc failed for '{campaign_name}'; sheet is still returned", exc_info=True)

    logger.info(f"Campaign report generated: sheet={sheet_url} doc={doc_url}")
    return {"sheet_url": sheet_url, "doc_url": doc_url}
