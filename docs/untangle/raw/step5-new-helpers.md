# New helpers from today's refactor — Problems (Step 5 check pass)

Scope: the 6 new/consolidated abstractions named in this pass — `webapp/src/utils/permissions.ts`,
`webapp/src/utils/sseStream.ts`, `backend/core/sse.py`, the `fetch_all_folder_users` /
`run_per_dialer` helpers in `automation/readymode_http.py`, `lib/dashboard_manager.py`'s
`convert_detection_to_string` call sites + `lib/quota_manager.py`'s merged owner-email constant,
and `backend/services/dashboard_service.py`'s `is_call_flagged` + its use from
`campaign_report_export.py`. Read-only analysis, no fixes proposed.

## Hidden Links

- `automation/delete_readymode_users.py:41` calls `fetch_all_folder_users(client)` with no `log`
  argument, while the two sibling callers of the same new helper —
  `automation/find_duplicate_readymode_users.py:42` and
  `automation/find_inactive_readymode_users.py:71` — both pass `log`. `fetch_all_folder_users`
  (`automation/readymode_http.py:949`, `notify = log or (lambda msg: None)`) silently drops every
  "WARN  Could not list writable folders" / "WARN  Could not list folder '<name>'" message for the
  delete path specifically. A user running Delete's folder-scan fallback (`_resolve_by_folder_scan`,
  `automation/delete_readymode_users.py:32-44`) against a dialer with a broken folder gets no log
  line at all for that failure, while the identical failure during a Duplicates or Inactive scan is
  reported — nothing in the shared helper's signature flags that one of its three callers forgot to
  wire the optional parameter through.
- `lib/dashboard_manager.py:629-631` comment claims the owner identity is now "Sourced from
  lib.quota_manager so there is one shared owner identity constant instead of separate copies per
  file" (`PROTECTED_OWNER = PROTECTED_OWNER_EMAIL`), but `backend/api/auth.py:82` and
  `backend/api/auth.py:101` still hardcode their own independent literal
  `"mohamedibrahimpayonner@gmail.com"`, and `backend/api/settings.py:225` still hardcodes its own
  independent literal `"Mohamed Abdo"` — neither references `lib.quota_manager.PROTECTED_OWNER_EMAIL`
  or `OWNER_EMAILS` in any way. The consolidation comment describes a merge that happened inside
  `dashboard_manager.py` only; the two call sites that actually gate "is this the protected owner"
  for login/role-escalation (`auth.py`) and for settings (`settings.py`) were never pointed at the
  new constant, so a future change to the owner's email still has to be made in (at least) three
  places by hand, same as before the refactor — the new constant just adds a fourth place that looks
  authoritative but isn't read by the two most security-relevant call sites.
- `lib/dashboard_manager.py:39-48` — the `try: from lib.quota_manager import ... PROTECTED_OWNER_EMAIL`
  / `except ImportError: PROTECTED_OWNER_EMAIL = "mohamedibrahimpayonner@gmail.com"` fallback
  re-hardcodes the exact same literal that `lib/quota_manager.py:30` defines. Change the email in
  `quota_manager.py` and forget this fallback, and the two only diverge silently if the import ever
  fails (quota system unavailable) — an untested path with no test covering it.
- `backend/api/readymode_users.py:23` — `import backend.api.readymode  # noqa: F401` is kept
  purely for its side effect (installing the thread-local `sys.stdout` proxy at
  `backend/api/readymode.py:38-39`), with a comment saying this file needs that proxy installed
  "before we start worker threads." But all four of this file's workers
  (`backend/api/readymode_users.py:56-74,111-129,152-169,199-218`) always construct and pass an
  explicit `log_callback` into their `automation.*` functions, and every one of those functions'
  stdout fallback (e.g. `automation/create_readymode_users.py:30-34`, `log()`'s `else: print(msg)`
  branch) is therefore unreachable from this file — confirmed by grep, the only caller of
  `create_users_multi_dialer` / `delete_users_multi_dialer` /
  `find_duplicate_users_multi_dialer` / `find_inactive_users_multi_dialer` anywhere in the codebase
  is this one file, always with a callback. The import-for-side-effect dependency on
  `readymode.py`'s module-load order is now needless: nothing in this file's own code path still
  needs the proxy it exists to install.

## Needless Links

- `webapp/src/utils/sseStream.ts`'s `checkOk` and `onParseError` options are each exercised by
  exactly one caller category. `checkOk: true` is passed only by `webapp/src/api/scoring.ts:79,109`
  (the only caller of `readSSEStream` with a `checkOk` — everything in
  `webapp/src/pages/UsersPage.tsx:364,413,460,508,574,632` relies on the `false` default). Likewise
  `onParseError` is supplied only by `webapp/src/api/scoring.ts:85-88,119-122`; none of
  `UsersPage.tsx`'s six call sites pass one, relying on the default silent-ignore. The helper's own
  doc comment (`sseStream.ts:8-12,17-21`) already names this as "matches call sites that never
  checked `res.ok`" / "every current caller treats a malformed line... this way" — i.e. the
  general-purpose shape was explicitly shaped around the two caller styles that existed at
  consolidation time, not a general contract; a third future caller has to go read both existing
  callers to know which combination of options is "the scoring style" vs "the bulk-ops style."
