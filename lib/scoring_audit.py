"""Per-agent aggregation for the Scoring section's heavy-audit ("Audit & Score") flow.

Pure, dependency-free functions (stdlib only) so they're easy to unit-test — same spirit as
``lib/scoring_sampler.py``. Where the sampler only picks phone numbers, this module turns the
*detections* of 5 freshly-downloaded heavy-audit samples (plus any already-flagged Actions-page
calls) into a single per-agent scoring verdict by **majority vote**.

The five quality points and how each maps to the company "Auditors-Scoring MOP" sheet:

  late_hello   -> col I  "Did the homeowner have to say 'hello' first?"        Yes = issue
  releasing    -> col M  "Agent's sound is low?"                               Yes = issue
  rebuttal_ok  -> col L  "Did the agent use rebuttals correctly?"              No  = issue
  agent_intro  -> col J  "Did the caller say his name and the purpose ...?"    No  = issue
  reason       -> col K  "Was the introduction delivered with energy ...?"     No  = issue

Voting:
  * Majority = strictly more than half of the *valid* votes (3 of 5, etc.). Ties / no-data fall
    to the non-issue side, matching the sheet's old fixed defaults (never penalise on no data).
  * late_hello and releasing also count the agent's Actions-page (already-flagged) calls — each
    such call votes by whether it tripped that flag. The other three points use the fresh samples
    only, because Actions-page rows don't carry intro / reason / rebuttal signal we trust here.
"""

from collections import defaultdict

from lib.scoring_sampler import (
    FLAG_RELEASING,
    FLAG_LATE_HELLO,
    FLAG_NO_REBUTTALS,
    _FLAG_ORDER,
    normalize_digits,
    format_phone_us,
)


def _get(row: dict, *keys):
    """First present, non-empty value among ``keys`` (case/spelling tolerant lookups)."""
    for k in keys:
        if k in row and str(row[k]).strip():
            return str(row[k]).strip()
    return ""


def _majority(true_count: int, total: int) -> bool:
    """True iff ``true_count`` is strictly more than half of ``total`` (ties -> False)."""
    return total > 0 and true_count * 2 > total


def _yn(flag: bool) -> str:
    return "Yes" if flag else "No"


def _detected_flags(row: dict) -> list:
    """Which of the three flags a single fresh heavy-audit result tripped."""
    flags = []
    if _get(row, "Releasing Detection", "releasing_detection") == "Yes":
        flags.append(FLAG_RELEASING)
    if _get(row, "Late Hello Detection", "late_hello_detection") == "Yes":
        flags.append(FLAG_LATE_HELLO)
    if _get(row, "Rebuttal Detection", "rebuttal_detection") == "No":
        flags.append(FLAG_NO_REBUTTALS)
    return flags


def aggregate_agent(agent: str, fresh_rows: list, action_calls: list, dialer: str = "") -> dict:
    """Fold an agent's fresh samples + Actions-page calls into one scoring row.

    Args:
        agent:        display name (as pasted).
        fresh_rows:   per-call dicts from ``batch_analyze_folder_fast`` for this agent's samples.
        action_calls: this agent's entries from the gather ``flagged_index`` -> ``[{phone, flags, dialer}]``.
        dialer:       busiest dialer the samples came from (col G), upper-cased by the caller is fine.

    Returns a row consumed by both the UI table and ``append_scoring_rows``::

        {agent, scores: {late_hello, releasing, rebuttal_ok, agent_intro, reason},  # each Yes/No
         phones: [{phone, flags}], note, flag_types, sample_count, action_count,
         source: "audited", dialer, tallies: {...}}
    """
    fresh_rows = fresh_rows or []
    action_calls = action_calls or []

    # Only fresh rows that actually classified contribute votes (skip "Error" rows).
    valid_rows = [r for r in fresh_rows if _get(r, "Status") != "Error"]

    def _yes_no_valid(*keys):
        """(#valid, #'Yes', #'No') for a Yes/No detection column across the valid fresh rows."""
        yes = no = 0
        for r in valid_rows:
            v = _get(r, *keys)
            if v == "Yes":
                yes += 1
            elif v == "No":
                no += 1
        return yes + no, yes, no

    # ── late_hello & releasing: fresh votes + one vote per Actions-page call ──
    lh_total, lh_yes, _ = _yes_no_valid("Late Hello Detection", "late_hello_detection")
    rel_total, rel_yes, _ = _yes_no_valid("Releasing Detection", "releasing_detection")

    for c in action_calls:
        c_flags = c.get("flags") or []
        lh_total += 1
        rel_total += 1
        if FLAG_LATE_HELLO in c_flags:
            lh_yes += 1
        if FLAG_RELEASING in c_flags:
            rel_yes += 1

    late_issue = _majority(lh_yes, lh_total)
    rel_issue = _majority(rel_yes, rel_total)

    # ── rebuttal / intro / reason: fresh samples only ──
    reb_total, _, reb_no = _yes_no_valid("Rebuttal Detection", "rebuttal_detection")
    intro_total, _, intro_no = _yes_no_valid("Agent Intro", "agent_intro")
    reason_total, _, reason_no = _yes_no_valid("Reason for calling", "Reason for Calling", "reason_for_calling")

    rebuttal_bad = _majority(reb_no, reb_total)     # majority "No" -> rebuttals not used correctly
    intro_missing = _majority(intro_no, intro_total)
    reason_missing = _majority(reason_no, reason_total)

    scores = {
        "late_hello": _yn(late_issue),       # Yes = issue
        "releasing": _yn(rel_issue),         # Yes = issue
        "rebuttal_ok": _yn(not rebuttal_bad),   # Yes = correct (No = issue)
        "agent_intro": _yn(not intro_missing),  # Yes = present (No = issue)
        "reason": _yn(not reason_missing),      # Yes = present (No = issue)
    }

    # ── phones: fresh sample numbers (with their own detected flags) + action numbers ──
    by_number, order = {}, []

    def _add(phone, flags):
        d = normalize_digits(phone)
        if not d:
            return
        if d not in by_number:
            by_number[d] = set()
            order.append(d)
        by_number[d].update(flags)

    for r in fresh_rows:
        _add(_get(r, "Phone Number", "phone_number"), _detected_flags(r))
    for c in action_calls:
        _add(c.get("phone"), c.get("flags") or [])

    phones = [
        {"phone": format_phone_us(d), "flags": [f for f in _FLAG_ORDER if f in by_number[d]]}
        for d in order
    ]

    # Human-readable issue summary for the table.
    issues = []
    if late_issue:
        issues.append(FLAG_LATE_HELLO)
    if rel_issue:
        issues.append(FLAG_RELEASING)
    if rebuttal_bad:
        issues.append(FLAG_NO_REBUTTALS)
    if intro_missing:
        issues.append("No Intro")
    if reason_missing:
        issues.append("No Reason")
    flag_types = [f for f in _FLAG_ORDER if f in issues]

    return {
        "agent": agent,
        "scores": scores,
        "phones": phones,
        "note": ", ".join(issues) if issues else "Clean",
        "flag_types": flag_types,
        "sample_count": len(valid_rows),
        "action_count": len(action_calls),
        "red_flag": bool(issues),
        "source": "audited",
        "dialer": dialer,
        "tallies": {
            "late_hello": {"yes": lh_yes, "total": lh_total},
            "releasing": {"yes": rel_yes, "total": rel_total},
            "rebuttal_no": {"no": reb_no, "total": reb_total},
            "agent_intro_no": {"no": intro_no, "total": intro_total},
            "reason_no": {"no": reason_no, "total": reason_total},
        },
    }
