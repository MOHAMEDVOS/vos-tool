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
_SUMMARY_SUBHEADER = _rgb(100, 130, 100)  # mid-green for agent name rows


# Issue columns: (column key in row dict, human-readable issue label, count_no=True means count "No" as the problem)
_ISSUE_COLS = [
    ("Agent Intro",          "Agent Intro (skipped intro)",           True),   # No = bad
    ("Owner Name",           "Owner Name (not confirmed)",            True),   # No = bad
    ("Reason For Calling",   "Reason for Calling (address skipped)",  True),   # No = bad
    ("Late Hello Detection", "Late Hello Detection",                  False),  # Yes = bad
    ("Releasing Detection",  "Releasing Detection",                   False),  # Yes = bad
]


def _build_agent_issues_summary(rows: List[Dict[str, Any]]) -> List[Tuple[str, str, int, int]]:
    """
    Count flagged answers per agent per issue column.
    For Agent Intro / Owner Name / Reason For Calling: count rows where value == "No".
    For Late Hello Detection / Releasing Detection: count rows where value == "Yes".
    Returns list of (agent_name, issue_label, issue_count, agent_total_calls)
    sorted by agent then issue, only where issue_count >= 10.
    """
    from collections import defaultdict
    counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    totals: Dict[str, int] = defaultdict(int)

    for r in rows:
        agent = str(r.get("Agent Name", "")).strip()
        if not agent:
            continue
        totals[agent] += 1
        for col_key, label, count_no in _ISSUE_COLS:
            val = r.get(col_key)
            if col_key == "Reason For Calling" and not val:
                val = r.get("Reason for calling") or r.get("Reason for Calling")
            val = str(val or "").strip()
            
            if count_no and val == "No":
                counts[agent][label] += 1
            elif not count_no and val == "Yes":
                counts[agent][label] += 1

    result = []
    for agent in sorted(counts.keys()):
        for _, label, _ in _ISSUE_COLS:
            c = counts[agent].get(label, 0)
            if c >= 10:
                result.append((agent, label, c, totals[agent]))
    return result


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
    
    data = []
    for r in rows:
        row_data = []
        for col in columns:
            if col == "Reason For Calling":
                val = r.get("Reason For Calling") or r.get("Reason for calling") or r.get("Reason for Calling") or ""
            else:
                val = r.get(col, "")
            row_data.append(str(val))
        data.append(row_data)

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

    # 4. Clip text (no wrap) for all data cells so transcription doesn't expand rows
    fmt_requests.append({
        "repeatCell": {
            "range": {"sheetId": 0, "startRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": len(columns)},
            "cell": {"userEnteredFormat": {"wrapStrategy": "CLIP"}},
            "fields": "userEnteredFormat.wrapStrategy",
        }
    })

    # 5. Set Transcription column width to 200px, others to auto-fit via pixelSize
    transcription_col = col_index["Transcription"]
    fmt_requests.append({
        "updateDimensionProperties": {
            "range": {"sheetId": 0, "dimension": "COLUMNS",
                      "startIndex": transcription_col, "endIndex": transcription_col + 1},
            "properties": {"pixelSize": 200},
            "fields": "pixelSize",
        }
    })

    if fmt_requests:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": fmt_requests},
        ).execute()

    # ── Sheet 2: Agent Issues Summary ────────────────────────────────────────
    summary_rows = _build_agent_issues_summary(rows)
    if summary_rows:
        _add_summary_sheet(sheets, sheet_id, summary_rows)

    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    return sheet_id, sheet_url


