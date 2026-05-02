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

# ── colour constants (RGB 0-1) ──────────────────────────────────────────────
_DARK_GREEN  = {"red": 0.133, "green": 0.302, "blue": 0.173}   # #224B2C header bg
_MID_GREEN   = {"red": 0.416, "green": 0.537, "blue": 0.404}   # #6A8967 section rows
_LIGHT_CREAM = {"red": 0.980, "green": 0.976, "blue": 0.933}   # #FAF9EE row bg
_WHITE       = {"red": 1.0,   "green": 1.0,   "blue": 1.0}
_RED_BADGE   = {"red": 0.839, "green": 0.153, "blue": 0.153}   # Yes-bad
_GREEN_BADGE = {"red": 0.204, "green": 0.596, "blue": 0.231}   # No-good / Yes-good
_ORANGE      = {"red": 0.976, "green": 0.686, "blue": 0.184}   # Medium
_YELLOW      = {"red": 1.0,   "green": 0.949, "blue": 0.6}     # coaching Yes


def get_service_account_credentials() -> service_account.Credentials:
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
    drive.permissions().create(
        fileId=file_id,
        body={"type": "user", "role": "writer", "emailAddress": email},
        sendNotificationEmail=False,
        supportsAllDrives=True,
    ).execute()


def copy_template_doc(drive, template_id: str, new_name: str, folder_id: str) -> str:
    body = {"name": new_name, "parents": [folder_id]}
    result = drive.files().copy(fileId=template_id, body=body, supportsAllDrives=True).execute()
    return result["id"]


# ── Sheet helpers ────────────────────────────────────────────────────────────

def _rgb(c: Dict) -> Dict:
    return {"red": c["red"], "green": c["green"], "blue": c["blue"]}


def _cell_color_req(sheet_gid: int, row: int, col_start: int, col_end: int, bg: Dict, fg: Dict = None, bold: bool = False):
    fmt: Dict = {"backgroundColor": _rgb(bg)}
    if fg or bold:
        fmt["textFormat"] = {}
        if fg:
            fmt["textFormat"]["foregroundColor"] = _rgb(fg)
        if bold:
            fmt["textFormat"]["bold"] = True
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_gid,
                "startRowIndex": row,
                "endRowIndex": row + 1,
                "startColumnIndex": col_start,
                "endColumnIndex": col_end,
            },
            "cell": {"userEnteredFormat": fmt},
            "fields": "userEnteredFormat(backgroundColor,textFormat)",
        }
    }


def _detection_color_requests(sheet_gid: int, row_idx: int, col_idx: int, value: str, col_name: str) -> List[Dict]:
    """Return a color request for a single detection cell based on value."""
    v = str(value).strip()
    if col_name == "Releasing Detection":
        bg = _RED_BADGE if v == "Yes" else _GREEN_BADGE
    elif col_name == "Late Hello Detection":
        bg = _RED_BADGE if v == "Yes" else _GREEN_BADGE
    elif col_name == "Rebuttal Detection":
        bg = _GREEN_BADGE if v == "Yes" else (_RED_BADGE if v == "No" else _LIGHT_CREAM)
    elif col_name == "Status":
        bg = _RED_BADGE if v == "Needs Training" else _GREEN_BADGE if v == "Excellent" else _LIGHT_CREAM
    else:
        return []
    return [_cell_color_req(sheet_gid, row_idx, col_idx, col_idx + 1, bg, _WHITE, bold=True)]


