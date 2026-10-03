"""Prepare review links for a missing TL Actions row in Podio and Google Forms."""

from __future__ import annotations

import csv
import html
import io
import os
import re
import unicodedata
from datetime import date
from typing import Any
from urllib.parse import urlencode

import requests

from backend.services.tl_actions_reconciliation import _sheet_rows, normalize_details

LOOKUP_SPREADSHEET_ID = "1NkCG8PxvI30rnhLtlQrc8j0_ROEnuXn6kMfIxIBtN-o"
TL_ACM_GID = "118340812"
TL_RES_ID_GID = "0"
PODIO_WEBFORM_URL = "https://podio.com/webforms/29591643/2500783"
GOOGLE_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScuvOTJbo7H_QR4VbCguoo4xBXF80LmO-WMk3ETuxL_JbWj6Q/viewform"

GOOGLE_FORM_ENTRIES = {
    "direct_manager": "1301018716",
    "team_leader_res_id": "1274631215",
    "action_date": "1932945942",
    "details": "824789418",
    "action": "993608123",
}


def _plain_text(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    return re.sub(r"<[^>]*>", " ", text)


AUDITOR_BY_EMAIL = {
    "mohamedabdo@res-va.com": "Mohamed Ibrahim Abdo Ali",
    "ayasamir@res-va.com": "Aya Samir Farahat",
    "zeinab@res-va.com": "Zeinab ahmed anwer",
}

PODIO_INCIDENT_CHOICE = "Late hours sheet/leave request submission"


def _person_key(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", _plain_text(str(value or ""))).split()).casefold()


def _read_lookup_tab(gid: str) -> list[list[str]]:
    spreadsheet_id = os.getenv("TL_ACTIONS_LOOKUP_SPREADSHEET_ID", LOOKUP_SPREADSHEET_ID)
    response = requests.get(
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq",
        params={"tqx": "out:csv", "gid": gid},
        timeout=(10, 45),
    )
    response.raise_for_status()
    if response.text.lstrip().lower().startswith(("<!doctype html", "<html")):
        raise ValueError("The team lookup sheet did not return CSV data")
    return list(csv.reader(io.StringIO(response.text)))


def _column(headers: list[str], *names: str) -> int:
    normalized = {re.sub(r"[^a-z0-9]", "", h.casefold()): i for i, h in enumerate(headers)}
    for name in names:
        key = re.sub(r"[^a-z0-9]", "", name.casefold())
        if key in normalized:
            return normalized[key]
    raise ValueError(f"The team lookup sheet is missing the {names[0]} column")


def _lookup_team_leader_res_id(team_leader: str, rows: list[list[str]]) -> str:
    # The TL RES ID tab has no header row: column A is RES ID and column B is the person's name.
    matches = [row for row in rows if len(row) >= 2 and _person_key(row[1]) == _person_key(team_leader)]
    res_ids = {row[0].strip() for row in matches if row[0].strip()}
    if len(res_ids) != 1:
        raise ValueError("Could not find one team leader RES ID in the TL RES ID tab")
    return next(iter(res_ids))


def _lookup_direct_manager(team_leader: str, rows: list[list[str]]) -> str:
    if len(rows) < 2:
        raise ValueError("The team-leader manager tab is empty")
    name_col = _column(rows[0], "Name", "Team Leader")
    manager_col = _column(rows[0], "Direct Manager", "Manager")
    matches = [row for row in rows[1:] if name_col < len(row) and _person_key(row[name_col]) == _person_key(team_leader)]
    managers = {row[manager_col].strip() for row in matches if manager_col < len(row) and row[manager_col].strip()}
    if len(managers) != 1:
        raise ValueError("Could not find one direct manager for this team leader")
    return next(iter(managers))


def _action_fields(details: str) -> dict[str, str]:
    labels = ("Team Leader", "Agent Name", "Type of Issue", "Details about incident", "Reported by TL", "Action Given", "Deduction")
    pattern = re.compile(r"\b(" + "|".join(re.escape(label) for label in labels) + r")\s*:\s*", re.IGNORECASE)
    matches = list(pattern.finditer(details))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        label = next(label for label in labels if label.casefold() == match.group(1).casefold())
        end = matches[index + 1].start() if index + 1 < len(matches) else len(details)
        result[label] = _plain_text(details[match.end():end]).strip()
    return result


def _submission_payload(
    *, row_number: int, action_date: date, details: str, user_email: str,
) -> dict[str, Any]:
    fields = _action_fields(details)
    required = ("Team Leader", "Agent Name")
    missing = [name for name in required if not fields.get(name)]
    if missing:
        raise ValueError("Action details are missing: " + ", ".join(missing))

    auditor = AUDITOR_BY_EMAIL.get(user_email.strip().casefold())
    if not auditor:
        raise ValueError("This VOS account is not mapped to an auditor name in Podio")
    team_leader = fields["Team Leader"]
    direct_manager = _lookup_direct_manager(team_leader, _read_lookup_tab(TL_ACM_GID))
    team_leader_res_id = _lookup_team_leader_res_id(team_leader, _read_lookup_tab(TL_RES_ID_GID))

    return {
        "action_date": action_date.isoformat(),
        "details": _full_action_text(fields, action_date),
        "team_leader": team_leader,
        "agent_name": fields["Agent Name"],
        "team_leader_res_id": team_leader_res_id,
        "direct_manager": direct_manager,
        "auditor_name": auditor,
        "incident": PODIO_INCIDENT_CHOICE,
        "podio_action": "$2",
        "google_action": "$2",
    }


def _full_action_text(fields: dict[str, str], action_date: date) -> str:
    lines = [
        f"Team Leader: {fields['Team Leader']}",
        f"Agent Name: {fields['Agent Name']}",
        f"Type of Issue: {PODIO_INCIDENT_CHOICE}",
        "Details about incident:",
        f"Action of [{fields['Agent Name']}] was not sent by [{fields['Team Leader']}]",
        f"{action_date.month}/{action_date.day}/{action_date.year}",
    ]
    optional_lines = []
    if fields.get("Reported by TL"):
        optional_lines.append(f"Reported by TL: {fields['Reported by TL']}")
    optional_lines.append("Action Given: 2$")
    if optional_lines:
        lines.append("")
        lines.extend(optional_lines)
    return "\n".join(lines)


def _podio_choice_id(field_name: str, label: str, form_html: str) -> str:
    select = re.search(
        rf"<select\b(?=[^>]*\bname=[\"']{re.escape(field_name)}[\"'])[^>]*>(.*?)</select>",
        form_html,
        re.IGNORECASE | re.DOTALL,
    )
    if not select:
        raise ValueError(f"Could not find Podio form field: {field_name}")
    for option in re.finditer(r"<option\b([^>]*)>(.*?)</option>", select.group(1), re.IGNORECASE | re.DOTALL):
        value = re.search(r"\bvalue=[\"']([^\"']*)[\"']", option.group(1), re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", option.group(2))
        if value and " ".join(html.unescape(text).split()).casefold() == " ".join(label.split()).casefold():
            return value.group(1)
    raise ValueError(f"Podio choice was not found: {label}")


def _podio_agent_item_id(agent_name: str, form_html: str) -> tuple[str | None, str | None]:
    select = re.search(
        r"<select\b(?=[^>]*\bname=[\"']fields\[agent-name-for\][\"'])[^>]*>(.*?)</select>",
        form_html,
        re.IGNORECASE | re.DOTALL,
    )
    if not select:
        return None, "Could not find the Agent field in Podio. Select the Agent manually before submitting."

    matches: set[str] = set()
    for option in re.finditer(r"<option\b([^>]*)>(.*?)</option>", select.group(1), re.IGNORECASE | re.DOTALL):
        value = re.search(r"\bvalue=[\"']([^\"']*)[\"']", option.group(1), re.IGNORECASE)
        label = re.sub(r"<[^>]+>", "", option.group(2))
        if value and value.group(1) and _person_key(label) == _person_key(agent_name):
            matches.add(value.group(1))

    if len(matches) != 1:
        if matches:
            return None, f"More than one Podio Agent matches {agent_name}. Select the correct Agent manually before submitting."
        return None, f"Could not find {agent_name} in Podio's Agent list. Select the Agent manually before submitting."
    return next(iter(matches)), None


def _podio_prefill_url(payload: dict[str, Any]) -> str:
    response = requests.get(PODIO_WEBFORM_URL, timeout=(10, 45))
    response.raise_for_status()
    form_html = response.text
    if "fields[auditor-name]" not in form_html:
        raise ValueError("Could not read the Podio action form")
    agent_item_id, agent_warning = _podio_agent_item_id(payload["agent_name"], form_html)
    values = {
        "fields[auditor-name]": _podio_choice_id("fields[auditor-name]", payload["auditor_name"], form_html),
        "fields[team-leader-name]": _podio_choice_id("fields[team-leader-name]", payload["team_leader"], form_html),
        "fields[details-about-incident]": payload["details"],
        "fields[incident-2]": _podio_choice_id("fields[incident-2]", payload["incident"], form_html),
        "fields[action]": _podio_choice_id("fields[action]", payload["podio_action"], form_html),
    }
    if agent_item_id:
        values["fields[agent-name-for]"] = agent_item_id
    # Podio relationship fields require the destination item's Podio ID, not its RES ID.
    return f"{PODIO_WEBFORM_URL}?{urlencode(values)}", agent_warning


def _google_prefill_url(payload: dict[str, Any]) -> str:
    action_date = payload["action_date"].split("-")
    values = {
        "usp": "pp_url",
        "srd": "true",
        f"entry.{GOOGLE_FORM_ENTRIES['direct_manager']}": payload["direct_manager"],
        f"entry.{GOOGLE_FORM_ENTRIES['team_leader_res_id']}": payload["team_leader_res_id"],
        f"entry.{GOOGLE_FORM_ENTRIES['action_date']}_year": str(int(action_date[0])),
        f"entry.{GOOGLE_FORM_ENTRIES['action_date']}_month": str(int(action_date[1])),
        f"entry.{GOOGLE_FORM_ENTRIES['action_date']}_day": str(int(action_date[2])),
        f"entry.{GOOGLE_FORM_ENTRIES['details']}": payload["details"],
        f"entry.{GOOGLE_FORM_ENTRIES['action']}": payload["google_action"],
    }
    return f"{GOOGLE_FORM_URL}?{urlencode(values)}"


def prepare_missing_action(*, row_number: int, action_date: date, expected_details: str, user_email: str) -> dict[str, Any]:
    """Revalidate a visible sheet row and prepare links for manual form review."""
    if row_number < 2:
        raise ValueError("Invalid Actions sheet row")
    if not expected_details.strip():
        raise ValueError("Action details are empty")

    current_rows = _sheet_rows(action_date, action_date)
    source = next((row for row in current_rows if row["sheet_row"] == row_number), None)
    if source is None or normalize_details(source["details"]) != normalize_details(expected_details):
        raise ValueError("This sheet row changed after reconciliation. Find missing actions again before sending it.")

    payload = _submission_payload(
        row_number=row_number,
        action_date=action_date,
        details=source["details"],
        user_email=user_email,
    )
    podio_url, agent_warning = _podio_prefill_url(payload)
    return {
        "podio_url": podio_url,
        "google_form_url": _google_prefill_url(payload),
        "agent_name": payload["agent_name"],
        "agent_warning": agent_warning,
    }
