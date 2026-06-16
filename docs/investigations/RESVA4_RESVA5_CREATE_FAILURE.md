# ReadyMode User Creation Fails on resva4 / resva5 — Tested Diagnosis

**Date:** 2026-06-16
**Symptom:** Bulk ReadyMode user creation shows a red ✗ for dialers `resva4` and `resva5`; users are not created there. Other dialers (resva, resva2, resva6, resva7) work.

---

## Test method (live, read-mostly)

Probe scripts using the production creation account `UserCreation` / `RES370@370`:

| Script | What it does |
|--------|--------------|
| `scripts/probe_creation_login.py` | Login-only, all dialers |
| `scripts/probe_create_attempt.py` | One real create attempt on resva4 + resva5 (default folder/OU) |
| `scripts/probe_orphan_check.py` | Checks whether the failed attempt left an orphan user |

---

## Results

### 1. Login works on ALL dialers (incl. resva4/resva5)
```
OK resva   OK resva2   OK resva4   OK resva5   OK resva6   OK resva7
```
→ **Not** a credentials / login problem. The new `UserCreation` account authenticates everywhere.

### 2. The CREATE step fails on resva4/resva5
Raw ReadyMode response (the `detail` the UI hides):
```
resva4 → [{'uid': 1651, 'uname': 'ZZ VOS Probe',
           'details': "Failed to create user 'ZZ VOS Probe' at creation step 2", 'error': ''}]
resva5 → [{'uid': 1731, ... 'details': "...at creation step 2", 'error': ''}]
```
- Login fine, request well-formed, but ReadyMode rejects **"creation step 2"**.
- A `uid` is allocated (step 1) but step 2 fails.

### 3. No orphan left behind
The probe user does **not** appear in the report userlist on either dialer → the failed step-2 create rolls back (caveat: report userlist may filter, so not absolute).

---

## CONFIRMED ROOT CAUSE (100% — proven with live data)

Two follow-up tests nailed it:

1. Retry with `ou='inherit'`, `folder=''` → both dialers returned **`'Missing folder data'`** → folder is mandatory and the value is what's being rejected.
2. Scraped each dialer's createUser page (`tmp.uMgmtWritableFolders` JSON blob) → the **"Agents" folder ID differs per instance**:

| Dialer | "Agents" folder ID | Hardcoded `48-36-14` valid? |
|--------|--------------------|------------------------------|
| resva  | `48-36-14`  | ✅ (why it works) |
| resva4 | `54-109-`   | ❌ |
| resva5 | `54-105-14` | ❌ |

(`Admin` happens to share `46-33-2` across instances; `Agents` does not.)

### Full sweep — Agents folder ID on every dialer (resva→resva7)

| Dialer | Agents folder ID | Hardcoded `48-36-14` works? |
|--------|------------------|------------------------------|
| resva  | `48-36-14`  | ✅ |
| resva2 | `48-36-14`  | ✅ |
| resva3 | `48-36-14`  | ✅ |
| resva4 | `54-109-`   | ❌ |
| resva5 | `54-105-14` | ❌ |
| resva6 | `48-36-4`   | ❌ (`-4`, not `-14`) |
| resva7 | `48-36-4`   | ❌ |

**4 of 7 dialers are broken** by the single hardcoded ID — not just the two originally reported. resva6/resva7 fail identically the moment they're used.

The code hardcodes resva's "Agents" ID (`48-36-14`) for every dialer → invalid on resva4/resva5 → "creation step 2" fails.

**Folder data source for the fix:** `tmp.uMgmtWritableFolders = [{"name":"Agents","id":"54-109-"}, ...]` is embedded directly in the `/Team/ManageUsers/createUser` page HTML — trivially parseable per dialer.

---

## Original hypothesis (now superseded by the confirmed cause above)