def create_spreadsheet(
    drive,
    sheets,
    name: str,
    rows: List[Dict[str, Any]],
    folder_id: str,
) -> Tuple[str, str]:
    """Create a formatted Google Sheet. Returns (sheet_id, sheet_url)."""
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
        "parents": [folder_id],
    }
    spreadsheet = drive.files().create(body=body, supportsAllDrives=True).execute()
    sheet_id = spreadsheet["id"]

    # Write values
    sheets.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range="Sheet1!A1",
        valueInputOption="RAW",
        body={"values": header + data},
    ).execute()

    # Get the real sheetId (tab gid) — not the spreadsheet file id
    meta = sheets.spreadsheets().get(spreadsheetId=sheet_id).execute()
    sheet_gid = meta["sheets"][0]["properties"]["sheetId"]
    num_cols = len(columns)

    fmt_requests = []

    # Header row: dark green bg, white bold
    fmt_requests.append(_cell_color_req(sheet_gid, 0, 0, num_cols, _DARK_GREEN, _WHITE, bold=True))

    # Freeze header row
    fmt_requests.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_gid,
                "gridProperties": {"frozenRowCount": 1},
            },
            "fields": "gridProperties.frozenRowCount",
        }
    })

    # Auto-resize all columns
    fmt_requests.append({
        "autoResizeDimensions": {
            "dimensions": {
                "sheetId": sheet_gid,
                "dimension": "COLUMNS",
                "startIndex": 0,
                "endIndex": num_cols,
            }
        }
    })

    # Detection & Status cell colours per data row
    detection_cols = {
        "Releasing Detection", "Late Hello Detection", "Rebuttal Detection", "Status"
    }
    for row_i, row_data in enumerate(rows):
        bg = _LIGHT_CREAM if row_i % 2 == 0 else _WHITE
        # Alternating row bg for non-detection cells
        fmt_requests.append(_cell_color_req(sheet_gid, row_i + 1, 0, num_cols, bg))
        for col_j, col_name in enumerate(columns):
            if col_name in detection_cols:
                val = row_data.get(col_name, "")
                fmt_requests += _detection_color_requests(sheet_gid, row_i + 1, col_j, val, col_name)

    sheets.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": fmt_requests},
    ).execute()

    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    return sheet_id, sheet_url


# ── Doc helpers ──────────────────────────────────────────────────────────────

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


def _pt(pt: float) -> int:
    """Convert points to Docs API unit (1/100 pt)."""
    return int(pt * 100)


def _color(r: float, g: float, b: float) -> Dict:
    return {"color": {"rgbColor": {"red": r, "green": g, "blue": b}}}


