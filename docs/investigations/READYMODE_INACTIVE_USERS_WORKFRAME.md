# ReadyMode Inactive User Cleanup — Workframe

**Date:** 2026-09-01
**Question:** Can VOS find agents who are no longer active on a dialer and delete them all in one step?
**Short answer:** Yes, built this session. It's a shift/login activity signal (did the agent work any shifts recently), not a call-volume one — that distinction matters and is explained below.

---

## Why "shift activity," not "call count"

The original ask was framed as "0 or 2 call logs in 60 days." Investigating it, the report that actually answers "is this agent still active" — **Agent Report** in ReadyMode's own sidebar — doesn't carry a per-agent call count at all. It's a per-agent, per-day **shift/login log**: Day/date, Name, User ID, Shift Start, Shift End, Logged Time, Ready/Break/Meeting/Bathroom/Lead time. An agent who never logs in has zero rows here, full stop — which is a cleaner and more direct "still active?" signal than call volume would be anyway (an agent could log in and work a shift but happen to get zero connects that day; that's a performance question, not a "should this account still exist" one).

So the feature flags agents by **days with at least one shift in the lookback window**, not calls — confirmed this is what was actually wanted mid-session ("no need for call count just the time activity").

---

## The captured contract

Captured live (2026-09-01) from `resva.readymode.com`, widening the Agent Report's date range and inspecting the request/response directly (jQuery's cached XHR reference meant live network-tab interception didn't work — the request was reconstructed from the page's own hidden form field names instead, then verified by firing it and parsing the real response):

```
POST {dialer}/CCS Reports/agent
Content-Type: application/x-www-form-urlencoded
X-Requested-With: XMLHttpRequest

config[dr][time_from_d]         = <MM/DD/YYYY>
config[dr][time_to_d]           = <MM/DD/YYYY>
config[dr][time_from_dateonly]  = 1
config[dr][time_to_dateonly]    = 1
agent_uid                       = (empty = all agents)
has_config_update               = 1
has_date_update                 = 1
todaysDate                      = <today, MM/DD/YYYY>
```

Response is an HTML fragment (not JSON — same pattern as the Folders app), `<table id="agent_report">` with one `<tr>` per (agent, day-with-a-shift). Confirmed live on resva with a 07/01–08/31 range: 4.38MB response, 6618 rows, 274 unique agents with any shift activity in that window.

Implemented as `ReadyModeHTTPClient.fetch_agent_activity(time_from, time_to)` in `automation/readymode_http.py`, returning `{uid: {"name", "days_active", "last_day"}}` — `days_active` is a **count of distinct days** with a shift row, not total hours; `last_day` is the raw "Mon DD" string from the last such row (no year in the source data).

---

## How the full feature works

An agent with zero shifts in the window doesn't appear in `fetch_agent_activity()`'s result at all — so "inactive" needs a full account roster to diff against, not just this report. That's exactly what `list_folder_users()` (built earlier this session for the delete/duplicate-detection zero-activity gap — see [`READYMODE_DELETE_USER_WORKFRAME.md`](READYMODE_DELETE_USER_WORKFRAME.md)) already provides: every account in every writable folder, regardless of activity.