The bulk creator sends a **hardcoded** folder + OU to **every** dialer:
- `folder = "48-36-14"`, `ou = "4"` ([webapp/src/pages/UsersPage.tsx:9](../../webapp/src/pages/UsersPage.tsx#L9), defaults at [UsersPage.tsx:67](../../webapp/src/pages/UsersPage.tsx#L67))
- passed straight through ([create_readymode_users.py:51-56](../../automation/create_readymode_users.py#L51-L56) → [readymode_http.py:191-200](../../automation/readymode_http.py#L191-L200))

But **folder and OU IDs are per-instance** — each `resvaN` subdomain is a separate ReadyMode account ([config.py:34-42](config.py#L34-L42)). The IDs `48-36-14` / `4` exist on resva/resva2 (where it works) but **not** on resva4/resva5, so "step 2" (folder/team/OU assignment) fails there.

This is the **same per-dialer-config gotcha** already documented for disposition IDs (id 96 = "Spanish Speaker" on resva2 but "Decision Maker" on resva3 — [readymode_http.py:109-113](../../automation/readymode_http.py#L109-L113)).

> Not yet ruled out: a per-instance **seat/license limit** on resva4/resva5 could also fail at "step 2". Decisive test: retry one create with `ou="inherit"` + `folder=""` — if it succeeds, folder/OU is confirmed as the cause.

---

## Secondary finding — UI hides the reason
The failure detail is captured server-side but never shown. The table renders only the dialer name ([UsersPage.tsx:555](../../webapp/src/pages/UsersPage.tsx#L555)); streamed `log` lines are ignored ([UsersPage.tsx:221-227](../../webapp/src/pages/UsersPage.tsx#L221-L227)). That's why this looked like a mystery.

---

## FIX IMPLEMENTED (2026-06-16) — dynamic per-dialer folder resolution

The folder is now sent by **name** and resolved to each dialer's own id at creation:

- `ReadyModeHTTPClient.get_writable_folders()` / `.resolve_folder(name)` parse `tmp.uMgmtWritableFolders` per dialer (cached) — [readymode_http.py](../../automation/readymode_http.py)
- `create_users_on_dialer()` resolves the folder name after login; a user whose folder doesn't exist on that dialer fails with a clear `"Folder 'X' not found on <dialer> (available: ...)"` message instead of a cryptic "step 2" error — [create_readymode_users.py](../../automation/create_readymode_users.py)
- Frontend `FOLDER_OPTIONS` now send names; default `Agents` — [UsersPage.tsx](../../webapp/src/pages/UsersPage.tsx)
- `BulkUserRow.folder` default → `"Agents"` — [schemas.py](../../backend/models/schemas.py)

**Validated live** (`scripts/probe_validate_fix.py`) — `resolve_folder('Agents')` returns the correct id on all 7 dialers:
```
resva 48-36-14  resva2 48-36-14  resva3 48-36-14
resva4 54-109-  resva5 54-105-14  resva6 48-36-4  resva7 48-36-4   → ALL MATCH
```

> **Still unverified:** whether the role/OU id `4` (Sales) is valid on resva4–resva7. The proven blocker was the folder; OU may also be per-instance. A single live create on resva4 would confirm the full pipeline end-to-end.

---

## Original recommended fix (now done — see above)

| # | Fix | Effort |
|---|-----|--------|
| 1 | **Resolve folder by NAME → per-dialer ID** at creation: parse `tmp.uMgmtWritableFolders` from each dialer's `/Team/ManageUsers/createUser` page, map the chosen folder name (e.g. "Agents") to that dialer's id. Source located — now Low/Medium effort | Low–Med |
| 2 | **Surface the error `detail`** in the UI (render `detail` + show `log` lines) | Low |
| 3 | Quick stopgap: let the user pick the correct folder/OU per dialer | Low |

**Bottom line:** Credentials are fine. resva4/resva5 fail because the hardcoded folder `48-36-14` / OU `4` don't exist on those instances — folder/OU must be resolved per-dialer.
