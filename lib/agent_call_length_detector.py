"""
Pure long-call flagger for the agent Lite Audit.
No I/O, no dependencies beyond stdlib. Called after the ReadyMode CSV pull.

Flags two reachability-quality issues by exact recording length:
  - Voicemail  > threshold  (agent leaving long voicemails — wasted time)
  - Dead Call  > threshold  (agent not hanging up — should disconnect instantly)

Everything else (Decision Maker, Wrong Number, Unknown, DNC, ...) is ignored.
"""

from __future__ import annotations
from typing import Any

# Disposition labels we flag (case-insensitive, exact match on the ReadyMode label).
_FLAG_LABELS = {"voicemail", "dead call"}

DEFAULT_THRESHOLD = 15  # seconds


def _to_seconds(value: Any) -> float | None:
    """Best-effort parse of a 'Recording Length (Seconds)' cell to float seconds."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def flag_long_calls(
    rows: list[dict[str, Any]],
    threshold: int = DEFAULT_THRESHOLD,
    agent_name: str | None = None,
) -> list[dict[str, Any]]:
    """
    Return the subset of CSV rows that are long Voicemails / Dead Calls.

    Each input row should carry these keys (from the CSV export aliases):
        'Disposition'  (ReadyMode 'Log Type'),
        'Duration'     (ReadyMode 'Recording Length (Seconds)'),
        'Phone'        (ReadyMode 'CCS_Profile.phone'),
        'Call Log ID'  (ReadyMode 'Call Log ID'),
        'Agent name'   (ReadyMode 'u.u_name')  -- optional, used only when agent_name given.

    Args:
        rows:       parsed CSV rows (list of dicts).
        threshold:  strictly-greater-than seconds gate (default 15).
        agent_name: when given, keep only rows whose 'Agent name' matches (case-insensitive,
                    trimmed). When None, no agent filtering (e.g. an 'All users' run).

    Returns a list of flagged samples, each:
        {call_log_id, phone, disposition, duration, agent}
    where ``disposition`` is the original-cased label and ``duration`` is int seconds.
    """
    want_agent = agent_name.strip().lower() if agent_name else None
    flagged: list[dict[str, Any]] = []

    for row in rows:
        disp_raw = (row.get("Disposition") or "").strip()
        if disp_raw.lower() not in _FLAG_LABELS:
            continue

        if want_agent is not None:
            row_agent = (row.get("Agent name") or "").strip().lower()
            if row_agent != want_agent:
                continue

        secs = _to_seconds(row.get("Duration"))
        if secs is None or secs <= threshold:
            continue

        flagged.append({
            "call_log_id": (row.get("Call Log ID") or "").strip(),
            "phone":       (row.get("Phone") or "").strip(),
            "disposition": disp_raw,
            "duration":    int(secs),
            "agent":       (row.get("Agent name") or "").strip(),
        })

    return flagged


def summarize_long_calls(flagged: list[dict[str, Any]]) -> dict[str, int]:
    """Small count summary for metrics: {'voicemail': n, 'dead_call': n, 'total': n}."""
    vm = sum(1 for f in flagged if f["disposition"].strip().lower() == "voicemail")
    dc = sum(1 for f in flagged if f["disposition"].strip().lower() == "dead call")
    return {"voicemail": vm, "dead_call": dc, "total": len(flagged)}
