# automation — Problems (Step 2)

Scope: the 8 files in `automation/` — `readymode_http.py`, `readymode_browser_login.py`,
`download_readymode_calls.py`, `download_readymode_calls_playwright.py`,
`create_readymode_users.py`, `delete_readymode_users.py`,
`find_duplicate_readymode_users.py`, `find_inactive_readymode_users.py`.

**On the graphify signal / the "pure HTTP" claim:** confirmed false as stated. Every file
in this folder calls `ReadyModeHTTPClient.login()`, and `readymode_http.py:390-393`
lazily imports `readymode_browser_login.py`, which launches a real Playwright/Chromium
browser (`readymode_browser_login.py:188-253`) whenever a Cloudflare challenge is
detected. `playwright>=1.40.0` is a real, installed dependency (`requirements.txt:44`),
not a dead optional branch. `readymode_http.py` also carries retry/sleep logic, ~130
lines of diagnostic/egress logging, and a hardcoded voicemail-blocking business rule —
all inside a module whose own docstring (`readymode_http.py:1`) calls it a "pure-HTTP
... client." This, plus the duplication below, is consistent with the god-object shape
graphify flagged (40 edges, #4 most-connected node).

## Hidden Links

- `readymode_http.py:1-14` vs `readymode_http.py:390-393` — the module docstring claims
  "Pure-HTTP ReadyMode client"; `login()` silently imports and can delegate to a full
  browser-automation module (`readymode_browser_login.py`) on a Cloudflare challenge.
  Nothing in the six caller files that each separately claim "pure HTTP, no browser"
  (`create_readymode_users.py:1`, `delete_readymode_users.py:1`,
  `find_duplicate_readymode_users.py:1`, `find_inactive_readymode_users.py:1`,
  `download_readymode_calls.py:1`) shows that calling `.login()` can launch Chromium.
- `readymode_http.py:86-87` defines `ReadyModeLoginError`; `download_readymode_calls_playwright.py:45-46`
  defines a second, unrelated `ReadyModeLoginError(Exception)` with no shared base.
  `readymode_browser_login.py:169-172` has to import the latter under an alias
  (`PlaywrightLoginError`) and `readymode_http.py:401-406` manually translates it back
  into the first class at the boundary. A bare `except ReadyModeLoginError` anywhere
  else in the codebase will not catch the Playwright one.
- Three independent copies of "build a full user roster from every writable folder":
  `delete_readymode_users.py:29-59` (`_resolve_by_folder_scan`),
  `find_duplicate_readymode_users.py:32-67` (`_build_roster`),
  `find_inactive_readymode_users.py:60-90` (`_build_full_roster`). All three call
  `get_writable_folders()`, convert ids via `resolve_folder_listing_id()`, and fan out a
  `ThreadPoolExecutor` over `list_folder_users()` — into three different result shapes.
  `find_inactive_readymode_users.py:62-64` names the other two copies in a comment, so
  the duplication is known and still unfactored.
- Four independent copies of "run per-dialer work in a `ThreadPoolExecutor`, collect
  `as_completed`, and hand-build a failure placeholder matching the happy-path shape":
  `create_readymode_users.py:97-132`, `delete_readymode_users.py:164-199`,
  `find_duplicate_readymode_users.py:124-158`, `find_inactive_readymode_users.py:190-210`.
  Each failure-placeholder dict must independently be kept in sync with its own
  function's normal-result shape, and with the other three files' pattern.
- The `log(msg)` "use callback or print" shim is copy-pasted six times:
  `create_readymode_users.py:29-33`, `delete_readymode_users.py:75-79`,
  `find_duplicate_readymode_users.py:82-86`, `find_inactive_readymode_users.py:110-111`,
  and again at `find_inactive_readymode_users.py:187-188` (twice in the same file).
- Dialer-short-name extraction exists as three separate implementations with different
  edge-case behavior: `readymode_http.py:138-140` (`dialer_name_from_url`, used by
  create/delete/find_duplicate/find_inactive), `download_readymode_calls.py:110-119`
  (`extract_dialer_name_from_url`, its own copy), and
  `download_readymode_calls_playwright.py:117-127` (a third copy, itself redefined again
  at `:288-297`). `download_readymode_calls.py` is the one file that reimplements this
  instead of importing the shared helper every sibling file uses.
- `readymode_http.py:107-121` (`DISPOSITION_TYPE_IDS`) is a frozen copy of one dialer's
  (resva2, captured 2026-06-15) live disposition config, explicitly documented as wrong
  for other dialers, used as a silent fallback when the live per-dialer fetch fails.
  Nothing checks whether this snapshot has since drifted from resva2 itself — only the
  comment keeps it "in sync."
- `automation/.env.example` documents a config surface the code no longer reads, and
  omits the one it does: `CHROMEDRIVER_PATH`, `CHROME_PROFILE_DIR`, `RECORDINGS_DIR`,
  `MAX_DOWNLOAD_RETRIES`, `RETRY_DELAY`, `MAX_ALL_USERS_DURATION_MINUTES`,
  `MAX_SINGLE_AGENT_DURATION_MINUTES` appear nowhere in the 8 `automation/*.py` files
  (Selenium/chromedriver-era leftovers); the env vars the code actually reads —
  `READYMODE_PROXY_URL` (`readymode_http.py:324`), `READYMODE_LOGIN_DIAGNOSTICS`
  (`readymode_http.py:274`), `READYMODE_EGRESS_DIAGNOSTICS` (`readymode_http.py:294`),
  `READYMODE_BROWSER_FALLBACK`/`READYMODE_HEADLESS`/`READYMODE_SLOW_MO_MS`/
  `READYMODE_BROWSER_LOGIN_ATTEMPTS` (`readymode_browser_login.py:80,174-180`),
  `MAX_CONCURRENT_DOWNLOADS` (`download_readymode_calls.py:70`) — are not in it at all.
- `readymode_browser_login.py:56-59` writes a `.png`/`.html` debug-snapshot pair with a
  shared filename stem. `backend/api/readymode.py:959` (outside `automation/`) assumes
  that pairing when building the `.html` URL for every `.png` it lists. The directory
  itself is shared correctly (`backend/api/readymode.py:943` imports `_debug_dir()`
  directly), but the pairing convention is not — only both sides independently agreeing
  on it.
- `readymode_http.py:904-910` (`resolve_folder_listing_id`) is explicitly documented as
  "not yet verified ... on every dialer/folder" — yet `delete_readymode_users.py:42`,
  `find_duplicate_readymode_users.py:48`, and `find_inactive_readymode_users.py:73` all
  call it and trust the result for deletion, duplicate-detection, and inactivity
  decisions with no additional check.

## Needless Links

- `readymode_http.py:390-393` — the stable "pure HTTP" transport (40-edge god node per
  graphify) imports `readymode_browser_login.py`, which itself imports
  `download_readymode_calls_playwright.py:169-172` to reuse its Playwright form-filling.
  The HTTP client now transitively depends on Chromium, stealth-patching JS, and
  Turnstile pixel-click heuristics — all more volatile than anything an HTTP client
  needs, so a ReadyMode login-page DOM change or a Playwright API change can now break
  what's supposed to be the simple path.
- `block_voicemail` is a parameter only one caller/workflow understands:
  `disposition_type_ids()` (`readymode_http.py:1037-1038`) and `all_type_ids()`
  (`readymode_http.py:1069`) default it `True`; `export_call_log_csv()`
  (`readymode_http.py:496-499`) is the one caller that overrides it to `False`, because
  the analytics/reachability CSV path must see voicemail rows while never downloading
  audio. Every download-path caller must simply remember never to flip it — nothing
  distinguishes "may legitimately include voicemail" from "must never include
  voicemail" beyond convention and comments.
- `claim_recordings_callback` / `release_recordings_callback` / `registry_run_id` /
  `force_reaudit` (`download_readymode_calls.py:370-382` signature, `:326-332`,
  `:442-476` the claim/release closures) are re-audit-registry vocabulary threaded
  through the general download orchestrator. These four parameters and the bookkeeping
  built around them are only meaningful to one external caller; the function's core job
  (log in, page through a report, download files) has to carry this unrelated
  bookkeeping on every call for that one workflow's sake.
- The audio-duration "hard floor" (`MIN_CALL_DURATION_S`, `_probe_duration_seconds`, the
  whole strict-mode filter, `download_readymode_calls.py:122-209`) lives inside the
  ReadyMode download orchestrator, even though deciding which calls are too short to be
  analytically meaningful (per the comment at `:122-125`, this is about
  releasing/late-hello/rebuttal detection) is a detection-pipeline concern. If that rule
  changes for detection reasons, this "talk to ReadyMode" module changes too.

## Surplus

- `download_readymode_calls_playwright.py` is ~1,100+ lines of dead code out of 1,539.
  Only `login_to_readymode` (`:130-280`) and the file's own `ReadyModeLoginError`
  (`:45-46`) are imported anywhere else in the repo, exclusively by
  `readymode_browser_login.py:169-172`. `_download_single_dialer_call_recordings`
  (`:359-1446`), the second `download_single_file` (`:300-357`),
  `_read_manifest`/`_merge_dialer_downloads` (`:1448-1489`), and this file's own
  `download_all_call_recordings` (`:1491-1539`) have no caller anywhere in the repo
  outside this file.
- `format_agent_name_for_filename` and `extract_dialer_name_from_url` are each defined
  twice in the same file (`download_readymode_calls_playwright.py:108-114` and again
  `:283-286`; `:117-127` and again `:288-297`). The first definition of each is
  unreachable the instant the module finishes importing — pure dead code.
- `keep_browser_open`, `driver_storage`, `call_type` on `download_all_call_recordings`
  (`download_readymode_calls.py:376,378,374`) are, per the function's own docstring
  (`:387-388`), "accepted for backward compatibility but are no longer used" — not read
  anywhere in the function body.
- `automation/.env.example` (whole file) documents configuration nothing reads —
  `CHROMEDRIVER_PATH`, `CHROME_PROFILE_DIR`, `RECORDINGS_DIR`, `MAX_DOWNLOAD_RETRIES`,
  `RETRY_DELAY`, `MAX_ALL_USERS_DURATION_MINUTES`, `MAX_SINGLE_AGENT_DURATION_MINUTES` —
  left from a Selenium/chromedriver-era version of this tool. (Same evidence as the
  Hidden Links entry above; listed here too because, independent of staleness risk, it's
  also just config for a setting that no longer exists.)

## Special Cases

- `readymode_http.py:58-65,68-83` — `_request_with_retries` (3 attempts, 3s sleep) is
  written for one specific observed network path ("a home-laptop Tailscale tunnel ... a
  brief Wi-Fi blip"), baked permanently into the general login path.
- `readymode_http.py:389-414` — a Cloudflare-challenge indicator gets a full
  browser-automation fallback; the sibling "security block" indicator
  (`readymode_http.py:37-40`, also detected by `_security_block_indicators`) is logged
  but never gets any special handling — an `if` for one of two detected values.
- `readymode_http.py:713-761,797-811` — the `AGENT_REPORT_PRESET="P134"` two-step (and
  sometimes three-step) POST dance: the first POST is known to ignore the requested date
  range, so a second is always sent, and a third is retried once more if the echoed
  range still doesn't match — a workaround for one observed ReadyMode server quirk,
  generalized into a blanket policy for every dialer.
- `readymode_browser_login.py:120-147` — `_attempt_turnstile_click` clicks Cloudflare
  Turnstile's checkbox by raw pixel offset (`box["x"] + 30`, line 133) because a
  selector-based click can't reach inside the iframe; the comment admits this is "a
  deliberate, informed choice to try it anyway rather than a reliable fix."
- `readymode_browser_login.py:174-180` — the browser-login retry count is capped at 2,
  specifically because "`login_to_readymode`'s own form-wait runs ~60s per attempt" — an
  attempt count special-cased to this one expensive call rather than a general policy.
- `download_readymode_calls_playwright.py:647-650` and `:792-796` — a hardcoded substring
  check for one specific NPS survey prompt ("On a scale of 0-10"), dismissed with a
  blind `page.mouse.click(10, 10)`, duplicated at both the campaign- and agent-filter
  retry loops.
- `download_readymode_calls_playwright.py:634-759,776-852` — `for attempt in range(3)`
  retry loops around campaign/agent dropdown selection, each wrapping bare
  `except:`/`except Exception:` blocks that are swallowed and retried rather than
  inspected.
- `download_readymode_calls.py:28-55` — a module-level `try/except ImportError` whose
  only job is tolerating two different ways of importing this same module
  (`automation.download_readymode_calls` vs bare `download_readymode_calls`),
  duplicating a 9-symbol import list to do it.
- `download_readymode_calls.py:400-408` (duplicated at
  `download_readymode_calls_playwright.py:386-396`) — if the configured
  `RECORDINGS_ROOT` isn't writable, silently fall back to `/tmp/Recordings`, an
  ephemeral path that likely doesn't survive a container restart — a silent, lossy
  fallback for one failure mode.
- `readymode_http.py:640-652` — `delete_user`'s docstring acknowledges the response
  body's shape on success vs. failure "was not captured," so a non-2xx status is
  "currently the only confirmed failure signal" — a known gap accepted as-is rather than
  resolved.
