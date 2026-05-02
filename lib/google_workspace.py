"""
Thin Google Workspace API helpers.
Handles credential loading/refresh and provides simple wrappers around
Drive, Sheets, and Docs API operations needed for campaign report export.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Tuple

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
]


def credentials_from_token_row(row: Dict[str, Any]) -> Credentials:
    """Build a Credentials object from a user_google_tokens DB row."""
    creds = Credentials(
        token=row.get("access_token"),
        refresh_token=row.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
    return creds


def build_drive(creds: Credentials):
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def build_sheets(creds: Credentials):
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def build_docs(creds: Credentials):
    return build("docs", "v1", credentials=creds, cache_discovery=False)


def copy_template_doc(drive, template_id: str, new_name: str, folder_id: str) -> str:
    """Copy the template Doc, rename it, move it to folder. Returns new doc_id."""
    body = {"name": new_name, "parents": [folder_id]}
    result = drive.files().copy(fileId=template_id, body=body).execute()
    return result["id"]


def create_spreadsheet(
    drive,
    sheets,
    name: str,
    folder_id: str,
    rows: List[Dict[str, Any]],
) -> Tuple[str, str]:
    """
    Create a new Google Sheet, write header + data rows, move to folder.
    Returns (sheet_id, sheet_url).
    """
    # Define columns (matching the screenshot header)
    columns = [
        "Agent Name", "Phone Number", "Disposition",
        "Releasing Detection", "Late Hello Detection", "Rebuttal Detection",
        "Transcription", "Dialer Name", "Agent Intro", "Owner Name",
        "Reason For Calling", "Intro Score", "Status",
    ]

    # Build values matrix: header + data rows
    header = [columns]
    data = []
    for r in rows:
        data.append([str(r.get(col, "")) for col in columns])

    body = {
        "properties": {"title": f"{name} – audit data"},
        "sheets": [{"properties": {"title": name}}],
    }
    spreadsheet = sheets.spreadsheets().create(body=body).execute()
    sheet_id = spreadsheet["spreadsheetId"]
    sheet_name = spreadsheet["sheets"][0]["properties"]["title"]

    # Write data
    range_name = f"'{sheet_name}'!A1"
    sheets.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=range_name,
        valueInputOption="RAW",
        body={"values": header + data},
    ).execute()

    # Move to target folder
    file = drive.files().get(fileId=sheet_id, fields="parents").execute()
    previous_parents = ",".join(file.get("parents", []))
    drive.files().update(
        fileId=sheet_id,
        addParents=folder_id,
        removeParents=previous_parents,
        fields="id, parents",
    ).execute()

    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    return sheet_id, sheet_url


def replace_doc_placeholders(docs, doc_id: str, mapping: Dict[str, str]) -> None:
    """
    Replace all {{placeholder}} strings in the Doc with computed values
    using the Docs batchUpdate replaceAllText API.
    """
    requests = []
    for placeholder, value in mapping.items():
        requests.append({
            "replaceAllText": {
                "containsText": {"text": placeholder, "matchCase": True},
                "replaceText": value or "",
            }
        })

    if requests:
        docs.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests},
        ).execute()
