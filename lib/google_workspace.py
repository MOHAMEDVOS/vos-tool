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
        supportsAllDrives=True,
    ).execute()


def copy_template_doc(drive, template_id: str, new_name: str, folder_id: str) -> str:
    """Copy the template Doc and rename it. Returns new doc_id."""
    body = {"name": new_name, "parents": [folder_id]}
    result = drive.files().copy(fileId=template_id, body=body, supportsAllDrives=True).execute()
    return result["id"]


def _rgb(r: int, g: int, b: int) -> dict:
    return {"red": r / 255, "green": g / 255, "blue": b / 255}


# Sheet palette
_HEADER_BG   = _rgb(32, 73, 37)   # dark green
_HEADER_FG   = _rgb(255, 255, 255)
_RED_BG      = _rgb(192, 0, 0)
_GREEN_BG    = _rgb(0, 150, 57)
_DETECT_FG   = _rgb(255, 255, 255)
_STATUS_RED  = _rgb(192, 0, 0)
_STATUS_FG   = _rgb(255, 255, 255)


def create_spreadsheet(
    drive,
    sheets,
    name: str,
    rows: List[Dict[str, Any]],
    folder_id: str,
) -> Tuple[str, str]:
    """
    Create a new Google Sheet inside the specified Shared Drive folder.
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
        "name": f"{name} – audit data",
        "mimeType": "application/vnd.google-apps.spreadsheet",
        "parents": [folder_id]
    }
    spreadsheet = drive.files().create(body=body, supportsAllDrives=True).execute()
    sheet_id = spreadsheet["id"]

    # Write data
    sheets.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range="Sheet1!A1",
        valueInputOption="RAW",
        body={"values": header + data},
    ).execute()

    # --- Formatting ---
    num_rows = len(data)
    col_index = {c: i for i, c in enumerate(columns)}

    fmt_requests = []

    # 1. Header row: dark green bg, white bold text, frozen
    fmt_requests.append({
        "repeatCell": {
            "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": len(columns)},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {"foregroundColor": _HEADER_FG, "bold": True},
                    "horizontalAlignment": "CENTER",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
        }
    })
    fmt_requests.append({"updateSheetProperties": {
        "properties": {"sheetId": 0, "gridProperties": {"frozenRowCount": 1}},
        "fields": "gridProperties.frozenRowCount",
    }})

    # 2. Detection columns: Yes=red, No=green, cell-by-cell
    def _detection_requests(col_name: str, yes_is_bad: bool):
        col_i = col_index[col_name]
        reqs = []
        for row_i, r in enumerate(rows, start=1):
            val = str(r.get(col_name, "")).strip()
            if val not in ("Yes", "No"):
                continue
            if yes_is_bad:
                bg = _RED_BG if val == "Yes" else _GREEN_BG
            else:
                bg = _GREEN_BG if val == "Yes" else _RED_BG
            reqs.append({
                "repeatCell": {
                    "range": {"sheetId": 0,
                              "startRowIndex": row_i, "endRowIndex": row_i + 1,
                              "startColumnIndex": col_i, "endColumnIndex": col_i + 1},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": bg,
                            "textFormat": {"foregroundColor": _DETECT_FG, "bold": True},
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                }
            })
        return reqs

    fmt_requests += _detection_requests("Releasing Detection", yes_is_bad=True)
    fmt_requests += _detection_requests("Late Hello Detection", yes_is_bad=True)
    fmt_requests += _detection_requests("Rebuttal Detection", yes_is_bad=False)

    # 3. Status column: "Needs Training" = red bg white bold
    status_col = col_index["Status"]
    for row_i, r in enumerate(rows, start=1):
        val = str(r.get("Status", "")).strip()
        if val == "Needs Training":
            fmt_requests.append({
                "repeatCell": {
                    "range": {"sheetId": 0,
                              "startRowIndex": row_i, "endRowIndex": row_i + 1,
                              "startColumnIndex": status_col, "endColumnIndex": status_col + 1},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": _STATUS_RED,
                            "textFormat": {"foregroundColor": _STATUS_FG, "bold": True},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            })

    if fmt_requests:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": fmt_requests},
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


def style_report_doc(docs, doc_id: str, sheet_url: str, sheet_name: str) -> None:
    """
    Post-process the copied Doc:
    - Bold all paragraph text
    - Replace raw {{sheet_url}} link text with a named hyperlink chip
    - Style header rows (dark green bg, white bold) and data rows (cream bg)
    """
    doc = docs.documents().get(documentId=doc_id).execute()
    content = doc.get("body", {}).get("content", [])

    requests = []

    # Palette
    header_bg = {"red": 32/255, "green": 73/255, "blue": 37/255}
    header_fg = {"red": 1.0,    "green": 1.0,    "blue": 1.0}
    cream_bg  = {"red": 255/255,"green": 255/255, "blue": 204/255}

    # Keywords that mark a header/section row in the Doc
    _HEADER_KEYWORDS = {
        "auditing feedback", "issue rating", "action needed",
        "action points", "campaign summary", "ratios",
    }

    for element in content:
        para = element.get("paragraph")
        if not para:
            continue

        start = element.get("startIndex", 0)
        end   = element.get("endIndex", 0)
        # end - 1 is the content range (excludes trailing newline);
        # skip if that range would be empty (blank / newline-only paragraphs)
        if end - 1 <= start:
            continue

        # Collect plain text of paragraph
        para_text = "".join(
            e.get("textRun", {}).get("content", "")
            for e in para.get("elements", [])
        ).strip().lower()

        is_header = any(kw in para_text for kw in _HEADER_KEYWORDS)

        # Bold entire paragraph
        requests.append({
            "updateTextStyle": {
                "range": {"startIndex": start, "endIndex": end - 1},
                "textStyle": {"bold": True, "fontSize": {"magnitude": 11, "unit": "PT"}},
                "fields": "bold,fontSize",
            }
        })

        # Color paragraph background
        bg = header_bg if is_header else cream_bg
        fg = header_fg if is_header else {"red": 0.0, "green": 0.0, "blue": 0.0}
        requests.append({
            "updateParagraphStyle": {
                "range": {"startIndex": start, "endIndex": end - 1},
                "paragraphStyle": {"shading": {"backgroundColor": {"color": {"rgbColor": bg}}}},
                "fields": "shading",
            }
        })
        if is_header:
            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": start, "endIndex": end - 1},
                    "textStyle": {"foregroundColor": {"color": {"rgbColor": fg}}},
                    "fields": "foregroundColor",
                }
            })

    if requests:
        docs.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests},
        ).execute()

    # --- Chip replacement: separate pass so index shifts don't corrupt the batch ---
    # Re-fetch doc to get post-styling indices
    doc2 = docs.documents().get(documentId=doc_id).execute()
    content2 = doc2.get("body", {}).get("content", [])

    chip_requests = []
    for element in content2:
        para = element.get("paragraph")
        if not para:
            continue
        for el in para.get("elements", []):
            tr = el.get("textRun", {})
            content_text = tr.get("content", "")
            if sheet_url in content_text:
                el_start = el.get("startIndex", 0)
                el_end   = el.get("endIndex", 0)
                chip_requests.append({
                    "deleteContentRange": {
                        "range": {"startIndex": el_start, "endIndex": el_end}
                    }
                })
                chip_requests.append({
                    "insertText": {
                        "location": {"index": el_start},
                        "text": sheet_name,
                    }
                })
                chip_requests.append({
                    "updateTextStyle": {
                        "range": {"startIndex": el_start, "endIndex": el_start + len(sheet_name)},
                        "textStyle": {
                            "bold": True,
                            "link": {"url": sheet_url},
                            "foregroundColor": {"color": {"rgbColor": {"red": 0.07, "green": 0.36, "blue": 0.78}}},
                            "fontSize": {"magnitude": 11, "unit": "PT"},
                        },
                        "fields": "bold,link,foregroundColor,fontSize",
                    }
                })
                break  # only one URL per doc
        if chip_requests:
            break

    if chip_requests:
        docs.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": chip_requests},
        ).execute()
