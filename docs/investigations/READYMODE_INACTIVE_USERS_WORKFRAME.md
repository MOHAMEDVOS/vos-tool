# ReadyMode Inactive User Cleanup — Workframe

**Date:** 2026-09-01
**Question:** Can VOS find agents who are no longer active on a dialer and delete them all in one step?
**Short answer:** Yes, built this session. It's a shift/login activity signal (did the agent work any shifts recently), not a call-volume one — that distinction matters and is explained below.

---

## Why "shift activity," not "call count"

The original ask was framed as "0 or 2 call logs in 60 days." Investigating it, the report that actually answers "is this agent still active" — **Agent Report** in ReadyMode's own sidebar — doesn't carry a per-agent call count at all. It's a per-agent, per-day **shift/login log**: Day/date, Name, User ID, Shift Start, Shift End, Logged Time, Ready/Break/Meeting/Bathroom/Lead time. An agent who never logs in has zero rows here, full stop — which is a cleaner and more direct "still active?" signal than call volume would be anyway (an agent could log in and work a shift but happen to get zero connects that day; that's a performance question, not a "should this account still exist" one).

So the feature flags agents by **days with at least one shift in the lookback window**, not calls — confirmed this is what was actually wanted mid-session ("no need for call count just the time activity").

---

## THE ROOT CAUSE (2026-09-02): the Agent Report is template-driven

Everything below about parsing was real, but it was downstream of the actual problem. **Which columns this report returns depends on which saved template the logged-in account has selected, and templates are per-account.**

All the browser-based recon ran under a human admin session whose selected template ("Auditor Template RTM", a custom one) happens to include a **User ID** column. The backend logs in as the `UserCreation` service account, which has no such template — so it got a structurally different report back and matched nothing. That is why every account showed 0 days and the whole roster was offered for deletion, on *every* dialer, even after the parsing fixes. The parser was fine; it was being handed a different report.

**The fix:** request a built-in preset explicitly instead of depending on the account's saved selection. `templateIdValue=P134` ("Agent report" under Default Reports) is available to every account. It returns one row per agent with a **Days Worked** column — the exact metric needed — instead of one row per agent per day, which also makes the response ~35× smaller (118KB vs 4MB for 60 days on resva).

**Critical detail (revised 2026-09-02, see the next section):** sending `templateIdValue` at all makes the server load the template's own saved date range and ignore the requested one — `loadingTemplate=1` is not what causes it. The fix is a two-step request, below.

**Trade-off accepted:** no built-in preset includes User ID (checked all four: P87, P102, P117, P134 — none have it). So roster↔activity matching is by display **name** now. Both sides are ReadyMode's own names, so they line up; and a name collision resolves toward the *most active* account, which fails safe — nobody is deleted because a namesake was idle.

Cross-validated live on resva: preset-based "Days Worked" for a known-active agent = **28**, exactly matching the 28 days counted independently by the old row-counting method, with 266 agents listed vs 265 counted the other way.

## SECOND ROOT CAUSE (2026-09-02): the requested date range was being ignored

Reported from production: the scan listed 1301 candidates on resva — the entire roster — including agents who work every day (Yomna Hussin Yassin, Shrouk Nader Abas Abdelgwad, Rowida Abbas Mohamed Mohamed). Every row showed 2 or fewer "active days."

Confirmed live by replaying the request: **a 60-day request came back holding two days of data (09/01–09/02).** With only two days in the report, the busiest agent on the dialer cannot show more than 2 days worked, so a `≤2 days` threshold matches everyone. The parsing was fine; the window was wrong.

Two separate server behaviours combine to cause it:

1. **The first agent-report POST in a session never applies the requested range.** It replies with whatever range the selected template has saved (one day on resva). Verified with fresh logins: identical params, first call → 2 days of data, second call → the full 60.
2. **`templateIdValue` re-loads the template *and* its saved date range every time it is sent** — with or without `loadingTemplate=1`. The earlier note blaming `loadingTemplate` was wrong; the flag is irrelevant.

**The fix — a two-step request** (`_post_agent_report()` in `readymode_http.py`):

| Call | Params | Purpose |
|---|---|---|
| 1 | dates + `templateIdValue=P134` + `loadingTemplate=1` | Selects the built-in preset. Response is discarded — its range is the template's, not ours. |
| 2 | dates only, **no** `templateIdValue` | Returns the preset's columns over the requested window. The template selection is already sticky on the session. |

**Verification handle:** the response echoes the window it actually used, in its own hidden inputs — `<input type='hidden' id='agent_rep_timefrom' value='07/04/2026' ...>` / `agent_rep_timeto`. `fetch_agent_activity()` now compares that echo against the requested range, retries once (resva4 generates the report server-side and can need a third call), and raises `ReadyModeAgentActivityError` rather than returning counts measured over a shorter window. A short window doesn't produce zero activity — it produces *undercounted* activity, which is worse: it looks plausible and flags real people.

Measured live on resva after the fix: 266 agents with activity (max 62 days worked), Yomna 27 days / 231h, Shrouk 22 days / 192h, Rowida 39 days / 211h. Full scan: 1302 accounts → **1037 candidates, every one at 0 days and 0 logged minutes.**

### Logged time is now reported, and the default threshold is 0

The preset's `Payable (t)` column (total logged/shift time) is parsed alongside Days Worked and returned as `minutes_active`, shown in the UI as a "Logged time" column. The default `max_days_active` dropped from 2 to **0** — "no login record at all in the window" — which is the only threshold that answers "should this account still exist" without a judgement call. At 0, any logged minutes also count as active (`_is_inactive()`), so an account can only be listed with zero days *and* zero hours. Raising the threshold goes back to a days-only question about people who did work.

## The originally captured contract (superseded above)

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

The candidate count itself is the tell. Compare it against the dialer's roster size: if candidates ≈ roster size exactly, no activity is being matched at all (parser broken, stale deployment, or — as in the 2026-09-02 date-range bug — the report covering a window too short for anyone to clear the threshold; check the max "active days" across all rows: if it equals the threshold, the window is wrong, not the roster). Measured live on resva 2026-09-02: roster 1301, genuinely active 249, correct candidates 1052 (≤2 days) / 1036 (zero days). A production UI showing exactly 1301 meant the deployed backend was running pre-fix code — the frontend bundle was current, but the parsing fix touched no frontend files, so a fresh frontend says nothing about the backend service having rebuilt.

## Known caveats

- **Folder-scan dependent, so it inherits that dependency's shakiness.** `resolve_folder_listing_id()`'s short-id/long-id derivation is confirmed for one folder on one dialer (see the duplicate-detection doc) — not yet proven everywhere.
- **Slow for the same reason folder scans are always slow**: full roster build is one request per writable folder, each potentially 1000+ users of HTML to parse, on top of the activity report itself (up to several MB for a 60-day window on a busy dialer). Parallelized the same way delete/duplicate-detection's folder scans are, but still bounded by the slowest single request.
- **`days_active` counts days, not hours.** An agent who logged in for 2 minutes on 3 different days looks more "active" than one who worked a full 8-hour shift once. Logged time is now shown next to it (`minutes_active`, from the report's `Payable (t)` column) so a surprising row can be judged on the spot.
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
