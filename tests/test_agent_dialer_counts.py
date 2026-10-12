import asyncio
from unittest.mock import MagicMock, patch

from backend.api import readymode


def test_agent_count_resolves_agent_per_dialer_and_counts_report_pages():
    client = MagicMock()
    client.init_call_log.return_value = {"Decision Maker": 1, "Voicemail": 9}
    client.fetch_report.side_effect = [
        {"userlist": {"x77": "Agents|Maya Hassan"}},
        {"pages": 2, "results": {str(i): {} for i in range(25)}},
        {"pages": 2, "results": {str(i): {} for i in range(3)}},
    ]

    with patch.object(readymode, "ReadyModeHTTPClient", return_value=client):
        result = readymode._agent_count_for_dialer(
            "resva3", "https://resva3.readymode.com/", "user", "pass",
            "Maya Hassan", "10/01/2026", "10/12/2026",
        )

    assert result == {
        "dialer": "resva3",
        "url": "https://resva3.readymode.com/",
        "found": True,
        "count": 28,
    }
    assert client.fetch_report.call_args_list[0].kwargs["types"] == [6, 1]
    assert client.fetch_report.call_args_list[1].kwargs["restrict_uid"] == "77"
    assert client.fetch_report.call_args_list[2].kwargs["page"] == 1


def test_agent_count_returns_not_found_when_agent_is_absent_from_dialer_report():
    client = MagicMock()
    client.fetch_report.return_value = {"userlist": {"x12": "Agents|Other Agent"}}

    with patch.object(readymode, "ReadyModeHTTPClient", return_value=client):
        result = readymode._agent_count_for_dialer(
            "resva4", "https://resva4.readymode.com/", "user", "pass",
            "Maya Hassan", "10/01/2026", "10/12/2026",
        )

    assert result == {
        "dialer": "resva4",
        "url": "https://resva4.readymode.com/",
        "found": False,
        "count": 0,
    }
    client.fetch_report.assert_called_once()


def test_agent_dialer_endpoint_skips_default_alias_and_returns_busiest_dialer():
    def count_for_dialer(name, *_args):
        if name == "resva":
            raise RuntimeError("dialer unavailable")
        return {
            "dialer": name,
            "url": f"https://{name}.readymode.com/",
            "found": True,
            "count": 12,
        }

    request = readymode.AgentDialerCountRequest(
        agent_name="  Maya Hassan  ", start_date="2026-10-01", end_date="2026-10-12"
    )
    with (
        patch("config.get_user_readymode_credentials", return_value=("user", "pass")),
        patch("config.READY_MODE_URLS", {
            "default": "https://resva.readymode.com/",
            "resva": "https://resva.readymode.com/",
            "resva2": "https://resva2.readymode.com/",
        }),
        patch.object(readymode, "_agent_count_for_dialer", side_effect=count_for_dialer) as count,
    ):
        result = asyncio.run(readymode.agent_dialer_counts(request, {"username": "auditor"}))

    assert result["agent_name"] == "Maya Hassan"
    assert [row["dialer"] for row in result["results"]] == ["resva2"]
    assert result["busiest"]["dialer"] == "resva2"
    assert result["failed"] == ["resva"]
    assert count.call_count == 2
