# ReadyMode Delete User — Feasibility & Workframe

**Date:** 2026-09-01
**Question:** Can VOS delete users on ReadyMode the same way it creates them?
**Short answer:** Yes. The real request has been captured live against resva4 — it's a plain `GET`, much simpler than create. Not implemented in VOS yet, but the contract is no longer unknown.

---

## The captured contract

Captured from a live browser session (network log), dragging a throwaway test user (`deletest`, uid `1883`) to ReadyMode's own trash icon and confirming the "Are you sure?" prompt:

```
GET https://resva4.readymode.com/Folders/fileAction/Delete/User=1883
→ 200 OK
```

No request body — the target's `uid` is embedded directly in the URL path as `User=<uid>`. This matches the drag-to-trash element's own markup, inspected on the same page:

```html
<div dropsuccess="$(ui.draggable).remove()" dropact="Delete"
     dragtitle="Delete %ft%" id="..._folderTrash"
     title="Drag any file to this bin to permanently delete it"
     dropconf="Are you sure you want to delete this %ft%?">
```

`dropact="Delete"` under a generic `/Folders/fileAction/...` path confirms this is ReadyMode's **generic file-manager delete action** — the same mechanism used to delete files and folders elsewhere in the UI, not a user-specific endpoint. That's also why there was never a dedicated "Delete User" button to find: users are just icons inside folders in this UI, and deletion is "drag item to trash," identical for a user, a file, or a folder.

