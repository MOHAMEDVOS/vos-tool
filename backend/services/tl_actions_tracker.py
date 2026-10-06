"""Append missing TL actions to the shared tracking spreadsheet."""

from __future__ import annotations

import os
import re
import unicodedata
from datetime import date, datetime
from typing import Any

from googleapiclient.errors import HttpError

from backend.services.tl_actions_reconciliation import _date_value, normalize_details
from lib.google_workspace import build_sheets, get_service_account_credentials

DEFAULT_TRACKER_SPREADSHEET_ID = "1TxjbS5PMEP5vmBX8I6VA5I5XY8QW6k2O6S6AzckGjyQ"
ACTION_FIELD_LABELS = (
    "Team Leader",
    "Agent Name",
    "Type of Issue",
    "Details about incident",
    "Reported by TL",
    "Action Given",
    "Deduction",
)


def _leader_key(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).split()).casefold()


def _action_key(action_day: Any, leader: Any, details: Any) -> tuple[str, str, str]:
    parsed_day = _date_value(action_day)
    date_key = parsed_day.isoformat() if parsed_day else str(action_day or "").strip()
    return date_key, _leader_key(leader), normalize_details(details).casefold()


def _date_serial(value: date) -> int:
    return (value - date(1899, 12, 30)).days


def _readable_details(value: Any) -> str:
    """Keep all action text while separating its fields and phone entries onto lines."""
    text = normalize_details(value)
    if not text:
        return ""
    labels = "|".join(re.escape(label) for label in ACTION_FIELD_LABELS)
    text = re.sub(
        rf"\s*\b({labels})\s*:\s*",
        lambda match: f"\n{match.group(1)}: ",
        text,
        flags=re.IGNORECASE,
    ).strip()
    return re.sub(r"\s+(?=\(\d{3}\)\s*\d{3}[-.\s]\d{4}\b)", "\n  ", text)


