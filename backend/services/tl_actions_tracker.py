"""Append missing TL actions to the shared tracking spreadsheet."""

from __future__ import annotations

import os
import unicodedata
from datetime import date, datetime
from typing import Any

from googleapiclient.errors import HttpError

from backend.services.tl_actions_reconciliation import _date_value, normalize_details
from lib.google_workspace import build_sheets, get_service_account_credentials

DEFAULT_TRACKER_SPREADSHEET_ID = "1TxjbS5PMEP5vmBX8I6VA5I5XY8QW6k2O6S6AzckGjyQ"


def _leader_key(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).split()).casefold()


def _action_key(action_day: Any, leader: Any, details: Any) -> tuple[str, str, str]:
    parsed_day = _date_value(action_day)
    date_key = parsed_day.isoformat() if parsed_day else str(action_day or "").strip()
    return date_key, _leader_key(leader), normalize_details(details).casefold()


def append_missing_actions(actions: list[dict[str, Any]]) -> dict[str, Any]:
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
        fields="sheets(properties(sheetId,title,index))",
    ).execute()
    sheet_properties = sorted(
        (sheet.get("properties", {}) for sheet in metadata.get("sheets", [])),
        key=lambda properties: properties.get("index", 0),
    )
    if not sheet_properties:
        raise ValueError("The tracker spreadsheet has no worksheet")

    title = str(sheet_properties[0].get("title", "Sheet1"))
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
    rows_to_append: list[list[str]] = []
    skipped_count = 0
    for action in actions:
        action_day = action["action_date"]
        if isinstance(action_day, (date, datetime)):
            parsed_day = action_day.date() if isinstance(action_day, datetime) else action_day
        else:
            parsed_day = date.fromisoformat(str(action_day))
        leader = str(action["team_leader"]).strip()
        details = str(action["details"]).strip()
        key = _action_key(parsed_day, leader, details)
        if key in existing:
            skipped_count += 1
            continue
        existing.add(key)
        rows_to_append.append([f"{parsed_day.month}/{parsed_day.day}/{parsed_day.year}", leader, details])

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

    return {
        "added_count": len(rows_to_append),
        "skipped_count": skipped_count,
        "updated_range": updated_range,
    }
