# Agent Busiest Dialer Implementation Plan

> **For agentic workers:** Execute this plan task by task and keep changes limited to the files listed below.

**Goal:** Let Agent Audit find the dialer with the most calls for the entered agent during the selected date range.

**Architecture:** Add a ReadyMode endpoint that checks each configured dialer concurrently, resolves the agent from that dialer's call-log `userlist`, and counts pages filtered by that dialer's agent ID. Add an Agent Audit button and results list matching the existing Campaign Audit interaction; clicking a found result sets the primary Dialer URL.

**Tech Stack:** FastAPI, Pydantic, ReadyModeHTTPClient, React, TypeScript.

**Spec:** Approved behavior in chat and name lookup notes in `docs/investigations/CAMPAIGN_DIALER_BUTTON.md`.

## Global Constraints

- Keep Google OAuth/JWT auth, quota logic, and database schema untouched.
- Use per-dialer user IDs; never reuse an ID from another dialer.
- Search the selected date range and do not start an audit from the lookup button.
- Preserve the existing campaign lookup behavior.

## Review Focus

- Agent absent from one dialer's `userlist`: report that dialer as not found and continue scanning others.
- One dialer request fails: report it in `failed` without losing successful dialer results.
- Same agent name on multiple dialers: resolve the name separately on each dialer before counting.
- Empty agent name: keep the button disabled, matching existing form behavior.
- No agent match on any dialer: show a clear not-found result without selecting a URL.

---

### Task 1: Agent call-count endpoint

**Files:**
- Modify: `backend/api/readymode.py`
- Test: `tests/test_agent_dialer_counts.py`
- Reuse: `automation/readymode_http.py:ReadyModeHTTPClient.fetch_report` and `resolve_agent_id`

**Interface:**
- Request: `{agent_name: string, start_date: ISO date, end_date: ISO date}`
- Response: `{agent_name: string, results: [{dialer, url, found, count}], busiest: result | null, failed: string[]}`

- [x] Add focused tests for per-dialer name resolution, page counting, absent agents, default-alias skipping, busiest selection, and per-dialer failures.
- [x] Run the focused tests and confirm the new behavior fails before implementing the endpoint.
- [x] Add an agent request model and per-dialer worker. Log in, load the dialer's own disposition IDs, fetch the date-range report to get that dialer's `userlist`, resolve the agent with `resolve_agent_id`, then fetch the filtered report and count its pages using the established page-size logic.
- [x] Add an authenticated endpoint that runs the worker concurrently for every configured dialer except the duplicate `default` alias, isolates failures by dialer, sorts results by count, and returns the busiest found result.
- [x] Review the endpoint against the five review-focus cases above and the existing campaign endpoint to ensure it does not change campaign behavior.

### Task 2: Agent Audit UI

**Files:**
- Modify: `webapp/src/api/readymode.ts`
- Modify: `webapp/src/pages/AuditPage.tsx`
- Verify: `npm run build` in `webapp/`

**Interface:**
- API client method: `agentDialerCounts({agent_name, start_date, end_date})`
- Response type: `AgentDialerCountsResponse` with the endpoint response fields above.

- [x] Add the response types and API client method.
- [x] Add independent loading, error, and result state for the Agent Audit lookup; render the button beside the agent identifier and use the current selected date range.
- [x] Render busiest, per-dialer counts, not-found rows, and failed dialers in the same visual pattern as Campaign Audit.
- [x] Make a found row set the primary Dialer URL, without starting an audit; confirm Campaign Audit rendering and behavior are unchanged by reviewing the diff.
- [x] Run the backend test suite and frontend production build; start the local app and confirm the route is registered.
