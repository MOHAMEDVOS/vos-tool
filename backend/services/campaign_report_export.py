"""
Orchestrates campaign report export: Google Sheet + Google Doc creation.
Uses service account credentials. Files are shared with the logged-in user.
"""

import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.dashboard_manager import dashboard_manager
from lib.campaign_metrics import build_doc_field_mapping
from lib.google_workspace import (
    get_service_account_credentials,
    build_drive,
    build_sheets,
    build_docs,
    copy_template_doc,
    create_spreadsheet,
    replace_doc_placeholders,
    style_report_doc,
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
    Full pipeline:
    1. Fetch audit rows for the campaign.
    2. Build a Google Sheet with the raw data.
    3. Copy the Doc template, fill placeholders with computed metrics.
    4. Share both files with the logged-in user.
    5. Return { sheet_url, doc_url }.
    """
    from backend.core.config import settings

    template_id = settings.GOOGLE_DOC_TEMPLATE_ID
    if not template_id:
        raise ValueError("GOOGLE_DOC_TEMPLATE_ID is not configured")

    folder_id = settings.GOOGLE_REPORT_DRIVE_FOLDER_ID
    if not folder_id:
        raise ValueError("GOOGLE_REPORT_DRIVE_FOLDER_ID is not configured")

    # --- Load service account credentials ---
    creds = get_service_account_credentials()
    drive = build_drive(creds)
    sheets_svc = build_sheets(creds)
    docs_svc = build_docs(creds)

    # --- Fetch audit data ---
    df = dashboard_manager.load_campaign_audit_data(campaign_name, start_date, end_date, username)
    if df is None or df.empty:
        raise ValueError(f"No audit data found for campaign '{campaign_name}'")

    raw_rows = df.to_dict("records")
    
    # Filter rows to match dashboard logic: only keep Lite Audits if they are flagged
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
            # Lite Audit, unknown, or missing type → only include if flagged
            if is_flagged(r):
                rows.append(r)

    if not rows:
        raise ValueError(f"No flagged audit data found for campaign '{campaign_name}'")

    # --- Create Sheet ---
    logger.info(f"Creating Sheet for campaign '{campaign_name}' ({len(rows)} rows)")
    sheet_id, sheet_url = create_spreadsheet(drive, sheets_svc, name=campaign_name, rows=rows, folder_id=folder_id)

    # --- Build placeholder mapping ---
    mapping = build_doc_field_mapping(
        rows=rows,
        campaign_name=campaign_name,
        sheet_url=sheet_url,
        start_date=str(start_date) if start_date else "",
        end_date=str(end_date) if end_date else "",
    )

    # --- Copy & fill Doc ---
    logger.info(f"Copying Doc template for campaign '{campaign_name}'")
    doc_name = f"{campaign_name} – performance report"
    sheet_name = f"{campaign_name} – audit data"
    doc_id = copy_template_doc(drive, template_id, doc_name, folder_id=folder_id)
    replace_doc_placeholders(docs_svc, doc_id, mapping)
    style_report_doc(docs_svc, doc_id, sheet_url, sheet_name)

    # --- Share both files with the logged-in user ---
    logger.info(f"Sharing files with {username}")
    share_file_with_user(drive, sheet_id, username)
    share_file_with_user(drive, doc_id, username)

    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
    logger.info(f"Campaign report generated: doc={doc_url} sheet={sheet_url}")

    return {"sheet_url": sheet_url, "doc_url": doc_url}