`automation/find_inactive_readymode_users.py`:
1. Build the full roster via every writable folder (parallelized, same pattern as duplicate-detection's `_build_roster`).
2. Fetch shift activity for the lookback window (default 60 days).
3. Compute every account's `days_active` (0 for accounts with zero rows in the activity report).

### Cross-dialer rule (added 2026-09-01, explicit product decision)

An agent can hold a separate account on more than one dialer. The original per-dialer version flagged an account purely on its own dialer's activity — but someone idle on dialer A while actively working dialer B is still active at the company; that's not who this feature is for. So when more than one dialer is scanned in the same request, a candidate is only flagged if their activity is at-or-below the threshold on **every** dialer they were found on, among the ones actually scanned — active anywhere scanned excludes them everywhere, even on the dialer where their own account looks idle.

Matching across dialers is by **display name** (case-insensitive, trimmed) — there's no other cross-dialer identity available; a uid is only ever meaningful on the dialer it came from. `find_inactive_users_multi_dialer()` now scans every dialer fully (unfiltered per-account data, via `_scan_dialer_full()`), builds a name → max-days-active map across all successfully-scanned dialers, then filters each dialer's own low-activity accounts against that map before returning results. Verified with a synthetic two-dialer test: an account low on dialer A but high on dialer B is correctly excluded from A's results; an account low on both is correctly flagged on both.

**A dialer that fails to scan is excluded from the "active elsewhere?" check** (no data from it either way) but still reported with `status: "failed"` — silence from a failed dialer must never be read as "confirmed inactive there." With only one dialer selected, the cross-dialer check is a no-op and behavior is identical to before.

Exposed at `POST /api/readymode-users/inactive` (`FindInactiveUsersRequest`: `dialer_urls`, `max_days_active`, `lookback_days`) — request/response shape unchanged by the cross-dialer rule, only the internal filtering logic changed. Admin-gated and SSE-streamed like `/duplicates`. Deletion reuses the existing uid-based `/delete` path unchanged — same per-dialer grouping and single-dialer-per-uid-request safety rule as duplicate-detection's delete flow.

**UI:** lives inside Delete mode (not a fourth top-level mode) — "Find Inactive Users" section below the existing name-based delete form, sharing that mode's dialer selection. Scan → table per dialer (checkbox per row, select-all) → bulk delete, same shape as the Duplicates scan-then-delete flow.

---

## Bug found in production, fixed live (2026-09-01): every account showed 0 active days

Shipped, then a live production scan showed every single account at "0 active days" — including agents confirmed actively working that same day. Root cause, confirmed via the same live-recon technique used to find the endpoint in the first place: this table's HTML has ~13 opening `<td>` tags per row but only 1-2 literal `</td>` closes (valid HTML5 "optional end tag" parsing — browsers handle it natively; regex matching `<td>...</td>` *pairs* cannot, and silently matched almost nothing instead of raising). Fixed with the same position-based chunking technique `list_folder_users()` already used for the same reason: take the text between one `<td` tag's own `>` and the next `<td`'s start, never look for a closing tag.

A second, smaller bug surfaced during the same investigation: each agent's block includes one per-agent **TOTAL** row spanning the entire queried range (its day cell is `-`, not a real date) — originally counted as an extra "active day" and could overwrite `last_day` with `-`. Both are now excluded by skipping any row whose day cell is `-` or empty.

Verified against a synthetic HTML sample reproducing both the unclosed-tag structure and a total row before touching the live code path again.

**This is a reminder, not just a fix:** the parsing logic was verified against synthetic HTML I constructed myself, and against a JS/DOM-based prototype in a live browser — but never against the *actual* raw HTML text the Python `requests`-based client would receive, because getting raw HTML text out of the browser tool triggered a safety filter. DOM parsers silently correct malformed markup that naive regex takes at face value; a browser-based prototype passing doesn't guarantee a regex-based reimplementation of it works the same way. Any future regex-based scraper added to this codebase should get one live pass validating actual parse *counts* (rows found, cells found) against the real response, not just logic verified against a hand-written sample.

**That gap is now closed** (2026-09-02): the shipped `fetch_agent_activity()` was run against real captured markup (content replaced with placeholders, tag/attribute structure preserved byte-for-byte) and parses it correctly — 3 real days counted, the summary row excluded. The real structure, for reference: `<tr >` with a space; cell 0 (day) unclosed; cells 1-2 (name, uid) **do** carry `</td>`; cells 3+ unclosed; attributes unquoted (`class=flexible_cell row=1 col=0`); header row uses `<th>`; per-agent total rows carry `class=summary_rows` and a `-` day cell.

### Safety net added (2026-09-02)

Two separate silent failures in this parser have now each produced the same dangerous outcome: zero activity for everyone, which downstream reads as "the entire roster is inactive" and offers all of it for deletion. `fetch_agent_activity()` no longer swallows failures — it raises `ReadyModeAgentActivityError` both on a parse exception and, critically, when a **substantial response (>2000 bytes) yields zero parseable rows**. A legitimately empty response still returns `{}` without raising. The scan's existing error path turns this into a `status: "failed"` dialer (visible red error in the UI) instead of a delete-everything recommendation.

### Diagnosing this class of bug quickly

The candidate count itself is the tell. Compare it against the dialer's roster size: if candidates ≈ roster size exactly, no activity is being matched at all (parser broken, or stale deployment). Measured live on resva 2026-09-02: roster 1301, genuinely active 249, correct candidates 1052 (≤2 days) / 1036 (zero days). A production UI showing exactly 1301 meant the deployed backend was running pre-fix code — the frontend bundle was current, but the parsing fix touched no frontend files, so a fresh frontend says nothing about the backend service having rebuilt.

## Known caveats

- **Folder-scan dependent, so it inherits that dependency's shakiness.** `resolve_folder_listing_id()`'s short-id/long-id derivation is confirmed for one folder on one dialer (see the duplicate-detection doc) — not yet proven everywhere.
- **Slow for the same reason folder scans are always slow**: full roster build is one request per writable folder, each potentially 1000+ users of HTML to parse, on top of the activity report itself (up to several MB for a 60-day window on a busy dialer). Parallelized the same way delete/duplicate-detection's folder scans are, but still bounded by the slowest single request.
- **`days_active` counts days, not hours.** An agent who logged in for 2 minutes on 3 different days looks more "active" than one who worked a full 8-hour shift once. This matches what was asked for (time-based activity, not call volume) but is worth knowing if a flagged account looks surprising.
- **No year in `last_day`.** The raw report data doesn't include one; inferring it from the request's own date range wasn't attempted since the UI mainly needs "how many days," not the exact date.

## Where this lives

| Layer | File |
|---|---|
| Activity fetch + parse | [`automation/readymode_http.py`](../../automation/readymode_http.py) — `fetch_agent_activity()` |
| Orchestration | [`automation/find_inactive_readymode_users.py`](../../automation/find_inactive_readymode_users.py) |
| API route | [`backend/api/readymode_users.py`](../../backend/api/readymode_users.py) — `POST /inactive` |
| Schema | [`backend/models/schemas.py`](../../backend/models/schemas.py) — `FindInactiveUsersRequest` |
| UI | [`webapp/src/pages/UsersPage.tsx`](../../webapp/src/pages/UsersPage.tsx) — inside Delete mode |

Related: [`READYMODE_DELETE_USER_WORKFRAME.md`](READYMODE_DELETE_USER_WORKFRAME.md), [`READYMODE_DUPLICATE_DETECTION_WORKFRAME.md`](READYMODE_DUPLICATE_DETECTION_WORKFRAME.md) — both the folder-scan roster and the uid-based delete this feature depends on were built for those.
