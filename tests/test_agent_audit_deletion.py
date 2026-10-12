import asyncio

from fastapi import HTTPException

from backend.api import dashboard as dashboard_api
from backend.api.dashboard import DeleteAgentAuditRequest
from lib.dashboard_manager import dashboard_manager


def test_delete_agent_audit_results_scopes_to_shared_users_and_exact_agent(monkeypatch):
    captured = []

    class FakeDatabase:
        def execute_query(self, query, params, fetch):
            captured.append((query, params, fetch))
            return 3 if "agent_audit_results" in query else 2

    monkeypatch.setattr(dashboard_manager, "_db_manager", FakeDatabase())
    monkeypatch.setattr(dashboard_manager, "get_shared_users", lambda username: [username, "teammate"])

    deleted = dashboard_manager.delete_agent_audit_results("owner", "  Mona Hassan  ")

    assert deleted == {"agent_audit": 3, "lite_audit": 2}
    assert len(captured) == 2
    assert "DELETE FROM agent_audit_results" in captured[0][0]
    assert "DELETE FROM lite_audit_results" in captured[1][0]
    for query, params, fetch in captured:
        assert "LOWER(TRIM(COALESCE(agent_name, ''))) = LOWER(%s)" in query
        assert "username IN (%s,%s)" in query
        assert params == ("owner", "teammate", "Mona Hassan")
        assert fetch is False


def test_delete_agent_audit_results_rejects_blank_name_before_database(monkeypatch):
    class FakeDatabase:
        def execute_query(self, *args, **kwargs):
            raise AssertionError("database should not be called for a blank agent name")

    monkeypatch.setattr(dashboard_manager, "_db_manager", FakeDatabase())

    try:
        dashboard_manager.delete_agent_audit_results("owner", "   ")
    except ValueError as exc:
        assert str(exc) == "Agent name is required"
    else:
        raise AssertionError("blank agent name should be rejected")


def test_delete_agent_audit_results_reports_database_errors(monkeypatch):
    class FakeDatabase:
        def execute_query(self, *args, **kwargs):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(dashboard_manager, "_db_manager", FakeDatabase())
    monkeypatch.setattr(dashboard_manager, "get_shared_users", lambda username: [username])

    try:
        dashboard_manager.delete_agent_audit_results("owner", "Mona Hassan")
    except RuntimeError as exc:
        assert str(exc) == "database unavailable"
    else:
        raise AssertionError("database errors should be surfaced")


def test_delete_agent_audit_endpoint_returns_deleted_count(monkeypatch):
    monkeypatch.setattr(
        dashboard_api,
        "delete_agent_audit_results",
        lambda username, agent_name: {"agent_audit": 4, "lite_audit": 2},
    )

    response = asyncio.run(
        dashboard_api.delete_agent_audit_data(
            DeleteAgentAuditRequest(agent_name="  Mona Hassan  "),
            {"username": "owner"},
        )
    )

    assert response == {
        "message": "Agent and Lite Audit results deleted",
        "deleted_agent_audit_count": 4,
        "deleted_lite_audit_count": 2,
    }


def test_delete_agent_audit_endpoint_rejects_whitespace_name():
    try:
        asyncio.run(
            dashboard_api.delete_agent_audit_data(
                DeleteAgentAuditRequest(agent_name=" "),
                {"username": "owner"},
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "Agent name is required"
    else:
        raise AssertionError("whitespace-only agent names should be rejected")