def create_campaign_doc(
    drive,
    docs,
    folder_id: str,
    doc_name: str,
    mapping: Dict[str, str],
) -> str:
    """
    Build a Campaign Performance Report Doc from scratch that matches
    the branded template layout. Returns the new doc_id.
    """
    # Create blank doc via Drive
    file_meta = {
        "name": doc_name,
        "mimeType": "application/vnd.google-apps.document",
        "parents": [folder_id],
    }
    file_resp = drive.files().create(body=file_meta, supportsAllDrives=True).execute()
    doc_id = file_resp["id"]

    m = mapping  # shorthand

    def _yes_no_color(val: str) -> Tuple[float, float, float]:
        v = str(val).strip()
        if v == "Yes":
            return (0.839, 0.153, 0.153)
        if v == "No":
            return (0.204, 0.596, 0.231)
        return (0.5, 0.5, 0.5)

    def _rating_color(val: str) -> Tuple[float, float, float]:
        v = str(val).strip()
        if v == "High":
            return (0.839, 0.153, 0.153)
        if v == "Medium":
            return (0.976, 0.686, 0.184)
        return (0.204, 0.596, 0.231)

    # We'll build the document content as a sequence of paragraphs using
    # batchUpdate insertText + formatting. Simpler: use a table structure.

    requests: List[Dict] = []

    # ── 1. Title ─────────────────────────────────────────────────────────────
    # Insert title text at end of doc (index 1 = after empty paragraph)
    title_text = "Campaign Performance Report\n"
    requests.append({"insertText": {"location": {"index": 1}, "text": title_text}})

    # ── 2. Build the main content table (rows) ────────────────────────────────
    # We insert a table with 4 columns, then fill + format cells.
    # Rows: header | campaign+dialer | date | issues x4 | action points header |
    #        coaching | allocation | campaign list | summary

    table_rows = 13  # header + 2 meta + 5 issue rows + action header + 3 action rows + summary
    table_cols = 4

    # Insert table after title paragraph (index = len(title_text) + 1)
    title_end = len(title_text) + 1
    requests.append({
        "insertTable": {
            "rows": table_rows,
            "columns": table_cols,
            "location": {"index": title_end},
        }
    })

    # batchUpdate to create the doc structure first, then format
    docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests},
    ).execute()

    # Re-fetch doc to get actual table cell indices
    doc = docs.documents().get(documentId=doc_id).execute()

    # Find the table element
    table_elem = None
    for elem in doc.get("body", {}).get("content", []):
        if "table" in elem:
            table_elem = elem["table"]
            break

    if not table_elem:
        logger.warning("Table not found in created doc — skipping formatting")
        return doc_id

    fmt_requests: List[Dict] = []

    # Helper to get cell start index
    def cell_start(r_idx: int, c_idx: int) -> int:
        return table_elem["tableRows"][r_idx]["tableCells"][c_idx]["content"][0]["startIndex"]

    def set_cell_text(r_idx: int, c_idx: int, text: str) -> int:
        idx = cell_start(r_idx, c_idx)
        fmt_requests.append({"insertText": {"location": {"index": idx}, "text": text}})
        return idx

    def set_cell_bg(r_idx: int, c_idx: int, r: float, g: float, b: float):
        cell = table_elem["tableRows"][r_idx]["tableCells"][c_idx]
        fmt_requests.append({
            "updateTableCellStyle": {
                "tableRange": {
                    "tableCellLocation": {
                        "tableStartLocation": {"index": table_elem["startIndex"]},
                        "rowIndex": r_idx,
                        "columnIndex": c_idx,
                    },
                    "rowSpan": 1,
                    "columnSpan": 1,
                },
                "tableCellStyle": {
                    "backgroundColor": {"color": {"rgbColor": {"red": r, "green": g, "blue": b}}}
                },
                "fields": "backgroundColor",
            }
        })

    def format_text_in_cell(r_idx: int, c_idx: int, text: str,
                             bold: bool = False,
                             fg_rgb: Tuple = None,
                             bg_cell_rgb: Tuple = None,
                             font_size: int = 10):
        idx = cell_start(r_idx, c_idx)
        fmt_requests.append({"insertText": {"location": {"index": idx}, "text": text}})
        end_idx = idx + len(text)
        tf: Dict = {"bold": bold, "fontSize": {"magnitude": font_size, "unit": "PT"}}
        if fg_rgb:
            tf["foregroundColor"] = {"color": {"rgbColor": {"red": fg_rgb[0], "green": fg_rgb[1], "blue": fg_rgb[2]}}}
        fmt_requests.append({
            "updateTextStyle": {
                "range": {"startIndex": idx, "endIndex": end_idx},
                "textStyle": tf,
                "fields": "bold,fontSize,foregroundColor",
            }
        })
        if bg_cell_rgb:
            set_cell_bg(r_idx, c_idx, *bg_cell_rgb)

    # ── Row 0: main header ───────────────────────────────────────────────────
    # Merge handled by text — just set content + dark green bg for cols 0-3
    header_cells = ["Campaign Performance Report", "", "", ""]
    for ci, txt in enumerate(header_cells):
        format_text_in_cell(0, ci, txt, bold=True, fg_rgb=(1, 1, 1), bg_cell_rgb=(0.133, 0.302, 0.173), font_size=13)

    # ── Row 1: Campaign + dialer info ────────────────────────────────────────
    campaign_label = f'Campaign: "{m.get("{{campaign_name}}", "")}"'
    dialer_label   = f'DIALER: {m.get("{{dialer}}", "")}'
    format_text_in_cell(1, 0, campaign_label, bold=True, bg_cell_rgb=(0.133, 0.302, 0.173), fg_rgb=(1, 1, 1))
    format_text_in_cell(1, 1, "Auditing feedback", bold=True, bg_cell_rgb=(0.133, 0.302, 0.173), fg_rgb=(1, 1, 1))
    format_text_in_cell(1, 2, "Issue Rating", bold=True, bg_cell_rgb=(0.133, 0.302, 0.173), fg_rgb=(1, 1, 1))
    format_text_in_cell(1, 3, "Action needed / Notes", bold=True, bg_cell_rgb=(0.133, 0.302, 0.173), fg_rgb=(1, 1, 1))

    # ── Row 2: Auditing duration date ────────────────────────────────────────
    date_from = m.get("{{date_from}}", "")
    date_to   = m.get("{{date_to}}", "")
    format_text_in_cell(2, 0, "Auditing duration date", bold=True, bg_cell_rgb=(0.416, 0.537, 0.404), fg_rgb=(1, 1, 1))
    format_text_in_cell(2, 1, f"From {date_from}  To  {date_to}", bg_cell_rgb=(0.98, 0.976, 0.933))
    format_text_in_cell(2, 2, "", bg_cell_rgb=(0.98, 0.976, 0.933))
    format_text_in_cell(2, 3, "", bg_cell_rgb=(0.98, 0.976, 0.933))

    # ── Issue rows 3-6 ────────────────────────────────────────────────────────
    issue_rows = [
        ("Effort Issue from Agents",  m.get("{{effort_feedback}}", "N/A"),   "N/A"),
        ("Rebuttals issue",           m.get("{{rebuttals_feedback}}", "N/A"), m.get("{{rebuttals_rating}}", "N/A")),
        ("Releasing issue",           m.get("{{releasing_feedback}}", "N/A"), m.get("{{releasing_rating}}", "N/A")),
        ("Active Tonality issue",     m.get("{{tonality_feedback}}", "N/A"),  "N/A"),
    ]
    for ri, (label, feedback, rating) in enumerate(issue_rows, start=3):
        format_text_in_cell(ri, 0, label, bold=True, bg_cell_rgb=(0.416, 0.537, 0.404), fg_rgb=(1, 1, 1))
        fb_rgb = _yes_no_color(feedback)
        format_text_in_cell(ri, 1, feedback, bold=True, fg_rgb=fb_rgb, bg_cell_rgb=(0.98, 0.976, 0.933))
        rt_rgb = _rating_color(rating)
        format_text_in_cell(ri, 2, rating, bold=True, fg_rgb=rt_rgb, bg_cell_rgb=(0.98, 0.976, 0.933))
        format_text_in_cell(ri, 3, "", bg_cell_rgb=(0.98, 0.976, 0.933))

    # ── Row 7: Action Points header ───────────────────────────────────────────
    for ci in range(4):
        txt = "Action Points" if ci == 0 else ""
        format_text_in_cell(7, ci, txt, bold=True, fg_rgb=(1, 1, 1), bg_cell_rgb=(0.133, 0.302, 0.173), font_size=12)

    # ── Action rows 8-10 ─────────────────────────────────────────────────────
    coaching_fb = m.get("{{coaching_feedback}}", "N/A")
    allocation_fb = m.get("{{allocation_feedback}}", "N/A")
    campaign_list_fb = m.get("{{campaign_list_issue}}", "N/A")

    action_rows = [
        ("Agents needs Coaching",   coaching_fb,       "N/A",  'Specific Coaching: EX "Need to focus on active listening"'),
        ("Agents allocation issue:", allocation_fb,    "N/A",  "Action needed: Using Higher skilled agents"),
        ("Campaign List Issue:",    campaign_list_fb,  "",     m.get("{{campaign_list_summary}}", "")),
    ]
    for ri, (label, feedback, rating, notes) in enumerate(action_rows, start=8):
        format_text_in_cell(ri, 0, label, bold=True, bg_cell_rgb=(0.416, 0.537, 0.404), fg_rgb=(1, 1, 1))
        fb_rgb = _yes_no_color(feedback)
        format_text_in_cell(ri, 1, feedback, bold=True, fg_rgb=fb_rgb, bg_cell_rgb=(0.98, 0.976, 0.933))
        rt_rgb = _rating_color(rating) if rating else (0.5, 0.5, 0.5)
        format_text_in_cell(ri, 2, rating, bold=(rating != ""), fg_rgb=rt_rgb, bg_cell_rgb=(0.98, 0.976, 0.933))
        format_text_in_cell(ri, 3, notes, bg_cell_rgb=(0.98, 0.976, 0.933))

    # ── Row 11: dialer sub-row (second line under campaign) ──────────────────
    format_text_in_cell(11, 0, dialer_label, bold=True, bg_cell_rgb=(0.133, 0.302, 0.173), fg_rgb=(1, 1, 1))
    format_text_in_cell(11, 1, "", bg_cell_rgb=(0.133, 0.302, 0.173))
    format_text_in_cell(11, 2, "", bg_cell_rgb=(0.133, 0.302, 0.173))
    format_text_in_cell(11, 3, "", bg_cell_rgb=(0.133, 0.302, 0.173))

    # ── Row 12: Campaign Summary ──────────────────────────────────────────────
    summary_text = m.get("{{summary_ratios}}", "")
    issue_rating_legend = (
        "Issue Rating Ratio:\n"
        "1. Low: Less than 30%\n"
        "2. Medium: 30% to 50%\n"
        "3. High: Greater than 50%"
    )
    format_text_in_cell(12, 0, "Campaign Summary", bold=True, bg_cell_rgb=(0.416, 0.537, 0.404), fg_rgb=(1, 1, 1))
    format_text_in_cell(12, 1, f"Ratios:\n{summary_text}", bg_cell_rgb=(0.98, 0.976, 0.933))
    format_text_in_cell(12, 2, "", bg_cell_rgb=(0.98, 0.976, 0.933))
    format_text_in_cell(12, 3, issue_rating_legend, bg_cell_rgb=(0.98, 0.976, 0.933))

    # Apply all formatting
    if fmt_requests:
        docs.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": fmt_requests},
        ).execute()

    return doc_id