def create_scoring_spreadsheet(
    drive,
    sheets,
    name: str,
    rows: List[Dict[str, Any]],
    folder_id: str,
) -> Tuple[str, str]:
    """Create a Google Sheet for the Scoring section (one row per sampled number).

    ``rows`` are the objects returned by ``lib.scoring_sampler.score_agents`` — each has
    ``agent``, ``phones`` (``[{phone, flags}]``), ``note``, ``red_flag``. The agent name repeats
    on each of its number rows; ``Note`` / ``Red Flag`` show only on the agent's first row.
    Returns ``(sheet_id, sheet_url)``.
    """
    columns = ["Agent name", "Phone", "Flag", "Note", "Red Flag"]
    FLAG_I, REDFLAG_I = 2, 4

    data: List[List[str]] = []
    flag_cells: List[int] = []      # data-row indexes (0-based within data) that carry a flag
    redflag_cells: List[int] = []   # data-row indexes whose Red Flag == Yes
    for r in rows:
        phones = r.get("phones") or [None]
        first = True
        for p in phones:
            phone = (p or {}).get("phone", "") if p else ""
            flags = (p or {}).get("flags", []) if p else []
            flag_txt = ", ".join(flags)
            data.append([
                r.get("agent", ""),
                phone,
                flag_txt,
                r.get("note", "") if first else "",
                ("Yes" if r.get("red_flag") else "No") if first else "",
            ])
            if flag_txt:
                flag_cells.append(len(data) - 1)
            if first and r.get("red_flag"):
                redflag_cells.append(len(data) - 1)
            first = False

    body = {
        "name": f"{name} – scoring",
        "mimeType": "application/vnd.google-apps.spreadsheet",
        "parents": [folder_id],
    }
    spreadsheet = drive.files().create(body=body, supportsAllDrives=True).execute()
    sheet_id = spreadsheet["id"]

    sheets.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range="Sheet1!A1",
        valueInputOption="RAW",
        body={"values": [columns] + data},
    ).execute()

    fmt_requests = [
        {  # header row: dark green, white bold, frozen
            "repeatCell": {
                "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1,
                          "startColumnIndex": 0, "endColumnIndex": len(columns)},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {"foregroundColor": _HEADER_FG, "bold": True},
                    "horizontalAlignment": "CENTER",
                }},
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        },
        {"updateSheetProperties": {
            "properties": {"sheetId": 0, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount",
        }},
    ]

    def _red_cell(row_i: int, col_i: int):
        return {"repeatCell": {
            "range": {"sheetId": 0, "startRowIndex": row_i + 1, "endRowIndex": row_i + 2,
                      "startColumnIndex": col_i, "endColumnIndex": col_i + 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": _RED_BG,
                "textFormat": {"foregroundColor": _DETECT_FG, "bold": True},
            }},
            "fields": "userEnteredFormat(backgroundColor,textFormat)",
        }}

    fmt_requests += [_red_cell(i, FLAG_I) for i in flag_cells]
    fmt_requests += [_red_cell(i, REDFLAG_I) for i in redflag_cells]

    if fmt_requests:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id, body={"requests": fmt_requests}
        ).execute()

    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    return sheet_id, sheet_url


