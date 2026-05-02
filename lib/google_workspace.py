"""
Google Workspace API helpers using service account credentials.
Service account creates files, then shares them with the logged-in user.
"""

import os
import json
import logging
from typing import Dict, List, Any, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
]


def get_service_account_credentials() -> service_account.Credentials:
    """Load service account credentials from GOOGLE_SERVICE_ACCOUNT_JSON env var."""
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON environment variable not set")
    sa_info = json.loads(sa_json)
    return service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)


def build_drive(creds):
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def build_sheets(creds):
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def build_docs(creds):
    return build("docs", "v1", credentials=creds, cache_discovery=False)


def share_file_with_user(drive, file_id: str, email: str) -> None:
    """Share a file with a user as Editor."""
    drive.permissions().create(
        fileId=file_id,
        body={"type": "user", "role": "writer", "emailAddress": email},
        sendNotificationEmail=False,
    ).execute()


def copy_template_doc(drive, template_id: str, new_name: str) -> str:
    """Copy the template Doc and rename it. Returns new doc_id."""
    body = {"name": new_name}
    result = drive.files().copy(fileId=template_id, body=body).execute()
    return result["id"]


def create_spreadsheet(
    sheets,
    name: str,
    rows: List[Dict[str, Any]],
) -> Tuple[str, str]:
    """
    Create a new Google Sheet and write header + data rows.
    Returns (sheet_id, sheet_url).
    """
    columns = [
        "Agent Name", "Phone Number", "Disposition",
        "Releasing Detection", "Late Hello Detection", "Rebuttal Detection",
        "Transcription", "Dialer Name", "Agent Intro", "Owner Name",
        "Reason For Calling", "Intro Score", "Status",
    ]

    header = [columns]
    data = [[str(r.get(col, "")) for col in columns] for r in rows]

    body = {
        "properties": {"title": f"{name} – audit data"},
        "sheets": [{"properties": {"title": name}}],
    }
    spreadsheet = sheets.spreadsheets().create(body=body).execute()
    sheet_id = spreadsheet["spreadsheetId"]
    sheet_name = spreadsheet["sheets"][0]["properties"]["title"]

    sheets.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{sheet_name}'!A1",
        valueInputOption="RAW",
        body={"values": header + data},
    ).execute()

    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    return sheet_id, sheet_url


def replace_doc_placeholders(docs, doc_id: str, mapping: Dict[str, str]) -> None:
    """Replace {{placeholder}} strings in the Doc via batchUpdate replaceAllText."""
    requests = [
        {
            "replaceAllText": {
                "containsText": {"text": placeholder, "matchCase": True},
                "replaceText": value or "",
            }
        }
        for placeholder, value in mapping.items()
    ]
    if requests:
        docs.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests},
        ).execute()
