"""The Doc's numbers must match the Campaign dashboard's summary strip."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.campaign_report_doc import count_issues, reachability_text


def test_counts_skip_rebuttal_misses_that_were_not_fair():
    rows = [
        {"Releasing Detection": "Yes", "Rebuttal Detection": "No", "Objection Gate": "no_attempt"},
        {"Late Hello Detection": "Yes", "Rebuttal Detection": "No", "Objection Gate": "no_objection"},
        {"Wrong Dispo Detection": "Yes", "Rebuttal Detection": "Yes"},
    ]
    assert count_issues(rows) == {"releasing": 1, "late_hello": 1, "no_rebuttal": 1, "wrong_dispo": 1}


def test_reachability_text_matches_the_dashboard_copy():
    scan = {"verdict": "LOW", "low_total": 8047, "good_total": 5198,
            "low_counts": {"Dead Calls": 1290}, "good_counts": {"Decision Makers": 4230}}
    assert reachability_text(scan) == (
        "This campaign shows low reachability.\n\n"
        "Low Engagement (8,047 calls):\n• Dead Calls: 1,290\n\n"
        "Good Engagement (5,198 calls):\n• Decision Makers: 4,230"
    )
