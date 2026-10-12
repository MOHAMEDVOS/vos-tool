# Campaign Audit: “Find busiest dialer” button

## What it does

The button checks the entered campaign across the seven configured ReadyMode dialers (`resva` through `resva7`) for the currently selected start and end dates. The frontend sends the campaign name and date range to `POST /api/readymode/campaign-dialer-counts`.

For each dialer, the backend logs into ReadyMode, looks up the campaign, requests the campaign-filtered call report, and estimates its total call count from the report page count and the last page size. These checks run concurrently. It returns the per-dialer counts, which dialers did not have the campaign, the dialer with the highest count, and any dialers whose check failed.

Campaign matching is case-insensitive exact matching first, then a match where the ReadyMode campaign name starts with the entered name followed by a dot. The `default` URL entry is skipped because it duplicates `resva`.

## What appears in the UI

The form shows the busiest dialer and its call count, followed by the counts (or “not found”) for each dialer. Failed dialers are listed separately. Clicking any found dialer row copies that dialer’s URL into the main Dialer URL field; it does not automatically choose the busiest row.

The button does not download recordings, analyze calls, consume audit quota, or start an audit. Those happen only when the user starts the audit separately. The check does perform ReadyMode logins and report reads across all configured dialers.

## Date range

The check uses the same date range selected in Campaign Audit. By default, Campaign Audit initializes this to the previous two workweeks (Monday through Friday), and refreshes it until the user customizes the range.

## Implementation

- UI and request construction: `webapp/src/pages/AuditPage.tsx`
- API type and client: `webapp/src/api/readymode.ts`
- Parallel dialer checks and counting: `backend/api/readymode.py`
- Campaign name resolution: `automation/readymode_http.py`
- Configured dialers: `config.py`

## Where Agent Audit gets agent names

ReadyMode's call log report endpoint (`/CCS Reports/call_log/update`) returns a `userlist` map alongside the call rows. Each dialer returns its own map of agent IDs to labels such as `Agents|Agent Name`; IDs are local to that dialer, so a name must be resolved separately on every dialer. Existing Agent Audit already does this: it gets `userlist` from the date-range report, resolves the entered name with `resolve_agent_id()`, then requests the report with that dialer's `restrict_uid`.

The lookup is based on agents represented in calls within the requested date range (and the selected call/disposition filters in Agent Audit). An agent with no matching calls in that range may not appear in the map. For a busiest-dialer check this is normally sufficient: a dialer with no matching calls cannot be the busiest. The resolver tries a case-insensitive exact name first, then accepts a dot-suffix variation (for example, an entered base name matching a ReadyMode label with a `.1` suffix).