**Confirmed:** URL shape, method (GET), success status (200).
**Not yet confirmed** (worth nailing down before/during implementation):
- Required headers — the create endpoint needs `X-Requested-With`/`Referer`; unknown whether delete does too, since this was observed passively rather than replayed with a minimal request.
- Response body shape on success or failure — create returns `{"success":[...]}` / `{"error":"..."}` JSON; delete's 200 response body wasn't captured, so error handling (e.g. "uid doesn't exist on this dialer") is still a guess.
- Whether ReadyMode soft-deletes (there's a **"Show/hide deleted users"** toggle in the Manage Users UI, suggesting deleted users may land in a recoverable state rather than being purged immediately) or hard-deletes. Worth checking that toggle before assuming this is irreversible the way `rm` is.
- Only verified on resva4 — the URL shape doesn't reference any per-dialer folder/OU id (unlike create), so it likely generalizes cleanly across all 7 `resvaN` tenants, but that's inference, not a live check on each one.

---

## Why this needed a live capture at all

ReadyMode has no public API or documentation. Every ReadyMode HTTP call in this codebase — login, the call-log report, create-user — was reverse-engineered from a live recon capture, not from a spec (see the [`automation/readymode_http.py`](../../automation/readymode_http.py#L1-L6) module docstring, and [`docs/READYMODE_HTTP_SPEC.md`](../READYMODE_HTTP_SPEC.md)). Before this capture:

- **No code** anywhere in the repo deleted a ReadyMode dialer user — no function, no route, no stub, no TODO, no doc mention. Confirmed by a full-repo search for `delete_user|remove_user|delete_agent|remove_agent` (plus deactivate/disable/suspend variants), scoped to `automation/`, `backend/`, `webapp/`, `docs/`.
- **No known HTTP contract** for it — ReadyMode's delete action had never been captured.

There *is* an unrelated `delete_user` already in the codebase — it deletes VOS's **own** internal dashboard accounts (Auditor/Admin logins to this QA tool), nothing to do with ReadyMode: [`backend/api/settings.py:293-317`](../../backend/api/settings.py#L293-L317) → `backend/services/user_service.py`. Don't confuse the two later.

---

## How create_user works today (the pattern to mirror)

| Layer | File | What it does |
|---|---|---|
| HTTP client | [`automation/readymode_http.py:311-351`](../../automation/readymode_http.py#L311-L351) | `ReadyModeHTTPClient.create_user()` |
| Login/session | [`automation/readymode_http.py:108-132`](../../automation/readymode_http.py#L108-L132) | `.login()` |
| Per-dialer folder resolution | [`automation/readymode_http.py:264-309`](../../automation/readymode_http.py#L264-L309) | `.get_writable_folders()` / `.resolve_folder()` |
| Orchestration | [`automation/create_readymode_users.py`](../../automation/create_readymode_users.py) | `create_users_on_dialer()`, `create_users_multi_dialer()` |
| API route | [`backend/api/readymode_users.py:31-89`](../../backend/api/readymode_users.py#L31-L89) | `POST /api/readymode-users/create` |
| Request schema | [`backend/models/schemas.py:150-161`](../../backend/models/schemas.py#L150-L161) | `BulkUserRow`, `BulkUserCreateRequest` |
| UI | [`webapp/src/pages/UsersPage.tsx`](../../webapp/src/pages/UsersPage.tsx) | "Create Dialer Users" tab |

**The HTTP call itself** — one `requests.Session` per dialer, cookie-authenticated:

```
POST {dialer}/Team/ManageUsers/createUser/save
Content-Type: application/x-www-form-urlencoded
X-Requested-With: XMLHttpRequest

saveData[0][u_name]    = <display name>
saveData[0][u_account] = <login id>
saveData[0][u_ext]     = <extension, optional>
saveData[0][folder]    = <per-dialer folder id>
saveData[0][ou]        = <role id, e.g. "4" = Sales>
saveData[0][idx]       = "0"
bulkpw                 = <password>
questDisplay           = "false"
```

Success → `{"success": [{"uid": ..., "userName": ..., "groupId": ...}]}`. Failure → `{"error": "..."}`, raised as `ReadyModeUserCreateError`.

**Login** ([readymode_http.py:108-132](../../automation/readymode_http.py#L108-L132)) — form POST to `/login_new/?then=/` with browser-like headers (`Origin`/`Referer`/`Sec-Fetch-*`, no CSRF token); success is verified by the `stationId` cookie being present, not just a 2xx status.

**Credentials** — create uses a shared "creation account" from `READYMODE_CREATE_USER` / `READYMODE_CREATE_PASSWORD` env vars ([readymode_users.py:44-45](../../backend/api/readymode_users.py#L44-L45), with a hardcoded fallback in code — see the security note below), falling back to the calling user's own personal ReadyMode credentials via `config.get_user_readymode_credentials()`. Everything else in VOS (audits, downloads) always uses the personal-credential path.

**The per-dialer gotcha, and why delete mostly dodges it:** folder and role/OU ids are **per-dialer**, not shared across the 7 `resvaN` tenants — a real incident, already diagnosed and fixed once for create: [`RESVA4_RESVA5_CREATE_FAILURE.md`](RESVA4_RESVA5_CREATE_FAILURE.md). "Agents" is folder id `48-36-14` on resva/resva2/resva3, `54-109-` on resva4, `54-105-14` on resva5, `48-36-4` on resva6/resva7. The captured delete contract (`/Folders/fileAction/Delete/User=<uid>`) doesn't reference a folder or OU id at all, so it sidesteps that specific problem — but the underlying principle still applies one level up: **a `uid` is only meaningful on the dialer it came from.** You still need the right dialer's uid for the user you're targeting; you just don't need a separate folder-id resolution step the way create does.

**Update, 2026-09-01 — this is now closed.** `ReadyModeHTTPClient.list_folder_users(folder_id)` `POST`s `Folders/Folder=<id>` (the generic Folders-app "open folder" action, same family as the delete endpoint above) and parses **every** account in that folder from the returned HTML — confirmed live on resva4's Agents folder (1215 users, all parsed correctly), not limited to accounts with recent call activity the way `userlist` is. `delete_users_on_dialer` now falls back to scanning every writable folder via this method when `resolve_agent_id()` can't find a name in `userlist` — closing the exact gap this section used to describe (an account with zero calls couldn't be deleted by name at all). See [`READYMODE_DUPLICATE_DETECTION_WORKFRAME.md`](READYMODE_DUPLICATE_DETECTION_WORKFRAME.md) for the full writeup, including the one part of this that's inferred rather than fully proven (the short-id/long-id derivation for folder ids).

---

## What a delete feature would need

1. **`ReadyModeHTTPClient.delete_user(uid)`** in `automation/readymode_http.py` — simpler than `create_user()`: just
   `self.session.get(f"{self.dialer}/Folders/fileAction/Delete/User={uid}")` on the existing authenticated session,
   checking the response the way `create_user()` checks its JSON (once the actual success/failure body shape is
   confirmed — see "Not yet confirmed" above). Add a `ReadyModeUserDeleteError` alongside the existing
   `ReadyModeLoginError` / `ReadyModeUserCreateError`. Unlike create, there's no folder/OU to resolve first — the
   request only needs a `uid`.
2. **A way to target a user** — either accept a `uid` directly, or add a `list_users()` / `find_user()` method (its own
   small recon, likely scraping the Manage Users page the same way `get_writable_folders()` scrapes the embedded
   `tmp.uMgmtWritableFolders` blob) so a caller can go from a name/login-id to a `uid` on a given dialer.
3. **Orchestration** mirroring `create_readymode_users.py` — per-dialer login, loop targets, and reuse the
   per-(account, dialer) locking pattern already built for audits in
   [`backend/api/readymode.py:59-99`](../../backend/api/readymode.py#L59-L99) (`_dialer_locks`) so a delete run can't
   collide with a concurrent audit/create run on the same dialer + account. Note create-user doesn't currently use
   this lock either — worth adding to both, but especially delete.
4. **An API route**, gated with `get_current_admin_user` (or stricter) from the start — see the security note below
   for why this matters more here than it did for create.
5. **UI** to pick a dialer + target user(s) — depends on point 2, since there's currently no way to browse existing
   users to pick from.
6. Add the confirmed contract to `docs/READYMODE_HTTP_SPEC.md` alongside login/report/create.

---

## Security note (pre-existing, not introduced by this)

The current create-user route has **no server-side role check** — just `Depends(get_current_user)` ([readymode_users.py:34](../../backend/api/readymode_users.py#L34)). The only gate is the frontend hiding the "Users" tab from non-Owner/Admin roles (`TAB_ROLES['Users']` in [`webapp/src/App.tsx:31`](../../webapp/src/App.tsx#L31)) — anyone with a valid VOS login and the right URL could call it directly today. Compare to VOS's own internal user-delete route, which does gate server-side: [`backend/api/settings.py:293-297`](../../backend/api/settings.py#L293-L297), `Depends(get_current_admin_user)` plus a tenancy check.

A ReadyMode delete route is destructive against a production platform — it shouldn't repeat create's gap. This is a pre-existing issue on a live route, not something this task introduces; worth fixing on its own regardless of whether/when delete gets built.

---

## How this was captured (2026-09-01)

Logging into ReadyMode and driving its UI isn't something Claude does on its own — that part was manual, same as it would be for anyone reverse-engineering a third-party UI:

1. Mohamed logged into `resva4.readymode.com` directly in his own Chrome (Claude never touched the login form or credentials).
2. Claude drove the already-authenticated session from there via the Claude-in-Chrome browser tool: navigated Team → Manage Users, found "Auditor1" (a real, actively-used QA account — its Activity Log showed same-day sign-ins and audit work) and confirmed with Mohamed that it should **not** be the test target.
3. Mohamed created a genuinely disposable account (`deletest`) and performed the actual drag-to-trash + "Are you sure?" confirmation himself — Claude does not perform permanent-delete actions itself even when explicitly authorized to, the same way it won't handle credentials, so this step stayed manual throughout (including a retry, the first attempt was dragged in a different Chrome tab than the one being watched).
4. Claude read the browser's network log for that tab afterward and found the request in §"The captured contract" above.

**Remaining follow-ups**, not yet done (see "Not yet confirmed" above for detail): capture the response body and required headers directly (e.g. a minimal authenticated request against a deliberately-invalid uid, to see the failure shape), check the "Show/hide deleted users" toggle to determine if this is a soft or hard delete, and confirm the URL generalizes across the other 6 `resvaN` dialers.

---

**Bottom line:** ReadyMode delete-user isn't implemented in VOS yet, but it's no longer blocked — the real contract is `GET /Folders/fileAction/Delete/User=<uid>`, captured live and confirmed working against resva4. What's left is mechanical: build `delete_user()` mirroring `create_user()`'s structure (simpler, since there's no folder/OU to resolve), wire it through an admin-gated route, and add a UI to pick a target user. The open items above (response-body shape, soft- vs hard-delete) are worth resolving before shipping this against real accounts, but don't block starting the implementation.
