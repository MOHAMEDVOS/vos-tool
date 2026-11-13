"""Fill a copy of the campaign report Google Doc template (GOOGLE_DOC_TEMPLATE_ID) with a campaign's numbers.

Issue ratings and the Yes/No dropdowns stay as the template has them: the Docs API can't set a
dropdown chip, and ratings are left to the auditor.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from lib.google_workspace import _build_agent_issues_summary

logger = logging.getLogger(__name__)

# Template table rows (0-based) and the label each must carry, so an edited template fails loudly.
_ROW_LABELS = {1: "Campaign", 2: "duration", 9: "Coaching", 11: "Campaign List", 12: "Summary"}
_NOT_A_FAIR_MISS = ("no_objection", "owner_ended_call", "unusable")


def count_issues(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    """Same counts as the Campaign dashboard's summary strip."""
    return {
        "releasing": sum(r.get("Releasing Detection") == "Yes" for r in rows),
        "late_hello": sum(r.get("Late Hello Detection") == "Yes" for r in rows),
        "no_rebuttal": sum(
            r.get("Rebuttal Detection") == "No" and r.get("Objection Gate") not in _NOT_A_FAIR_MISS for r in rows
        ),
        "wrong_dispo": sum(r.get("Wrong Dispo Detection") == "Yes" for r in rows),
    }


def reachability_text(scan: Dict[str, Any]) -> str:
    """Mirrors buildCopyText in CampaignAuditDashboard.tsx."""
    def block(title: str, total: int, counts: Dict[str, int]) -> List[str]:
        return [f"{title} ({total:,} calls):", *(f"• {k}: {v:,}" for k, v in counts.items())]

    verdict = "low" if scan["verdict"] == "LOW" else "good"
    return "\n".join([
        f"This campaign shows {verdict} reachability.", "",
        *block("Low Engagement", scan["low_total"], scan["low_counts"]), "",
        *block("Good Engagement", scan["good_total"], scan["good_counts"]),
    ])


def _cell(doc: dict, row: int, col: int) -> dict:
    table = next(e["table"] for e in doc["body"]["content"] if "table" in e)
    return table["tableRows"][row]["tableCells"][col]


def _cell_text(cell: dict) -> str:
    return "".join(
        pe.get("textRun", {}).get("content", "")
        for ce in cell["content"] for pe in ce.get("paragraph", {}).get("elements", [])
    )


def _chips(cell: dict, kind: str) -> List[dict]:
    return [pe for ce in cell["content"] for pe in ce.get("paragraph", {}).get("elements", []) if kind in pe]


def create_campaign_doc(
    drive, docs, *, template_id: str, folder_id: str, campaign: str,
    start_date: Optional[date], end_date: Optional[date], rows: List[Dict[str, Any]],
    scan: Optional[Dict[str, Any]], sheet_url: str, dialer: str = "",
) -> str:
    """Copy the template, fill it, and return the new doc's URL (the caller shares it)."""
    month = (end_date or start_date or date.today()).strftime("%b")
    doc_id = drive.files().copy(
        fileId=template_id, supportsAllDrives=True,
        body={"name": f"{campaign.replace(' ', '_')}_week_{month}", "parents": [folder_id]},
    ).execute()["id"]

    n = count_issues(rows)
    replaced = docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
        {"replaceAllText": {"containsText": {"text": old, "matchCase": True}, "replaceText": new}}
        for old, new in [
            ("Releasing Calls : out of 1000", f"Releasing\t{n['releasing']} / 1,000"),
            ("Late Hello Calls : out of 1000", f"Late Hello\t{n['late_hello']} / 1,000"),
            ("No rebuttals / early hang ups from the owners  : out of 200",
             f"No Rebuttal\t{n['no_rebuttal']} / 200\nWrong Dispo\t{n['wrong_dispo']} / 1,000"),
        ]
    ]}).execute()
    if any(r.get("occurrencesChanged", 0) < 1 for r in replaced["replies"]):
        logger.warning("Campaign doc %s: a ratio line was not found in the template", doc_id)

    doc = docs.documents().get(documentId=doc_id).execute()
    for row, label in _ROW_LABELS.items():
        if label not in _cell_text(_cell(doc, row, 0)):
            raise ValueError(f"Doc template changed: row {row} should mention '{label}'")

    edits: List[tuple] = []  # (index, [requests]); applied from the end so earlier indexes stay valid

    def insert(index: int, text: str) -> None:
        edits.append((index, [{"insertText": {"location": {"index": index}, "text": text}}]))

    name_cell = _cell(doc, 1, 0)
    for el in _chips(name_cell, "dropdown"):
        if dialer:
            edits.append((el["startIndex"], [
                {"deleteContentRange": {"range": {"startIndex": el["startIndex"], "endIndex": el["endIndex"]}}},
                {"insertText": {"location": {"index": el["startIndex"]}, "text": dialer.upper()}},
            ]))
    run = next(pe for ce in name_cell["content"] for pe in ce["paragraph"]["elements"] if "“”" in pe.get("textRun", {}).get("content", ""))
    insert(run["startIndex"] + run["textRun"]["content"].index("“”") + 1, campaign)

    for chip, value in zip(_chips(_cell(doc, 2, 1), "dateElement"), (start_date, end_date)):
        if value:
            stamp = datetime(value.year, value.month, value.day, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
            edits.append((chip["startIndex"], [
                {"deleteContentRange": {"range": {"startIndex": chip["startIndex"], "endIndex": chip["endIndex"]}}},
                {"insertDate": {"location": {"index": chip["startIndex"]}, "dateElementProperties": {
                    "timestamp": stamp, "dateFormat": "DATE_FORMAT_MONTH_DAY_YEAR_ABBREVIATED", "locale": "en"}}},
            ]))

    coaching = "\n".join(f"{agent}\t{label}" for agent, label, _, _ in _build_agent_issues_summary(rows))
    if coaching:
        insert(_cell(doc, 9, 3)["content"][0]["startIndex"], coaching)
    if scan:
        insert(_cell(doc, 11, 3)["content"][0]["startIndex"], reachability_text(scan))

    link_par = next(ce for ce in _cell(doc, 12, 1)["content"] if "Detailed" in _cell_text({"content": [ce]}))
    at = link_par["endIndex"] - 1
    title = f"{campaign} - audit data"
    edits.append((at, [
        {"insertText": {"location": {"index": at}, "text": title}},
        {"updateTextStyle": {"range": {"startIndex": at, "endIndex": at + len(title)},
                             "textStyle": {"link": {"url": sheet_url}}, "fields": "link"}},
    ]))

    requests = [r for _, group in sorted(edits, key=lambda e: e[0], reverse=True) for r in group]
    docs.documents().batchUpdate(documentId=doc_id, body={
        "requests": requests, "writeControl": {"requiredRevisionId": doc["revisionId"]},
    }).execute()
    return f"https://docs.google.com/document/d/{doc_id}/edit"