def append_scoring_rows(sheets, spreadsheet_id: str, tab_name: str, score_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Append one row per agent to an auditor tab of the company "Auditors-Scoring MOP" sheet.

    The sheet is built on ARRAYFORMULAs anchored at row 3 (verified live): cols A(Date),
    B(RES-ID), E(TL Name), F(Assigned Auditor), S(Performance Index%) auto-fill off Agent Name
    (col C) — we MUST NOT write them. We write only C,D and G:R (two contiguous blocks that skip
    the formula columns). Only two scoring columns are VOS-driven; the rest are fixed defaults:
      I "Did the homeowner have to say hello first?"  = Yes if agent late-hello-flagged else No
      M "Agent's sound is low?"                       = Yes if agent releasing-flagged else No

    A runtime header guard refuses to write if the template's columns ever move, so a layout
    change can never drop a value into the wrong scoring cell. Returns a small status dict.
    """
    meta = sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet = next((s for s in meta["sheets"]
                  if s["properties"]["title"].strip().lower() == tab_name.strip().lower()), None)
    if not sheet:
        raise ValueError(f"Tab {tab_name!r} not found in the scoring sheet")
    title = sheet["properties"]["title"]
    gid = sheet["properties"]["sheetId"]

    # Header guard: combine header rows 1+2 per column and assert the columns are where we expect.
    hdr = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"'{title}'!A1:T2").execute().get("values", [])

    def htext(col: int) -> str:
        return " ".join(str(r[col]) for r in hdr if col < len(r)).lower()

    def guard(col: int, *needles: str):
        h = htext(col)
        if not all(n in h for n in needles):
            raise ValueError(
                f"Scoring sheet layout changed (tab {title!r}, col index {col} = {h!r}); "
                f"expected to contain {needles}. Aborting to avoid writing to the wrong column."
            )

    guard(2, "agent")                 # C Agent Name
    guard(3, "phone")                 # D Phone Number
    guard(6, "dialer")                # G Dialer Name
    guard(8, "homeowner", "hello")    # I Late Hello
    guard(12, "sound", "low")         # M Releasing

    # Append point = first empty row in col C (data starts at row 3).
    col_c = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"'{title}'!C3:C").execute().get("values", [])
    start = 3 + len(col_c)

    cd_block, gr_block = [], []
    for r in score_rows:
        # phones stacked one-per-line inside the single Phone Number cell (newline = in-cell break)
        phones = "\n".join(p.get("phone", "") for p in (r.get("phones") or []) if p.get("phone"))
        flags = set(r.get("flag_types") or [])
        late = "Yes" if "Late Hello" in flags else "No"
        rel = "Yes" if "Releasing" in flags else "No"
        dialer = str(r.get("dialer") or "").upper()
        cd_block.append([r.get("agent", ""), phones])
        # G  H    I     J     K     L     M    N     O        P     Q   R
        gr_block.append([dialer, "OH", late, "Yes", "Yes", "Yes", rel, "No", "Active", "No", "", ""])

    end = start + len(score_rows) - 1
    sheets.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"valueInputOption": "RAW", "data": [
            {"range": f"'{title}'!C{start}:D{end}", "values": cd_block},
            {"range": f"'{title}'!G{start}:R{end}", "values": gr_block},
        ]},
    ).execute()

    # Wrap the Phone Number cells (col D, index 3) so the stacked numbers display one-per-line.
    sheets.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{
            "repeatCell": {
                "range": {"sheetId": gid, "startRowIndex": start - 1, "endRowIndex": end,
                          "startColumnIndex": 3, "endColumnIndex": 4},
                "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
                "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)",
            }
        }]},
    ).execute()

    sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit#gid={gid}"
    return {"tab": title, "rows_added": len(score_rows), "start_row": start, "sheet_url": sheet_url}


def _add_summary_sheet(sheets, spreadsheet_id: str, summary_rows: List[Tuple[str, str, int, int]]) -> None:
    """Add a second sheet tab 'Agent Issues Summary' with a grouped issue table."""

    # 1. Create the new sheet tab
    add_resp = sheets.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": "Agent Issues Summary"}}}]},
    ).execute()
    summary_gid = add_resp["replies"][0]["addSheet"]["properties"]["sheetId"]

    # 2. Build the values: header + grouped data rows
    header = [["Agent Name", "Issue Type", "Total Samples with Issue"]]
    values = []
    current_agent = None
    for agent, label, count, total in summary_rows:
        count_str = f"{count} out of {total}"
        if agent != current_agent:
            values.append([agent, label, count_str])
            current_agent = agent
        else:
            values.append(["", label, count_str])

    sheets.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="Agent Issues Summary!A1",
        valueInputOption="RAW",
        body={"values": header + values},
    ).execute()

    total_rows = len(values) + 1  # +1 for header

    fmt = []

    # Header row: dark green bg, white bold, frozen
    fmt.append({
        "repeatCell": {
            "range": {"sheetId": summary_gid, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": 3},
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
    fmt.append({"updateSheetProperties": {
        "properties": {"sheetId": summary_gid, "gridProperties": {"frozenRowCount": 1}},
        "fields": "gridProperties.frozenRowCount",
    }})

    # Data rows: colour agent-name cells mid-green + count column centre-aligned
    current_agent = None
    for row_i, (agent, label, count, total) in enumerate(summary_rows, start=1):
        if agent != current_agent:
            current_agent = agent
            fmt.append({
                "repeatCell": {
                    "range": {"sheetId": summary_gid,
                              "startRowIndex": row_i, "endRowIndex": row_i + 1,
                              "startColumnIndex": 0, "endColumnIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": _SUMMARY_SUBHEADER,
                            "textFormat": {"foregroundColor": _HEADER_FG, "bold": True},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            })

        # Count cell colour based on ratio (count / total)
        ratio = count / total if total else 0
        if ratio >= 0.5:
            count_bg = _RED_BG
            count_fg = _HEADER_FG
        elif ratio >= 0.25:
            count_bg = _rgb(230, 120, 0)
            count_fg = _HEADER_FG
        else:
            count_bg = _rgb(255, 214, 102)  # yellow-ish — still visible issue
            count_fg = _rgb(0, 0, 0)

        fmt.append({
            "repeatCell": {
                "range": {"sheetId": summary_gid,
                          "startRowIndex": row_i, "endRowIndex": row_i + 1,
                          "startColumnIndex": 2, "endColumnIndex": 3},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": count_bg,
                        "textFormat": {"foregroundColor": count_fg, "bold": True},
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        })

    # Auto-resize all 3 columns
    fmt.append({
        "autoResizeDimensions": {
            "dimensions": {"sheetId": summary_gid, "dimension": "COLUMNS",
                           "startIndex": 0, "endIndex": 3}
        }
    })

    sheets.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": fmt},
    ).execute()


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
            if "SHEET_LINK_PLACEHOLDER" in content_text:
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