def _format_tracker_sheet(sheets: Any, spreadsheet_id: str, sheet_id: int, row_count: int, sheet_row_count: int, banded_ranges: list[dict[str, Any]]) -> None:
    """Apply a simple, readable table style to the whole tracker worksheet."""
    requests: list[dict[str, Any]] = []
    for banded_range in banded_ranges:
        banded_range_id = banded_range.get("bandedRangeId")
        if banded_range_id is not None:
            requests.append({"deleteBanding": {"bandedRangeId": banded_range_id}})

    requests.extend([
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                "properties": {"pixelSize": 115},
                "fields": "pixelSize",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2},
                "properties": {"pixelSize": 240},
                "fields": "pixelSize",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 3},
                "properties": {"pixelSize": 620},
                "fields": "pixelSize",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 3, "endIndex": 4},
                "properties": {"pixelSize": 36},
                "fields": "pixelSize",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 4, "endIndex": 5},
                "properties": {"pixelSize": 65},
                "fields": "pixelSize",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 5, "endIndex": 6},
                "properties": {"pixelSize": 270},
                "fields": "pixelSize",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 6, "endIndex": 7},
                "properties": {"pixelSize": 150},
                "fields": "pixelSize",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 3},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.12, "green": 0.27, "blue": 0.42},
                        "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True, "fontSize": 11},
                        "verticalAlignment": "MIDDLE",
                        "horizontalAlignment": "LEFT",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment,horizontalAlignment)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": max(row_count, 2), "startColumnIndex": 0, "endColumnIndex": 3},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 1, "green": 1, "blue": 1},
                        "textFormat": {"foregroundColor": {"red": 0.16, "green": 0.20, "blue": 0.25}, "bold": False, "fontSize": 10},
                        "verticalAlignment": "TOP",
                        "horizontalAlignment": "LEFT",
                        "wrapStrategy": "WRAP",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment,horizontalAlignment,wrapStrategy)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 4, "endColumnIndex": 7},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.12, "green": 0.27, "blue": 0.42},
                        "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True, "fontSize": 11},
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 4, "startColumnIndex": 4, "endColumnIndex": 6},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.92, "green": 0.96, "blue": 0.99},
                        "textFormat": {"foregroundColor": {"red": 0.16, "green": 0.20, "blue": 0.25}, "fontSize": 10},
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 3, "startColumnIndex": 5, "endColumnIndex": 6},
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {"type": "DATE", "pattern": "M/d/yyyy"},
                        "textFormat": {"foregroundColor": {"red": 0.12, "green": 0.27, "blue": 0.42}, "bold": True, "fontSize": 10},
                    }
                },
                "fields": "userEnteredFormat(numberFormat,textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 3, "endRowIndex": 4, "startColumnIndex": 5, "endColumnIndex": 6},
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"foregroundColor": {"red": 0.12, "green": 0.27, "blue": 0.42}, "bold": True, "fontSize": 12},
                    }
                },
                "fields": "userEnteredFormat(textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 5, "endRowIndex": 6, "startColumnIndex": 4, "endColumnIndex": 7},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.22, "green": 0.43, "blue": 0.61},
                        "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True, "fontSize": 10},
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 6, "endRowIndex": max(sheet_row_count, row_count, 7), "startColumnIndex": 4, "endColumnIndex": 7},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 1, "green": 1, "blue": 1},
                        "textFormat": {"foregroundColor": {"red": 0.16, "green": 0.20, "blue": 0.25}, "fontSize": 10},
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment)",
            }
        },
        {
            "addBanding": {
                "bandedRange": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 5, "endRowIndex": max(sheet_row_count, row_count, 7), "startColumnIndex": 4, "endColumnIndex": 7},
                    "rowProperties": {
                        "headerColor": {"red": 0.22, "green": 0.43, "blue": 0.61},
                        "firstBandColor": {"red": 1, "green": 1, "blue": 1},
                        "secondBandColor": {"red": 0.94, "green": 0.97, "blue": 0.99},
                    },
                }
            }
        },
        {
            "addBanding": {
                "bandedRange": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": max(sheet_row_count, row_count, 2), "startColumnIndex": 0, "endColumnIndex": 3},
                    "rowProperties": {
                        "headerColor": {"red": 0.12, "green": 0.27, "blue": 0.42},
                        "firstBandColor": {"red": 1, "green": 1, "blue": 1},
                        "secondBandColor": {"red": 0.94, "green": 0.97, "blue": 0.99},
                    },
                }
            }
        },
        {
            "setBasicFilter": {
                "filter": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": max(row_count, 1), "startColumnIndex": 0, "endColumnIndex": 3}}
            }
        },
        {
            "setDataValidation": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 3, "startColumnIndex": 5, "endColumnIndex": 6},
                "rule": {"condition": {"type": "DATE_IS_VALID"}, "strict": True, "showCustomUi": True},
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": max(row_count, 2), "startColumnIndex": 0, "endColumnIndex": 1},
                "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "M/d/yyyy"}}},
                "fields": "userEnteredFormat.numberFormat",
            }
        },
    ])
    if row_count > 1:
        requests.append({
            "autoResizeDimensions": {
                "dimensions": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 1, "endIndex": row_count}
            }
        })
    sheets.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()


def _update_report(sheets: Any, spreadsheet_id: str, title: str, start_date: date, end_date: date) -> None:
    escaped_title = title.replace("'", "''")
    prefix = f"'{escaped_title}'!"
    query_formula = (
        '=IFERROR(QUERY(FILTER({$B$2:$B,$A$2:$A},$A$2:$A>=$F$2,$A$2:$A<=$F$3,$B$2:$B<>""),'
        '"select Col1,count(Col1) group by Col1 order by count(Col1) desc label Col1 \'\',count(Col1) \'\'",0),"")'
    )
    sheets.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "valueInputOption": "USER_ENTERED",
            "data": [
                {"range": f"{prefix}E1:G1", "values": [["Missing actions by team leader", "", ""]]},
                {"range": f"{prefix}E2:F4", "values": [["From", _date_serial(start_date)], ["To", _date_serial(end_date)], ["Total missing actions", "=SUM(G7:G)"]]},
                {"range": f"{prefix}E6:G6", "values": [["Rank", "Team leader", "Missing actions"]]},
                {"range": f"{prefix}E7", "values": [["=ARRAYFORMULA(IF(F7:F=\"\",\"\",ROW(F7:F)-6))"]]},
                {"range": f"{prefix}F7", "values": [[query_formula]]},
            ],
        },
    ).execute()


