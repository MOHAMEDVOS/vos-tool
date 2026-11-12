"""Scoring must ignore samples that never finished analysis, whatever the Error status text says."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from lib.scoring_audit import aggregate_agent


def _five_calls_without_rebuttal(status):
    return [
        {"Status": status, "Rebuttal Detection": "No", "Late Hello Detection": "No",
         "Releasing Detection": "No", "Phone Number": f"(757) 000-000{i}"}
        for i in range(5)
    ]


def test_scored_samples_with_no_rebuttal_flag_the_agent():
    row = aggregate_agent("Agent", _five_calls_without_rebuttal("Good"), [])
    assert row["scores"]["rebuttal_ok"] == "No"


@pytest.mark.parametrize("status", ["Error", "Error: Rebuttal step failed: timeout"])
def test_samples_that_ended_in_an_error_status_do_not_count(status):
    row = aggregate_agent("Agent", _five_calls_without_rebuttal(status), [])
    assert row["scores"]["rebuttal_ok"] == "Yes"
