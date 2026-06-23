"""
Pure reachability summarizer for Campaign Lite Audit.
No I/O, no dependencies beyond stdlib. Called after the ReadyMode CSV pull.

LOW  = Dead Call + Unknown + Voicemail
GOOD = Decision Maker* (excl. DNC - Decision Maker) + Wrong Number
verdict = "LOW" if low_total > good_total else "GOOD"
"""

from __future__ import annotations
from typing import Any

_LOW_LABELS    = {"dead call", "unknown", "voicemail"}
_GOOD_PREFIX   = "decision maker"
_GOOD_EXACT    = {"wrong number"}
_EXCLUDE_PREFIX = "dnc"


def _classify(disposition: str) -> str | None:
    d = disposition.strip().lower()
    if d in _LOW_LABELS:
        return "low"
    if d.startswith(_EXCLUDE_PREFIX):
        return None
    if d.startswith(_GOOD_PREFIX) or d in _GOOD_EXACT:
        return "good"
    return None


def summarize_reachability(
    rows: list[dict[str, Any]],
    campaign_name: str,
) -> dict[str, Any]:
    """
    Bucket ReadyMode disposition rows into low vs good engagement.

    Each row must have a 'Disposition' key (from ReadyMode's 'Log Type' field).
    Rows should already be pre-filtered to the target campaign before calling.

    Returns:
        campaign_name, total_calls, verdict ('LOW'|'GOOD'),
        low_total, good_total, low_counts dict, good_counts dict
    """
    low_counts:  dict[str, int] = {}
    good_counts: dict[str, int] = {}

    for row in rows:
        raw = (row.get("Disposition") or "").strip()
        if not raw:
            continue
        group = _classify(raw)
        if group == "low":
            low_counts[raw]  = low_counts.get(raw, 0)  + 1
        elif group == "good":
            good_counts[raw] = good_counts.get(raw, 0) + 1

    low_total  = sum(low_counts.values())
    good_total = sum(good_counts.values())
    verdict    = "LOW" if low_total > good_total else "GOOD"

    return {
        "campaign_name": campaign_name,
        "total_calls":   len(rows),
        "verdict":       verdict,
        "low_total":     low_total,
        "good_total":    good_total,
        "low_counts":    low_counts,
        "good_counts":   good_counts,
    }