def append_missing_actions(actions: list[dict[str, Any]], report_start_date: date, report_end_date: date) -> dict[str, Any]:
    """Append rows not already in the tracker; never overwrite existing rows."""
    if not os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
        raise ValueError(
            "Configure GOOGLE_SERVICE_ACCOUNT_JSON in the backend and share the tracker with that service account as Editor."
        )

    credentials = get_service_account_credentials()
    sheets = build_sheets(credentials)
    spreadsheet_id = os.getenv("TL_ACTIONS_TRACKER_SPREADSHEET_ID", DEFAULT_TRACKER_SPREADSHEET_ID)
    metadata = sheets.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId,title,index,gridProperties(rowCount)),bandedRanges(bandedRangeId))",
    ).execute()
    sheet_properties = sorted(
        (sheet.get("properties", {}) for sheet in metadata.get("sheets", [])),
        key=lambda properties: properties.get("index", 0),
    )
    if not sheet_properties:
        raise ValueError("The tracker spreadsheet has no worksheet")

    selected_sheet = sheet_properties[0]
    title = str(selected_sheet.get("title", "Sheet1"))
    sheet_id = int(selected_sheet.get("sheetId", 0))
    sheet_row_count = int(selected_sheet.get("gridProperties", {}).get("rowCount", 1000))
    banded_ranges = selected_sheet.get("bandedRanges", [])
    escaped_title = title.replace("'", "''")
    values = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{escaped_title}'!A:C",
        valueRenderOption="FORMATTED_VALUE",
    ).execute().get("values", [])
    expected_headers = ("date", "teamleader", "actiontemp")
    actual_headers = tuple(
        "".join(character for character in str(cell).casefold() if character.isalnum())
        for cell in (values[0] if values else [])[:3]
    )
    if actual_headers != expected_headers:
        raise ValueError("Tracker headers must be Date, Teamleader, Action temp in columns A–C")

    existing = {
        _action_key(row[0] if len(row) > 0 else "", row[1] if len(row) > 1 else "", row[2] if len(row) > 2 else "")
        for row in values[1:]
        if any(str(cell).strip() for cell in row)
    }
    rows_to_append: list[list[Any]] = []
    skipped_count = 0
    for action in actions:
        action_day = action["action_date"]
        if isinstance(action_day, (date, datetime)):
            parsed_day = action_day.date() if isinstance(action_day, datetime) else action_day
        else:
            parsed_day = date.fromisoformat(str(action_day))
        leader = str(action["team_leader"]).strip()
        details = _readable_details(action["details"])
        key = _action_key(parsed_day, leader, details)
        if key in existing:
            skipped_count += 1
            continue
        existing.add(key)
        rows_to_append.append([_date_serial(parsed_day), leader, details])

    if rows_to_append:
        try:
            response = sheets.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"'{escaped_title}'!A:C",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": rows_to_append},
            ).execute()
        except HttpError as exc:
            if exc.resp.status == 403:
                raise ValueError("Share the tracker spreadsheet with the backend service account as Editor") from exc
            raise
        updated_range = response.get("updates", {}).get("updatedRange")
    else:
        updated_range = None

    # Reformat old rows too, so the existing tracker is cleaned up on the next button click.
    formatted_dates = [[_date_serial(day) if (day := _date_value(row[0] if row else "")) else ""] for row in values[1:]]
    formatted_details = [[_readable_details(row[2] if len(row) > 2 else "")] for row in values[1:]]
    if formatted_dates:
        sheets.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "valueInputOption": "RAW",
                "data": [
                    {"range": f"'{escaped_title}'!A2:A{len(values)}", "values": formatted_dates},
                    {"range": f"'{escaped_title}'!C2:C{len(values)}", "values": formatted_details},
                ],
            },
        ).execute()

    total_rows = len(values) + len(rows_to_append)
    _update_report(sheets, spreadsheet_id, title, report_start_date, report_end_date)
    _format_tracker_sheet(
        sheets,
        spreadsheet_id,
        sheet_id,
        total_rows,
        sheet_row_count,
        banded_ranges,
    )

    return {
        "added_count": len(rows_to_append),
        "skipped_count": skipped_count,
        "updated_range": updated_range,
    }
