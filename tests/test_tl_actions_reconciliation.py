from datetime import date

from backend.services import tl_actions_reconciliation
from backend.services.tl_actions_reconciliation import _action_match_key


def test_waived_rtm_templates_match_actions_details_when_csv_joins_duration_boundary():
    cases = (
        (
            '<p>Team Leader: ahmed fouad ahmed abdeldayem<br/>Agent Name: Yomna Hussin Yassin<br/>'
            'Type of Issue: RTM<br/>Details about incident:</p><p>exceeded break time.<br/>'
            'break taken : 1h:16m</p><p>exceeded wrap-up time.<br/>'
            'wrap time : 1h:01m</p><p>Reported by TL: No<br/>Deduction: 25%</p>',
            'Team Leader: ahmed fouad ahmed abdeldayem\nAgent Name: Yomna Hussin Yassin\n'
            'Type of Issue: RTM\nDetails about incident:exceeded break time.\n'
            'break taken : 1h:16mexceeded wrap-up time.\nwrap time : 1h:01m'
            'Reported by TL:no\nDeduction: 25%"',
        ),
        (
            '<p>Team Leader: ahmed fouad ahmed abdeldayem<br/>Agent Name: Radwa ahmed fawzy mohamed<br/>'
            'Type of Issue: RTM<br/>Details about incident:</p><p>did not complete 9 hours.<br/>'
            'logged time : 6h:19m</p><p>exceeded break time.<br/>'
            'break taken : 1h:05m</p><p>exceeded bathroom time.<br/>bathroom time : 0h:12m</p>'
            '<p>Reported by TL: No<br/>Deduction: 25%</p>',
            '"Team Leader: ahmed fouad ahmed abdeldayem\nAgent Name: Radwa ahmed fawzy mohamed\n'
            'Type of Issue: RTM\nDetails about incident:did not complete 9 hours.\n'
            'logged time : 6h:19mexceeded break time.\nbreak taken : 1h:05mexceeded bathroom time.\n'
            'bathroom time : 0h:12mReported by TL: No\nDeduction: 25%"',
        ),
    )

    for action_details, appeal_template in cases:
        assert _action_match_key(action_details) == _action_match_key(appeal_template)


def test_hr_reconciliation_matches_duration_boundary_formatting_difference(monkeypatch):
    action_details = (
        '<p>Team Leader: ahmed fouad ahmed abdeldayem<br/>'
        'Agent Name: Yomna Hussin Yassin<br/>Type of Issue: RTM<br/>'
        'Details about incident:</p><p>exceeded break time.<br/>'
        'break taken : 1h:16m</p><p>exceeded wrap-up time.<br/>'
        'wrap time : 1h:01m</p><p>Reported by TL: No<br/>Deduction: 25%</p>'
    )
    monkeypatch.setattr(
        tl_actions_reconciliation,
        "_google_sheet_values",
        lambda _spreadsheet_id, sheet_name, _range: (
            [["Action Date", "Details"], ["10/27/2026", action_details]]
            if sheet_name == "Actions"
            else [["Please Insert action temp from the reporting group", "Result"]]
        ),
    )
    monkeypatch.setattr(
        tl_actions_reconciliation,
        "_payroll_actions",
        lambda _start_date, _end_date: [
            {
                "details": (
                    "Team Leader: AHMED FOUAD AHMED ABDELDAYEM Agent Name: Yomna Hussin Yassin "
                    "Type of Issue: RTM Details about incident: exceeded break time. "
                    "break taken : 1h:16mexceeded wrap-up time. wrap time : 1h:01m "
                    "Reported by TL: No Deduction: 25%"
                )
            }
        ],
    )

    result = tl_actions_reconciliation.reconcile_tl_actions(date(2026, 10, 27), date(2026, 10, 27))

    assert result["missing_count"] == 0
    assert result["hr_found_count"] == 1
