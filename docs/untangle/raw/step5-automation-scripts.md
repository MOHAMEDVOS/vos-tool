# Step 5 re-scan — automation/, scripts/, tools/, models/

Fresh read-through after today's refactor (dead code deletion, roster/threadpool
helper consolidation into `automation/readymode_http.py`, docstring/comment cleanup).
Read-only pass; nothing fixed.

## Special Cases (most important first)

- **`scripts/probe_disposition_fetch.py:18-19`, `scripts/probe_disposition_map.py:23-24`,
  `scripts/probe_validate_fix.py:12-13`** — a real ReadyMode account's plaintext
  username/password (REDACTED — see git history prior to this fix) is hardcoded and **committed to
  git** (`git ls-files` confirms all three are tracked; first added in commit
  `e4a8d9c`). This is the single most important finding in this scan: a live
  credential sitting in source control, copied identically into three files (so
  rotating it means remembering to fix three places, none of which say so — also a
  Hidden Link). Should be rotated and pulled from env/DB like every other script in
  `scripts/` already does (`probe_audit_csv.py`, `probe_campaign_field.py`).
- **`scripts/migrate_campaign_from_agent.py:102-108`** — one-time migration that
  `DELETE`s rows from `agent_audit_results` right after inserting them into
  `campaign_audit_results`, with no `--apply`/dry-run gate and no transaction
  wrapping insert+delete together (unlike its sibling `backfill_dialer_names.py`,
  which has both). If the delete runs on a subset of a bigger write failure, rows are
  gone with no safety net and no way to tell dry-run from live run before executing.
- **`scripts/restore_db_data.py:67-82`** — bare `except Exception: pass` inside the
  per-row restore loop for `agent_audit_results` / `lite_audit_results` /
  `campaign_audit_results`; a row that fails to insert is silently dropped with zero
  logging, so a partial restore looks identical to a complete one in the script's own
  output.
- **`scripts/restore_db_data.py:39,91`** — reads `cloud-migration/db_backup.json` and
  `cloud-migration/phrases_backup.json`; neither file exists in the repo (`ls
  cloud-migration/` shows only `deploy.sh`, `init.sql`, `kubernetes/`,
  `migration_schema.sql`, `monitoring/`). The script silently no-ops those sections
  (caught by its own `except`) if the files aren't there, so it's unclear whether this
  script still does anything useful or is a leftover from one past cloud migration.
- **`automation/readymode_http.py:117-131` (`DISPOSITION_TYPE_IDS`)** — a hardcoded
  disposition-label→id map captured from exactly one dialer (resva2) that is
  documented as wrong on other dialers (id 96 means different things on resva2 vs
  resva3). It's a last-resort fallback, well-commented, but is still a special case
  baked into a "general" module that every downstream caller has to know is
  per-dialer-unreliable.
- **`models/manager.py:109-112`** — hardcoded absolute path `/app/hardcoded_embeddings.pkl`
  with a bare `if not os.path.exists(...)` fallback to a relative path; a special case
  for one deployment layout (Railway container) living in otherwise-general model
  loading code.

## Hidden Links

- **`automation/download_readymode_calls_playwright.py:68-93` (`get_next_run_counter`)
  vs. `automation/download_readymode_calls.py:81-106`** — byte-for-byte identical
  function (same body, same comments) in both files. Nothing marks them as copies; a
  bugfix to one (e.g. the counter-parsing edge case) won't propagate to the other.
- **`automation/download_readymode_calls_playwright.py:26-30` (`_env_flag`) vs.
  `automation/readymode_browser_login.py:72-76`** — identical helper duplicated
  between the two files that already import from each other (`readymode_browser_login`
  imports `login_to_readymode` from the playwright file), so the duplication isn't
  even saving an import — it's just an unlinked copy.
- **`scripts/backfill_dialer_names.py:56-58` (`derive_dialer_from_path`)** — docstring
  states it's "a mirror of `processing.batch_engine.extract_dialer_name_from_path`,
  kept standalone." That's an intentional, acknowledged hidden link, but still one: if
  the real extraction logic in `processing/batch_engine.py` changes (e.g. a new folder
  naming convention), this script's copy silently goes stale and a future backfill run
  would derive the wrong dialer name with no warning.
- **`scripts/rebuttal_eval/rules.py` / `scripts/rebuttal_eval/test_rules.py`** —
  `replay_production.py`'s own docstring calls this out: "not a parallel
  re-implementation like rules.py/test_rules.py." `rules.py` is a from-scratch
  re-encoding of objection/rebuttal cue regexes that overlap heavily with
  `analyzer/rebuttal_detection.py` and `analyzer/objection_gate.py`'s real production
  regexes. The overlap is deliberate (it's an experimentation harness, explicitly
  flagged as such), but a production regex change still won't be reflected here unless
  someone remembers to port it by hand.