- `backend/core/sse.py`'s `run_sse_stream(..., keepalive=...)` is only ever passed explicitly as
  `keepalive=False`, and only by the four `readymode_users.py` call sites
  (`backend/api/readymode_users.py:74,129,169,218`); `backend/api/scoring.py:215,370` and
  `backend/api/readymode.py:545` never pass it, relying on the `True` default. Same shape as the
  `checkOk`/`onParseError` case above on the Python side of the same new abstraction: the parameter
  exists in a general helper but in practice encodes "which of the three pre-refactor styles is this
  caller" rather than a choice each caller reasons about independently.
- `backend/core/sse.py:97` (`poll_interval: float = 0.2`) is never overridden by any of the 7 call
  sites across `scoring.py`, `readymode.py`, and `readymode_users.py` — confirmed by grep, no
  `poll_interval=` appears anywhere outside the helper's own definition. A parameter with one value
  in practice; see also Surplus below.

## Surplus

- `backend/services/campaign_report_export.py:27-31` (`_is_flagged`) is a pure pass-through wrapper
  around `backend.services.dashboard_service.is_call_flagged` — same signature, same return value,
  no added behavior, just a local name and a comment explaining why it delegates. The module already
  imports `is_call_flagged` directly at line 15; `_select_report_rows` (line 39) could call
  `is_call_flagged(row)` itself with one fewer level of indirection and the same guarantee the
  comment is trying to document (the import line already states it).
- `backend/core/sse.py:97` `poll_interval` — see Needless Links; as a parameter nobody ever varies,
  it's speculative generality the helper didn't need to expose yet (every caller hard-codes trust in
  the "0.2s matches every existing copy" default cited in the docstring at line 117).
- `lib/dashboard_manager.py:2398,2402` call `convert_detection_to_string(record.get('Releasing
  Detection', 'No'), default='No')` / `(record.get('Late Hello Detection', 'No'), default='No')` —
  the `.get(key, 'No')` already guarantees a non-`None` string is passed in, so
  `convert_detection_to_string`'s own `if value is None: return default` branch (line 228-229) can
  never fire for these two call sites; the `default='No'` argument here is unreachable dead weight,
  left over from merging this call site with the ones at `dashboard_manager.py:2081-2083,2525-2526,
  2602,2607` that *do* call `.get(key)` with no inline default and need the function's own default
  handling. Harmless (both forms produce the same result today, since the inline default and the
  function default are both `'No'`), but it's two different calling conventions for the same merged
  function with no comment explaining why, and a future edit to one of the two defaults can silently
  diverge from the other without any test catching it.

## Special Cases

- `lib/quota_manager.py:31` — `OWNER_EMAILS = ["Mohamed Abdo", PROTECTED_OWNER_EMAIL,
  "mohamedabdo@res-va.com"]` merges three structurally different identifiers (a display name, an
  email, a second, different email) into one list under a name that promises emails. Both of this
  list's only two read sites (`lib/quota_manager.py:699,793`) do a flat `username in OWNER_EMAILS`
  membership check against whatever string is passed as `username` — per the existing
  backend-api findings (`backend/api/auth.py:126` stores users keyed by email), it is not
  established that `"Mohamed Abdo"` (a display name, matching `backend/api/settings.py:225`'s
  separate, unmigrated check) is ever the value actually compared here; this list reads like three
  previously-separate special-cased literals (one per legacy call site) concatenated into a single
  list rather than genuinely unified around one identity.
- `lib/dashboard_manager.py:655-661` (`UserManager._is_protected_owner_variant`) always
  `return False` — a method that exists, is presumably still called somewhere expecting the old
  "variant" behavior, but has been special-cased down to a permanent no-op as part of the "relaxed
  rules" described in its own docstring (lines 656-660), rather than being removed along with
  whatever `PROTECTED_VARIANTS` (line 635, now permanently `[]`) used to drive. Not evaluated
  further than this file per scope, but flagging as a dead branch left behind by the owner-identity
  consolidation.

## Not flagged

- `webapp/src/utils/permissions.ts` — read in full plus its three call sites
  (`webapp/src/App.tsx`, `webapp/src/pages/SettingsPage.tsx`, and
  `webapp/src/components/layout/Sidebar.tsx`, checked in addition to the two named in scope since it
  gates the same tabs). Every `Feature` the type defines is read by at least one real call site
  (verified by grepping all 18 feature strings against `webapp/src`); `App.tsx` and `Sidebar.tsx`
  independently gate the same tabs but both go through `canAccess` with no duplicated role tables —
  this is the abstraction doing its job, not a hidden link. No needless or surplus findings in this
  file.
- `backend/core/sse.py` itself (as opposed to its callers, covered above) — the module's own code is
  internally consistent with its own docstring's description of the three pre-refactor styles it
  replaces; the safety-net `except Exception` in `_thread_target` (lines 124-134) is explicitly
  documented as a backstop, not a silent special case.

## Counts

- Hidden Links: 4
- Needless Links: 3
- Surplus: 3
- Special Cases: 2
