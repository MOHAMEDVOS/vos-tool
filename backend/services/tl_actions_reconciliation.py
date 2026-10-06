"""Read-only reconciliation between the TL Actions sheet and Payroll actions."""

from __future__ import annotations

import html
import csv
import io
import os
import re
import unicodedata
from collections import defaultdict, deque
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Any

import requests

from lib.google_workspace import build_sheets, get_service_account_credentials

PAYROLL_API = "https://payroll-backend-prod.azurewebsites.net"
SPREADSHEET_ID = "1x_pcfm0_NMpfAYLIOHStTKwgA94k9chcrZbJyx1gJII"
SHEET_NAME = "Actions"
WAIVER_SPREADSHEET_ID = "1zlyYv5srp_mjEFlADeMOPLbF7u3shWjtzXSwqbuCwYI"
WAIVER_SHEET_NAME = "Audit Reply"
PAGE_SIZE = 100


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"br", "p", "div", "li", "tr"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"p", "div", "li", "tr"}:
            self.parts.append(" ")


def _plain_text(value: Any) -> str:
    raw = html.unescape(str(value or ""))
    parser = _TextExtractor()
    parser.feed(raw)
    text = "".join(parser.parts)
    # Payroll sometimes removes whitespace at HTML line-break boundaries.
    for label in (
        "Team Leader:", "Agent Name:", "Type of Issue:",
        "Details about incident:", "Reported by TL:", "Action Given:",
    ):
        text = re.sub(rf"(?<=[\w)])(?={re.escape(label)})", " ", text, flags=re.IGNORECASE)
    # These separators are labels; spaces around their colons vary between the sheet and Payroll.
    text = re.sub(r"\s*:\s*", ":", text)
    return " ".join(text.split())


def normalize_details(value: Any) -> str:
    """Remove markup/entities and whitespace-only differences, preserving content/case."""
    return unicodedata.normalize("NFKC", _plain_text(value))


def _is_verbal_action(details: Any) -> bool:
    text = _plain_text(details)
    # The Actions sheet may label this choice as either Action Given or Deduction.
    # Both represent the same verbal-only action that should be excluded.
    for label in ("Action Given", "Deduction"):
        match = re.search(
            rf"\b{label}\s*:\s*(.*?)(?=\s+(?:Action Given|Deduction|Reported by TL|Team Leader|Agent Name|Type of Issue|Details about incident)\s*:|$)",
            text,
            flags=re.IGNORECASE,
        )
        if match and match.group(1).strip().casefold() == "verbal":
            return True
    return False