- **`scripts/probe_audit_csv.py:29-38` and `scripts/probe_campaign_field.py:24-31`** —
  near-identical hand-rolled `.env` parsing loop (`for line in env_path.read_text()...
  k, _, v = line.partition("=")`) copied across probe scripts instead of using
  `python-dotenv` (already a dependency) or a shared helper.
- **`automation/download_readymode_calls.py:114-132`
  (`extract_dialer_name_from_url`) vs. `automation/readymode_http.py:148-150`
  (`dialer_name_from_url`)** — two functions that answer the same question
  (dialer name from URL) with different edge-case behavior, explicitly documented at
  the call site as "overlaps... deliberately kept separate." Documented, but still two
  places that must be remembered whenever a new malformed-URL case shows up, and the
  comment itself notes `backend/api/readymode.py` imports this one directly, outside
  this consolidation's visibility.

## Needless Links

- **`automation/download_readymode_calls_playwright.py`** as a whole is now a
  dependency of `automation/readymode_browser_login.py` purely for `login_to_readymode`
  + `ReadyModeLoginError` (confirmed via grep — nothing else in the file is imported
  from outside it). The browser-login fallback module (stable, narrowly-scoped: "solve
  one Cloudflare challenge") now has to tolerate whatever happens to the rest of that
  file (its unused download orchestration code, its own `MAX_CONCURRENT_DOWNLOADS`
  env-var parsing, its own `USERNAME`/`PASSWORD` module globals) even though none of it
  is used by the thing depending on it.

## Surplus

- **`automation/download_readymode_calls_playwright.py`** — of its 7 top-level
  defs/classes, only `login_to_readymode` and `ReadyModeLoginError` are imported
  anywhere else in the codebase (confirmed by grep across the repo). Dead/unused in
  place:
  - `ReadyModeNoCallsError` (class, line 37) — never imported elsewhere, never raised
    by the one function (`login_to_readymode`) still in use.
  - `_sanitize_path_component` (line 63) — zero callers anywhere in the repo.
  - `get_next_run_counter` (line 68) — unused in this file's own remaining logic
    (`login_to_readymode` never calls it); the live copy is
    `download_readymode_calls.py`'s own (see Hidden Links above).
  - Module-level `USERNAME`/`PASSWORD` (lines 22-23) — read only by
    `login_to_readymode`'s defaults, but that function is always called with explicit
    `readymode_user`/`readymode_pass` from `readymode_browser_login.py`, so these
    env-var reads are themselves effectively unreachable fallback paths.
  - `MAX_CONCURRENT_DOWNLOADS` / `_max_downloads_env` (lines 51-60) — not referenced by
    anything else in the file (the download loop that would have used it was removed
    in the HTTP rewrite); the real one lives in `download_readymode_calls.py`.
  This whole file reads like the pre-HTTP-rewrite downloader that was supposed to
  shrink down to just the login-form logic `readymode_browser_login.py` actually needs,
  but the shrink never happened — a half-done piece of today's (or an earlier) refactor.
- **`scripts/probe_audit_csv.py`**, **`scripts/probe_campaign_field.py`**,
  **`scripts/probe_disposition_fetch.py`**, **`scripts/probe_disposition_map.py`**,
  **`scripts/probe_validate_fix.py`** — five one-off exploration/validation scripts
  whose own docstrings say the question they were written to answer is already
  answered (e.g. `probe_campaign_field.py`'s docstring literally lists which fields
  are "✓" confirmed and says this probe finds the last unknown one; `probe_audit_csv.py`
  is finding fieldKeys that are presumably now hardcoded into
  `readymode_http.export_call_log_csv`'s default `fields=` tuple). None are imported by
  anything else, none are referenced from docs or CI. They're historical scratch work
  with no future reason to change — candidates to move to `scratch/` or delete (and
  definitely to strip the hardcoded credentials from first, regardless).
- **`scripts/migrate_campaign_from_agent.py`** and **`scripts/restore_db_data.py`** —
  one-time migration/restore scripts; `migrate_campaign_from_agent.py`'s docstring says
  "one-time migration," and it has presumably already run (last touched Oct 28 in a
  broad "Update audit, ReadyMode, and TL Actions workflows" commit, not a recent
  migration run). Kept indefinitely with no indication of whether they're still safe to
  re-run (migrate script isn't idempotent against partial failure — see Special Cases).

## Not reflagging (already known / accepted)

- `models/manager.py`'s module-level `_SEMANTIC_MODEL` / `_SEMANTIC_EMBEDDINGS`
  globals are a textbook Hidden Link (every caller depends on load-order and the
  background-thread reload racing with reads), but this is a pre-existing singleton
  pattern spanning `audio_pipeline/`, `backend/main.py`, `lib/wrong_dispo_detector.py`,
  `lib/phrase_learning.py`, and `analyzer/rebuttal_detection.py` — out of this scan's
  four directories on its own merits, noted here only because `models/manager.py` is
  in scope and is the thing being depended on.

## Counts

- Special cases: 6
- Hidden links: 6
- Needless links: 1
- Surplus: 7 (1 file + 5 probe scripts + 2 migration/restore scripts, grouped above)
