# Agent audit result visibility

## Findings

Agent Audit results are saved in `agent_audit_results` and loaded by the Dashboard's **Agent Audit** tab. The current **Clear Agent Audit Data** action removes all agent-audit records for the signed-in user's sharing group; it does not target a single agent.

The **Actions** page and **Call Review** page both derive their agent deduction rows from flagged calls. The flagged-call API combines agent-audit and lite-audit records, while excluding campaign rows. Therefore, deleting one agent's heavy Agent Audit results would remove those records from the Dashboard's Agent Audit tab, Actions, and Call Review after their queries refresh. Any lite-audit results for the same agent would remain in Actions and Call Review, and campaign audit results are stored separately.

The shared Agent Deductions table is used on both Actions and Call Review. A delete control added there would therefore appear in both places unless explicitly limited to one page.

## Product implication

If the intended action is **Delete this agent's Agent Audit results**, scope deletion to that agent's records in `agent_audit_results`; leave lite and campaign records untouched. Explain that matching flagged heavy-audit calls will also disappear from Actions and Call Review, while lite-audit calls for the same agent can still appear. Refresh/invalidate the Agent Audit, flagged-call, and badge queries after deletion.

The existing all-data deletion is broader: the clear action in Actions deletes both agent and lite audit data, while the Dashboard Agent Audit clear action deletes agent-audit data only.

## References

- `webapp/src/features/dashboard/AgentAuditDashboard.tsx` — Agent Audit table and existing clear-all control.
- `backend/api/dashboard.py` — Agent Audit read and clear endpoints; flagged-call endpoint.
- `backend/services/dashboard_service.py` — combines agent and lite audit data for flagged calls.
- `webapp/src/pages/ActionsPage.tsx` — Agent Deductions view and its use of flagged-call data.
- `webapp/src/pages/CallReviewPage.tsx` — reuses the Agent Deductions table and loads flagged calls.
- `lib/dashboard_manager.py` — storage and current bulk deletion behavior.
