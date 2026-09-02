# ReadyMode Duplicate User Detection — Workframe

**Date:** 2026-09-01
**Question:** Duplicate ReadyMode users (the same person represented by 2+ accounts) have been showing up on dialers lately — can VOS detect and clean these up?
**Short answer:** Yes, built this session. It reuses the same `userlist` data the delete feature already resolves names against, groups by shared name, and lets you review before deleting the extras.

---

## Why this matters beyond "nice to have"

Building this surfaced a real gap in the delete feature built earlier: `resolve_agent_id()` (the function delete-by-name relies on) **silently returns the first matching name it finds**. If two accounts share a name, calling delete-by-name resolves and removes exactly one of them — arbitrarily, whichever ReadyMode's JSON happened to list first — with no signal a collision even occurred. In a world with duplicates, delete-by-name was already ambiguous. This feature both surfaces that collision and gives delete a precise, unambiguous way to target one exact account by uid.

---

## Design decisions (locked in, not open questions)

- **Duplicate scope:** same display name **anywhere on the dialer**, regardless of which folder each copy sits in. `userlist` entries carry a folder prefix (`"Admin|Name"` vs `"Agents|Name"`), and the same name can legitimately appear under different folders in the raw data — but two separate accounts (two different uids) sharing a name is exactly the shape an accidental duplicate takes, folder placement included. Scoping to "same folder only" would miss the case where one copy landed in the wrong folder.
- **Keep-which logic:** automatically keep the account with the **highest uid** (newest / most recently created), tag the rest `delete_candidate`. No manual per-group picking. uids sort as **integers**, not strings — `"1000"` must not rank before `"999"`.
  - Originally kept the *oldest*; flipped to newest on 2026-09-02 after seeing real groups (e.g. one name holding uids 1259–1262). When an account gets recreated, the newest copy is the one actually in use and the older ones are the abandoned leftovers.
- **Review before delete still applies.** Scan and delete are two separate steps in the UI; nothing is removed automatically just because a scan found it.

---

## How detection works

`automation/readymode_http.py` → `group_duplicate_users(userlist)`:
1. Parse each `userlist` entry (`{"x<uid>": "Folder|Name"}`) into `(uid, folder, name)`.
2. Group by name, case-insensitive and trimmed — the same match strength as `resolve_agent_id`'s exact-match first pass. Deliberately **not** `resolve_agent_id`'s fuzzy dot-suffix pass (`_name_match`) — reusing tolerant matching here would risk grouping two genuinely different people ahead of a delete action.
3. Groups of size 1 are dropped. Remaining groups sort accounts by uid ascending (integer) — index 0 = `keep`, the rest = `delete_candidate`.

Orchestration (`automation/find_duplicate_readymode_users.py`) mirrors the delete orchestrator: login once per dialer, fetch the userlist via the shared lookback window, group, return. Fans out across dialers with `ThreadPoolExecutor`, same as create/delete. **A login or fetch failure returns `status: "failed"`, never an empty group list under `status: "ok"`** — a scan failure must never look identical to "this dialer genuinely has no duplicates."

Exposed at `POST /api/readymode-users/duplicates` (admin-gated, same as `/delete` — this route reveals the full recently-active roster per dialer and is the direct precursor to a destructive action). Streams SSE-style, one log line per dialer plus a final `done` event with the per-dialer group breakdown.

---

## Formerly a known limitation, closed live (2026-09-01)

`fetch_report()`'s `userlist` **only includes accounts with at least one call in the queried date range** (90 days back from today — see `lookup_date_range()` in `readymode_http.py`; was originally 730 days, but that window times out `fetch_report()`'s 60s timeout against a real dialer with that much call history). A duplicate copy with zero call activity does not appear in `userlist` — this was flagged as out of scope initially, but turned out to be a real, immediate blocker (a live scan missed an actual zero-activity duplicate), so it was closed the same session.

