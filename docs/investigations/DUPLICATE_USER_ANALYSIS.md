# Duplicate User — Investigation

**Question:** Is it possible to create a duplicate user in the app?
**Date:** 2026-06-16
**Scope:** Two distinct creation paths — (A) internal VOS app users, (B) ReadyMode bulk user creation.

---

## TL;DR

| Path | Duplicate possible? | Why |
|------|--------------------|-----|
| **A. VOS app user** | **No** | DB `UNIQUE` constraint + `user_exists()` pre-check + whitelist `ON CONFLICT` |
| **B. ReadyMode bulk** | **Yes (possible)** | No VOS-side dedup or existence check — relies entirely on ReadyMode server to reject |

---

## A. VOS App User Creation — PROTECTED

**Flow:** `POST /api/settings/users` → `create_user()` → `user_manager.add_user()`

Three layers of protection:

1. **DB unique constraint** — `users.username VARCHAR(255) UNIQUE NOT NULL`
   ([cloud-migration/init.sql:14](../../cloud-migration/init.sql#L14), [docs/sql/SUPABASE_SCHEMA_INIT.sql:11](../sql/SUPABASE_SCHEMA_INIT.sql#L11))
2. **Pre-check** — `add_user()` calls `user_exists()` and returns `False` if found
   ([lib/dashboard_manager.py:830-832](../../lib/dashboard_manager.py#L830-L832))
3. **Unique-violation catch** — even on a TOCTOU race, the INSERT fails and is caught, no fallback insert
   ([lib/dashboard_manager.py:896-898](../../lib/dashboard_manager.py#L896-L898))
4. **Whitelist** — uses `INSERT ... ON CONFLICT (email) DO UPDATE`, so re-submitting just updates
   ([backend/services/user_service.py:71-78](../../backend/services/user_service.py#L71-L78))

**Result:** Re-creating an existing email → `add_user()` returns `False` → API returns `400 "Failed to create user"`. No duplicate row.

### Minor inconsistency (not a duplicate)
`create_user()` upserts the **whitelist row first**, *then* calls `add_user()`. If `add_user` fails because the user already exists, the whitelist row was already silently updated (role / readymode creds overwritten) even though the API reports failure.
[user_service.py:67-90](../../backend/services/user_service.py#L67-L90)

---

## B. ReadyMode Bulk User Creation — NO VOS-SIDE GUARD

**Flow:** `POST /api/readymode-users/create` → `create_users_multi_dialer()` → per-dialer loop → `client.create_user()`

There is **no deduplication and no existence check anywhere in VOS** for this path:

1. **Frontend zips 3 parallel textareas by index** (names / login_ids / passwords), no dedup of `login_id`
   ([webapp/src/pages/UsersPage.tsx:80-99](../../webapp/src/pages/UsersPage.tsx#L80-L99))
2. **Backend loops the list as-is** — one POST per row, no "does this login_id already exist?" check
   ([automation/create_readymode_users.py:47-71](../../automation/create_readymode_users.py#L47-L71))
3. **Same list is sent to every selected dialer in parallel** — by design (same agent across dialers), not a true duplicate
   ([automation/create_readymode_users.py:74-109](../../automation/create_readymode_users.py#L74-L109))

**Whether a duplicate is actually created depends entirely on the ReadyMode server:**
- If ReadyMode **rejects** a duplicate `u_account`, it returns `{"error": ...}` → raised as `ReadyModeUserCreateError` → row marked `failed`. No duplicate.
  ([automation/readymode_http.py:217-220](../../automation/readymode_http.py#L217-L220))
- If ReadyMode **does not reject** it, a duplicate account **is created** — VOS does nothing to stop it.

### Concrete ways a duplicate attempt happens
- Same `login_id` entered twice in the input (typo / paste) → submitted twice to each dialer.
- An agent that already exists on the dialer is included in the list → re-creation attempt.

---

## Recommendations (suggestions only — not implemented)

| # | Fix | Path | Impact |
|---|-----|------|--------|
| 1 | Dedup `login_id` client-side before submit; warn on collisions | B (frontend) | Low effort, stops accidental double-paste |
| 2 | Dedup the `users` list server-side in `create_users_on_dialer` | B (backend) | Defensive, cheap |
| 3 | Surface ReadyMode's "already exists" error clearly as a distinct status (e.g. `skipped`) vs generic `failed` | B | Better UX, clarity |
| 4 | Move whitelist upsert to *after* `add_user()` succeeds (or wrap in one transaction) | A | Removes the silent-overwrite inconsistency |

**Bottom line:** App users are safe. ReadyMode bulk creation has no VOS-side duplicate protection — it trusts ReadyMode to reject duplicates, and does not dedup its own input.
