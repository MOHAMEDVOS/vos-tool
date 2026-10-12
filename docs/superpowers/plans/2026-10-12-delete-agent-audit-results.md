# Delete Agent Audit Results Implementation Plan

> **For agentic workers:** Native execution in this session. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user permanently delete one agent's Agent Audit records from the Actions table.

**Architecture:** Add a user-authenticated API route that asks the dashboard manager to delete matching `agent_audit_results` rows only for users sharing the caller's dashboard. Add a confirmation action to the Actions page's Agent Deductions table and invalidate Agent Audit, flagged-call, and badge queries. Lite Audit and campaign data remain untouched.

**Tech Stack:** FastAPI, PostgreSQL, React 19, TypeScript, TanStack Query, pytest, Vite.

**Spec:** [docs/investigations/AGENT_AUDIT_RESULT_VISIBILITY.md](../../investigations/AGENT_AUDIT_RESULT_VISIBILITY.md)

## Global Constraints

- Follow the existing authenticated dashboard API and data-manager patterns.
- Keep dashboard sharing behavior consistent with existing bulk Agent Audit deletion.
- Do not change database schema or delete Lite Audit or campaign results.
- Show an explicit confirmation naming the agent before permanent deletion.

## Review Focus

- Agent names with surrounding whitespace or case differences must delete only the intended name match; test normalized case-insensitive matching.
- A request with a blank agent name must be rejected before reaching the database; test API validation.
- A delete must be limited to the caller's shared dashboard members and the Agent Audit table; test generated SQL/parameters.
- Lite Audit and campaign records must remain outside the deletion query; test that the manager targets only `agent_audit_results`.
- After success, the Actions, Dashboard Agent Audit, Call Review, and badge queries must refresh; verify in the local UI.

---

### Task 1: Add scoped deletion in the dashboard manager and API

**Files:**
- Modify: `lib/dashboard_manager.py`
- Modify: `backend/services/dashboard_service.py`
- Modify: `backend/api/dashboard.py`
- Create: `tests/test_agent_audit_deletion.py`

**Interface:** `POST /api/dashboard/agent-audits/delete` accepts `{"agent_name": "..."}` and returns `{"message": "Agent Audit results deleted", "deleted_count": n}` for the authenticated caller.

- [x] Write manager/API tests for successful deletion, blank-name rejection, shared-user scoping, case-insensitive exact agent-name matching, and DB failure handling.
- [x] Run the new tests and confirm they fail because the endpoint and manager method do not exist.
- [x] Add `delete_agent_audit_results(username, agent_name)` to delete matching rows in `agent_audit_results` for the caller's shared users only; return deleted row count.
- [x] Add a service wrapper and a Pydantic-validated FastAPI route; reject blank names and return a clear error on DB failure.
- [x] Run the new tests and then the existing Python test suite.

### Task 2: Add confirmed deletion to the Actions table

**Files:**
- Modify: `webapp/src/api/dashboard.ts`
- Modify: `webapp/src/pages/ActionsPage.tsx`

**Interface:** `dashboardApi.deleteAgentAudits(agentName: string)` calls the new route. `AgentDeductionsTable` accepts optional delete props so the control is enabled only on Actions, not Call Review.

- [x] Add a delete control in each Actions agent row and a confirmation naming the agent and explaining that only Agent Audit results are deleted; Lite Audit results may remain.
- [x] On confirmed deletion, call the API and invalidate `agent-audits`, `flagged-calls`, and `flagged-count`; show an error if the request fails.
- [x] Build the frontend with `npm run build` in `webapp`.

### Task 3: Run the app locally and verify the user flow

**Files:** None.

- [x] Start the backend and Vite frontend using the repository's local development setup; open the app at `http://localhost:3000` (Vite proxies API requests to port 8000).
- [ ] Open Actions locally, confirm the row action and named confirmation appear, cancel once, then confirm on a disposable/local account if authenticated data is available.
- [ ] Verify deleted Agent Audit rows disappear from Actions, Dashboard Agent Audit, and Call Review after refresh; confirm Lite Audit and campaign data are not included in the deletion.
- [x] Record the environment limitation: the local account has no flagged calls to delete; backend deletion behavior is covered with a fake database in tests.

### Task 4: Commit and push the feature

**Files:** Feature files and this plan only.

- [x] Review the final diff and stage only the feature files, the plan, and the investigation note; leave all pre-existing untracked files untouched.
- [ ] Commit the verified change and push the current branch to `origin` after confirming its URL.
