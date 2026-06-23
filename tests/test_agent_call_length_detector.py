"""Unit tests for lib/agent_call_length_detector.py — pure logic, no DB, no I/O."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.agent_call_length_detector import flag_long_calls, summarize_long_calls


def _row(disposition, duration, phone="(813) 555-1234", call_log_id="1", agent="Ahmed"):
    return {
        "Disposition": disposition,
        "Duration": duration,
        "Phone": phone,
        "Call Log ID": call_log_id,
        "Agent name": agent,
    }


def test_voicemail_over_threshold_flagged():
    flagged = flag_long_calls([_row("Voicemail", "28")])
    assert len(flagged) == 1
    assert flagged[0]["disposition"] == "Voicemail"
    assert flagged[0]["duration"] == 28


def test_dead_call_over_threshold_flagged():
    flagged = flag_long_calls([_row("Dead Call", "22")])
    assert len(flagged) == 1
    assert flagged[0]["disposition"] == "Dead Call"
    assert flagged[0]["duration"] == 22


def test_at_or_below_threshold_ignored():
    rows = [_row("Voicemail", "15"), _row("Dead Call", "10"), _row("Voicemail", "0")]
    assert flag_long_calls(rows) == []


def test_other_dispositions_ignored():
    rows = [
        _row("Decision Maker - NYI", "120"),
        _row("Wrong Number", "60"),
        _row("Unknown", "90"),
        _row("DNC - Unknown", "200"),
    ]
    assert flag_long_calls(rows) == []


def test_bad_or_empty_duration_ignored():
    rows = [_row("Voicemail", ""), _row("Dead Call", None), _row("Voicemail", "abc")]
    assert flag_long_calls(rows) == []


def test_empty_input():
    assert flag_long_calls([]) == []


def test_case_insensitive_disposition():
    flagged = flag_long_calls([_row("VOICEMAIL", "30"), _row("dead call", "30")])
    assert len(flagged) == 2


def test_custom_threshold():
    rows = [_row("Voicemail", "8")]
    assert flag_long_calls(rows, threshold=5) == [] or flag_long_calls(rows, threshold=5)[0]["duration"] == 8
    assert len(flag_long_calls(rows, threshold=5)) == 1
    assert len(flag_long_calls(rows, threshold=10)) == 0


def test_agent_filter_matches_case_insensitive():
    rows = [
        _row("Voicemail", "30", agent="Ahmed Mohamed"),
        _row("Voicemail", "30", agent="Sara Ali"),
    ]
    flagged = flag_long_calls(rows, agent_name="ahmed mohamed")
    assert len(flagged) == 1
    assert flagged[0]["phone"]  # carried through


def test_agent_filter_none_keeps_all_agents():
    rows = [
        _row("Voicemail", "30", agent="Ahmed"),
        _row("Dead Call", "30", agent="Sara"),
    ]
    assert len(flag_long_calls(rows, agent_name=None)) == 2


def test_float_seconds_truncated_to_int():
    flagged = flag_long_calls([_row("Voicemail", "28.9")])
    assert flagged[0]["duration"] == 28


def test_summarize_long_calls():
    flagged = flag_long_calls([
        _row("Voicemail", "30"),
        _row("Voicemail", "40"),
        _row("Dead Call", "20"),
    ])
    summary = summarize_long_calls(flagged)
    assert summary == {"voicemail": 2, "dead_call": 1, "total": 3}


def test_fields_carried_through():
    flagged = flag_long_calls([_row("Voicemail", "30", phone="(813) 933-3426", call_log_id="7164070")])
    assert flagged[0]["phone"] == "(813) 933-3426"
    assert flagged[0]["call_log_id"] == "7164070"