def _team_leader_name(details: Any) -> str:
    text = _plain_text(details)
    match = re.search(
        r"\bTeam Leader\s*:\s*(.*?)(?=\s+(?:Agent Name|Type of Issue|Details about incident|Reported by TL|Action Given|Deduction)\s*:|$)",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


def _header_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _date_value(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        # Sheets serial date values, relative to 1899-12-30.
        number = float(text)
        if 20000 < number < 100000:
            from datetime import timedelta
            return date(1899, 12, 30) + timedelta(days=int(number))
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _google_sheet_values(spreadsheet_id: str, sheet_name: str, range_name: str) -> list[list[str]]:
    csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq"
    try:
        response = requests.get(
            csv_url,
            params={"tqx": "out:csv", "sheet": sheet_name},
            timeout=(10, 45),
        )
        response.raise_for_status()
        if response.text.lstrip().lower().startswith(("<!doctype html", "<html")):
            raise ValueError("Google returned a web page instead of the sheet CSV")
        return list(csv.reader(io.StringIO(response.text)))
    except (requests.RequestException, ValueError) as public_error:
        if not os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
            raise ValueError(
                f"Could not read the public {sheet_name} sheet. Confirm it is shared with anyone who has the link, "
                "or configure GOOGLE_SERVICE_ACCOUNT_JSON for the backend."
            ) from public_error
        credentials = get_service_account_credentials()
        sheets = build_sheets(credentials)
        escaped_tab = sheet_name.replace("'", "''")
        return sheets.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{escaped_tab}'!{range_name}",
            valueRenderOption="FORMATTED_VALUE",
        ).execute().get("values", [])


def _waiver_template_key(value: Any) -> str:
    text = normalize_details(value).strip()
    quote_pairs = (("\"", "\""), ("'", "'"), ("“", "”"), ("‘", "’"))
    for opening, closing in quote_pairs:
        if len(text) >= 2 and text.startswith(opening) and text.endswith(closing):
            text = text[len(opening):-len(closing)].strip()
            break
    return text.casefold()


def _waived_action_templates() -> set[str]:
    spreadsheet_id = os.getenv("TL_ACTIONS_WAIVER_SPREADSHEET_ID", WAIVER_SPREADSHEET_ID)
    sheet_name = os.getenv("TL_ACTIONS_WAIVER_SHEET_NAME", WAIVER_SHEET_NAME)
    values = _google_sheet_values(spreadsheet_id, sheet_name, "A:Z")
    header_index = None
    template_index = result_index = None
    for row_index, row in enumerate(values[:20]):
        keys = [_header_key(cell) for cell in row]
        template = next((i for i, key in enumerate(keys) if key == "pleaseinsertactiontempfromthereportinggroup"), None)
        result = next((i for i, key in enumerate(keys) if key == "result"), None)
        if template is not None and result is not None:
            header_index, template_index, result_index = row_index, template, result
            break
    if header_index is None or template_index is None or result_index is None:
        raise ValueError("Could not find the action template and Result columns in the waiver sheet")

    waived = set()
    for row in values[header_index + 1:]:
        template = row[template_index] if template_index < len(row) else ""
        result = row[result_index] if result_index < len(row) else ""
        normalized_template = _waiver_template_key(template)
        if normalized_template and str(result).strip().casefold() == "waived":
            waived.add(normalized_template)
    return waived


def _sheet_action_rows(start_date: date, end_date: date) -> list[dict[str, str]]:
    spreadsheet_id = os.getenv("TL_ACTIONS_SPREADSHEET_ID", SPREADSHEET_ID)
    values = _google_sheet_values(spreadsheet_id, SHEET_NAME, "A:Z")
    waived_templates = _waived_action_templates()
    if not values:
        raise ValueError("The Actions tab is empty")

    header_index = None
    date_index = detail_index = None
    for row_index, row in enumerate(values[:20]):
        keys = [_header_key(cell) for cell in row]
        d = next((i for i, key in enumerate(keys) if key in {"actiondate", "date", "createddate", "timestamp"}), None)
        detail = next((i for i, key in enumerate(keys) if key in {"details", "detailsaboutincident", "actiondetails"}), None)
        if d is not None and detail is not None:
            header_index, date_index, detail_index = row_index, d, detail
            break
    if header_index is None or date_index is None or detail_index is None:
        raise ValueError("Could not find Action Date and Details columns in the Actions tab")

    headers = values[header_index]
    result = []
    for row_number, row in enumerate(values[header_index + 1:], start=header_index + 2):
        if not any(str(cell).strip() for cell in row):
            continue
        action_day = _date_value(row[date_index] if date_index < len(row) else "")
        if action_day is None or not start_date <= action_day <= end_date:
            continue
        fields = {str(headers[i]).strip(): str(row[i]) for i in range(min(len(headers), len(row)))}
        details = fields.get(headers[detail_index], "")
        if not normalize_details(details):
            continue
        is_verbal = _is_verbal_action(details)
        is_waived = _waiver_template_key(details) in waived_templates
        category = "verbal" if is_verbal else "waived" if is_waived else "hr_required"
        result.append({
            "sheet_row": row_number,
            "action_date": str(action_day),
            "details": details,
            "category": category,
        })
    return result


def _sheet_rows(start_date: date, end_date: date) -> list[dict[str, str]]:
    """Return only actions that team leaders are expected to submit to Payroll."""
    return [row for row in _sheet_action_rows(start_date, end_date) if row["category"] == "hr_required"]


def _payroll_actions(start_date: date, end_date: date) -> list[dict[str, Any]]:
    email = os.getenv("PAYROLL_EMAIL")
    password = os.getenv("PAYROLL_PASSWORD")
    if not email or not password:
        raise ValueError("Configure PAYROLL_EMAIL and PAYROLL_PASSWORD in the backend environment")

    with requests.Session() as session:
        login = session.post(
            f"{PAYROLL_API}/login",
            json={"email": email.lower(), "password": password},
            timeout=(10, 30),
        )
        if not login.ok:
            raise ValueError(f"Payroll login failed (HTTP {login.status_code})")
        token = login.json().get("token")
        if not token:
            raise ValueError("Payroll login response did not include an access token")
        session.headers.update({"Authorization": f"Bearer {token}"})

        all_items: list[dict[str, Any]] = []
        page = 1
        total = None
        while total is None or len(all_items) < total:
            response = session.get(
                f"{PAYROLL_API}/action_againsts",
                params={
                    "page": page,
                    "limit": PAGE_SIZE,
                    "created_start": start_date.isoformat(),
                    "created_end": end_date.isoformat(),
                    "include_hr_comment": "true",
                },
                timeout=(10, 60),
            )
            if not response.ok:
                raise ValueError(f"Payroll action request failed (HTTP {response.status_code})")
            payload = response.json()
            data = payload.get("data", payload)
            items = data.get("items", [])
            if not isinstance(items, list):
                raise ValueError("Payroll returned an unexpected actions response")
            all_items.extend(
                item.get("attributes", item)
                for item in items
                if isinstance(item, dict) and isinstance(item.get("attributes", item), dict)
            )
            try:
                total = int(data.get("count", len(all_items)))
            except (TypeError, ValueError):
                total = len(all_items)
            if not items or page > 500:
                break
            page += 1
        return all_items


def reconcile_tl_actions(start_date: date, end_date: date) -> dict[str, Any]:
    if end_date < start_date:
        raise ValueError("End date must be on or after start date")
    all_sheet_actions = _sheet_action_rows(start_date, end_date)
    sheet = [row for row in all_sheet_actions if row["category"] == "hr_required"]
    payroll = _payroll_actions(start_date, end_date)

    payroll_by_details: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    for item in payroll:
        key = normalize_details(item.get("details", ""))
        if key:
            payroll_by_details[key].append(item)

    missing = []
    matched_count = 0
    for source in sheet:
        candidates = payroll_by_details[normalize_details(source["details"])]
        if candidates:
            candidates.popleft()
            matched_count += 1
        else:
            details = _plain_text(source["details"])
            missing.append({
                "sheet_row": source["sheet_row"],
                "action_date": source["action_date"],
                "details": details,
                "team_leader": _team_leader_name(details) or "Unknown team leader",
            })

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "sheet_count": len(sheet),
        "missing_count": len(missing),
        "action_count": len(all_sheet_actions),
        "verbal_count": sum(row["category"] == "verbal" for row in all_sheet_actions),
        "waived_count": sum(row["category"] == "waived" for row in all_sheet_actions),
        "hr_expected_count": len(sheet),
        "hr_found_count": matched_count,
        "results": missing,
    }