**The fix:** `ReadyModeHTTPClient.list_folder_users(folder_id)` — a second, independent way to enumerate users, found via the same kind of live capture that found the delete contract. It `POST`s `Folders/Folder=<id>` (the generic Folders-app "open folder" action — confirmed live on resva4's Agents folder, folder id `54`, returning **every** account in that folder regardless of call history: 1215 users, all successfully parsed). The scan now calls `_build_roster()` (`find_duplicate_readymode_users.py`) to merge `userlist` with every writable folder's live listing before grouping — so a zero-activity duplicate is caught as long as its account exists in a folder, which is always true for a live account. `delete_users_on_dialer` gained the same fallback for name resolution, for the same reason (see [`READYMODE_DELETE_USER_WORKFRAME.md`](READYMODE_DELETE_USER_WORKFRAME.md)).

**Trade-off:** this makes both scans slower — one extra HTTP request per writable folder per dialer, and a folder can have 1000+ users to parse. Folder fetches are parallelized (`ThreadPoolExecutor`, both in `delete_users_on_dialer`'s fallback and `_build_roster()`) — sequential fetching was confirmed live as the actual source of a slow delete (2026-09-01). Still bounded by the slowest single folder, so still noticeably slower than the userlist-only fast path — worth knowing if a scan or a zero-activity delete feels sluggish. Two further options if it's still not fast enough, not yet implemented: scope the scan to one folder when the caller already knows which (biggest remaining win — turns "~6 folders" into "1"), or find whether ReadyMode's own search bar hits a targeted "search users by name" endpoint (would avoid full-folder scanning almost entirely, but needs its own live capture to confirm).

**One derivation that's inferred, not fully proven:** `list_folder_users()` takes a short numeric folder id (`"54"`), while `get_writable_folders()` (used by create) returns a longer per-instance id (`"54-109-"` on resva4). `resolve_folder_listing_id()` assumes the short id is just the numeric prefix before the first `-` — confirmed correct for the one folder tested live (Agents, resva4). Not yet verified on every folder/dialer combination; if a folder scan silently returns nothing on some dialer, this derivation is the first thing to check.

### Related gotcha found live (2026-09-01): already-deleted accounts still appear in `userlist`

A live scan on resva3 reported a "test" duplicate that didn't exist — manually checking Manage Users showed only one real `test` account. Cause: `userlist` keeps a name→uid entry for an account **after** it's been deleted, as long as that uid has historical calls within the queried window — and ReadyMode labels these with a literal `"(deleted)"` suffix (e.g. `"No group|test (deleted)"`, folder shows as `"No group"`). Both matching entries in this case were ghost records from a prior deletion, not a real live duplicate at all.

`group_duplicate_users()` now excludes any label containing `"(deleted)"` (case-insensitive) before grouping — confirmed live fix. Worth remembering when reasoning about `userlist` in general: it is a mix of *live* accounts and *dead accounts with surviving call history*, not a snapshot of currently-existing accounts. Anything else that reads `userlist` directly (rather than through `group_duplicate_users`/`resolve_agent_id`) should account for this too.

---

## Deleting a found duplicate

`BulkUserDeleteRow` (`backend/models/schemas.py`) gained an optional `uid` field. When set, `POST /api/readymode-users/delete` deletes that exact account — no name resolution, no ambiguity, reusing the same `client.delete_user(uid)` the delete feature already has.

**Hard safety rule, enforced server-side (`backend/api/readymode_users.py`):** a uid-carrying request must target exactly one dialer. A uid is only meaningful on the dialer it was scanned from — the same numeric id can belong to a completely different real person on another dialer. Broadcasting a uid-carrying request across multiple `dialer_urls` (the normal behavior for name-based create/delete, which intentionally do apply the same list to every selected dialer) would risk deleting an unrelated account wherever that id happens to exist elsewhere:

```python
if any(u.uid for u in request.users) and len(request.dialer_urls) != 1:
    raise HTTPException(status_code=400, detail="Exact-uid deletes must target exactly one dialer per request...")
```

The frontend enforces the same rule client-side (groups selected duplicates by dialer, fires one `/delete` request per dialer, never combined) — defense in depth, not a substitute for the server check.

---

## Where this lives

| Layer | File | What it does |
|---|---|---|
| Grouping logic | [`automation/readymode_http.py`](../../automation/readymode_http.py) | `group_duplicate_users()`, `lookup_date_range()` (shared with delete) |
| Orchestration | [`automation/find_duplicate_readymode_users.py`](../../automation/find_duplicate_readymode_users.py) | `find_duplicate_users_on_dialer()`, `find_duplicate_users_multi_dialer()` |
| Delete (uid-capable) | [`automation/delete_readymode_users.py`](../../automation/delete_readymode_users.py) | `delete_users_on_dialer()` now takes `targets: [{"name", "uid"}]` |
| API routes | [`backend/api/readymode_users.py`](../../backend/api/readymode_users.py) | `POST /duplicates` (new), `POST /delete` (uid-aware) |
| Schemas | [`backend/models/schemas.py`](../../backend/models/schemas.py) | `FindDuplicateUsersRequest`, `BulkUserDeleteRow.uid` |
| UI | [`webapp/src/pages/UsersPage.tsx`](../../webapp/src/pages/UsersPage.tsx) | Third "Duplicates" mode — scan, review, select, delete |

Related docs: [`DUPLICATE_USER_ANALYSIS.md`](DUPLICATE_USER_ANALYSIS.md) (why duplicates can be created in the first place — no dedup guard on ReadyMode bulk-create), [`READYMODE_DELETE_USER_WORKFRAME.md`](READYMODE_DELETE_USER_WORKFRAME.md) (the delete contract this reuses, and the same userlist limitation from delete's side).

---

**Bottom line:** duplicate detection is live — scan, review keep/delete-candidate tags, select, delete, all per-dialer. It's built entirely on data VOS could already fetch (the call-log report's userlist), so it inherits that data's one real limitation: zero-activity duplicates are invisible to it. That's documented everywhere it matters — code, doc, and UI — rather than left as a silent gap.
