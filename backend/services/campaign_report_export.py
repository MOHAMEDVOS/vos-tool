"""
Orchestrates campaign report export: Google Sheet + Google Doc creation.
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
    credentials_from_token_row,
    build_drive,
    build_sheets,
    build_docs,
    copy_template_doc,
    create_spreadsheet,
    replace_doc_placeholders,
)
from lib.security_utils import SecurityManager

logger = logging.getLogger(__name__)


def _load_google_tokens(username: str) -> Optional[Dict[str, Any]]:
    from lib.database import get_db_manager
    db = get_db_manager()
    if db is None:
        return None
    return db.execute_query(
        "SELECT access_token, refresh_token_encrypted, expires_at FROM user_google_tokens WHERE username = %s",
        (username,),
        fetchone=True,
    )


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
    4. Return { sheet_url, doc_url }.
    Raises ValueError if Google tokens are missing (frontend shows re-auth prompt).
    """
    from backend.core.config import settings

    # --- Load credentials ---
    token_row = _load_google_tokens(username)
    if not token_row or not token_row.get("refresh_token_encrypted"):
        raise ValueError("google_not_connected")

    sec = SecurityManager()
    decrypted_refresh = sec.decrypt_string(token_row["refresh_token_encrypted"])
    token_row = dict(token_row)
    token_row["refresh_token"] = decrypted_refresh

    creds = credentials_from_token_row(token_row)
    drive = build_drive(creds)
    sheets_svc = build_sheets(creds)
    docs_svc = build_docs(creds)

    folder_id = settings.GOOGLE_REPORT_DRIVE_FOLDER_ID
    template_id = settings.GOOGLE_DOC_TEMPLATE_ID

    if not folder_id:
        raise ValueError("GOOGLE_REPORT_DRIVE_FOLDER_ID is not configured")
    if not template_id:
        raise ValueError("GOOGLE_DOC_TEMPLATE_ID is not configured")

    # --- Fetch audit data ---
    df = dashboard_manager.load_campaign_audit_data(campaign_name, start_date, end_date, username)
    if df is None or df.empty:
        raise ValueError(f"No audit data found for campaign '{campaign_name}'")

    rows = df.to_dict("records")

    # --- Create Sheet ---
    logger.info(f"Creating Sheet for campaign '{campaign_name}' ({len(rows)} rows)")
    _, sheet_url = create_spreadsheet(
        drive, sheets_svc,
        name=campaign_name,
        folder_id=folder_id,
        rows=rows,
    )

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
    doc_id = copy_template_doc(drive, template_id, doc_name, folder_id)
    replace_doc_placeholders(docs_svc, doc_id, mapping)

    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
    logger.info(f"Campaign report generated: doc={doc_url} sheet={sheet_url}")

    return {"sheet_url": sheet_url, "doc_url": doc_url}
