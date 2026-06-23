"""Unit tests for lib/campaign_audit_detector.py — pure logic, no DB, no I/O."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.campaign_audit_detector import summarize_reachability


def _rows(*dispositions: str) -> list[dict]:
    return [{"Disposition": d} for d in dispositions]


def test_low_verdict():
    result = summarize_reachability(
        _rows("Dead Call", "Dead Call", "Unknown", "Voicemail", "Decision Maker - NYI"),
        "TestCamp",
    )
    assert result["verdict"] == "LOW"
    assert result["low_total"] == 4
    assert result["good_total"] == 1
    assert result["low_counts"]["Dead Call"] == 2
    assert result["low_counts"]["Unknown"] == 1
    assert result["low_counts"]["Voicemail"] == 1
    assert result["good_counts"]["Decision Maker - NYI"] == 1


def test_good_verdict():
    result = summarize_reachability(
        _rows("Decision Maker - NYI", "Decision Maker - NYI", "Wrong Number", "Dead Call"),
        "TestCamp",
    )
    assert result["verdict"] == "GOOD"
    assert result["good_total"] == 3
    assert result["low_total"] == 1


def test_equal_is_good():
    result = summarize_reachability(
        _rows("Dead Call", "Decision Maker - NYI"),
        "TestCamp",
    )
    assert result["verdict"] == "GOOD"


def test_dnc_decision_maker_excluded():
    result = summarize_reachability(
        _rows("DNC - Decision Maker", "DNC - Decision Maker", "Dead Call"),
        "TestCamp",
    )
    assert result["good_total"] == 0
    assert result["low_total"] == 1
    assert result["verdict"] == "LOW"


def test_unknown_labels_ignored():
    result = summarize_reachability(
        _rows("Sold", "Influencer", "Dead Call"),
        "TestCamp",
    )
    assert result["low_total"] == 1
    assert result["good_total"] == 0
    assert "Sold" not in result["low_counts"]
    assert "Influencer" not in result["good_counts"]


def test_empty_input():
    result = summarize_reachability([], "TestCamp")
    assert result["verdict"] == "GOOD"
    assert result["total_calls"] == 0
    assert result["low_total"] == 0
    assert result["good_total"] == 0


def test_wrong_number_is_good():
    result = summarize_reachability(
        _rows("Wrong Number", "Wrong Number", "Dead Call"),
        "TestCamp",
    )
    assert result["good_total"] == 2
    assert result["good_counts"]["Wrong Number"] == 2


def test_case_insensitive():
    result = summarize_reachability(
        _rows("DEAD CALL", "voicemail", "WRONG NUMBER"),
        "TestCamp",
    )
    assert result["low_total"] == 2
    assert result["good_total"] == 1


def test_total_calls():
    rows = _rows("Dead Call", "Unknown", "Sold", "Decision Maker - NYI")
    result = summarize_reachability(rows, "TestCamp")
    assert result["total_calls"] == 4
