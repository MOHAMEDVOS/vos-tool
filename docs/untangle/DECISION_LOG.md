**Status: Step 5 complete — full pass done** (2026-11-07). Step 5 ran as a fresh, independent
re-scan (5 subagents told not to read the prior findings first) plus a fix wave on everything it
found. Caught and fixed: an incomplete owner-email consolidation (backend/api/auth.py and
settings.py were never updated to use the new shared constant — now fixed), a live ReadyMode
credential hardcoded in 3 scripts and committed to git history (removed from source; **rotating
the actual password is still the user's job**), a real latent bug in audio channel-extraction
(>2-channel audio was silently corrupting voice-activity detection — now fixed), a caller that
silently dropped warnings, several more duplicate-helper consolidations, and more dead-code/import
cleanup. Full tally for the whole session: see bottom of this file.

Two small user-visible changes worth a look, both flagged by the subagent that made them rather
than decided silently: Call Review's "No Rebuttals" badge now reads "No Rebuttal" (matching the
string used elsewhere as a functional filter/export label, not just cosmetic); one dashboard's
confirm-dialog lost a `text-center` class that had no visible effect in its layout.

`lib/campaign_metrics.py` and `lib/optimized_pipeline.py` — deleted on your call (2026-11-07).
Both were fully-built but had zero external callers anywhere in the live app.

Still open, deliberately not touched: the database schema-mechanism consolidation, which needs a
dedicated pass against a real database rather than a quick autonomous fix.

# VOS Untangle — Decision Log (Step 3)

Source material: `docs/untangle/raw/01-*.md` through `10-*.md` — 10 chunks, every file in
`lib/`, `backend/`, `automation/`, `audio_pipeline/`, `processing/`, `webapp/src/`,
`scripts/`, `tools/`, `models/`, `analyzer/` read in full, ~300 individual findings.
Not covered yet (by design, per the skill's own ordering): `tests/` and comment cleanup —
those are Step 4 actions done last, once the structural fixes below land.

Each fix below is written **above** the problems it resolves, per the skill's format.
Findings inside protected files (`dashboard_manager.py` user/audit/quota logic,
`security_utils.py`, `backend/api/auth.py`, `backend/core/database.py`/`security.py`,
`quota_service.py`/`user_service.py`, `App.tsx` routing, `LoginPage.tsx`) are marked
`[PROTECTED]` — included because the user explicitly approved touching them.

---

## Active bugs found along the way

These aren't just structural debt — they're live correctness problems, listed here so
they don't get lost inside the bigger redesign below.

1. **Production "semantic" rebuttal check has been silently degraded to a dumb keyword list.**
   `SemanticAudioProcessor` — the class actually wired into every "heavy" single-file audit
   (`backend/services/audio_service.py:139`) — never finishes initializing its real detection
   engine (`audio_pipeline/semantic_audio_processor.py:35-73`, dead code, never called), so it
   always falls back to an 11-phrase hardcoded list. No error, just quietly worse grading.
2. **Same class silently breaks late-hello detection on every heavy audit.** A dropped argument
   (`semantic_audio_processor.py:204`) raises `AttributeError`, swallowed into `'Error'`.
3. **The admin quota-redistribution tool silently does nothing.** `tools/quota_redistribution.py`
   writes to `quota_manager`'s private in-memory dict; `_save_quota_data` never persists that
   dict to Postgres. The `/redistribution/apply` endpoint returns success regardless.
4. **A Groq/LLM API failure gets recorded as a genuine "no rebuttal found."** `analyzer/
   llm_rebuttal_evaluator.py`'s fallback response is never distinguished from a real verdict by
   its caller (`rebuttal_detection.py:2177-2202`) — inverts this codebase's own "silent miss over
   false positive" rule and can blame an agent for a rate limit.
5. **Two divergent user-delete paths in `dashboard_manager.py`**, one of which silently skips
   quota cleanup due to a mismatched import (`from quota_manager import` instead of `from
   lib.quota_manager import`, wrapped in a bare `except`).
6. **`GET /api/jobs/{job_id}` has a latent `NameError`** — `backend/api/jobs.py` calls `get_job()`
   but only imports `create_job, update_job`.
7. **All 6 endpoints in `backend/api/health.py` swallow their own intended error.** Each raises a
   deliberate `HTTPException(503, ...)` inside a `try` whose `except Exception` re-catches it and
   re-raises a generic 500 — the real status/message never reaches the caller.
8. **`reset_user_to_isolated` in `dashboard_manager.py` never does anything.** It reads a
   "sharing mode" dict that's reconstructed empty on every load and never written — always sees
   the hardcoded default and always takes the no-op branch.
9. **Clearing agent-audit data doesn't refresh the sidebar's flagged-call badge.**
   `AgentAuditDashboard.tsx:26` invalidates query key `'badge-count'`; the badge itself is keyed
   `'flagged-count'` (`useDashboard.ts:60`). The other two dashboards have this right.
10. **The "Attention Required" row highlight in the agent dashboard does nothing.**
    `AuditTable.tsx` never reads the `getRowClassName` prop it declares.
11. **Call Review is missing a badge Actions has.** `CallCard`'s issue list has no Long VM/Dead
    branch; `ActionsPage`'s equivalent does — same underlying data, already-diverged duplicate.
12. **Two live, incompatible password-hashing systems**, confirmed exactly where CLAUDE.md's
    known issue lives: `backend/core/security.py` (unsalted SHA256) vs `lib/security_utils.py`
    (salted PBKDF2, already correct). `dashboard_manager.py`'s own password check is a dead stub —
    not the source of the known issue.
13. **`SECRET_KEY`/`JWT_SECRET` placeholder fallbacks are still never rejected at startup**
    (confirmed live: `backend/core/config.py:71-72`, `config.py:292-293`).
14. **Rate limiting is fully built and completely disabled** (confirmed: `rate_limit.py` has zero
    live callers; wiring is commented out in `main.py` with a Railway-cache-issue note).

---

## Fixes (the one fix behind several problems)

### Tier 1 — isolated correctness fixes (small, do these first)

**Fix: check `source` before trusting `rebuttal_detected`.**
In `analyzer/rebuttal_detection.py`'s caller of `llm_rebuttal_evaluator`, treat
`source == "llm_evaluation_failed"` as "LLM result unknown," not "LLM said no" — don't let it
clear existing semantic match candidates.
- Resolves: Bug #4 above (`llm_rebuttal_evaluator.py:514-516,537-545`, `rebuttal_detection.py:2177-2202`).

**Fix: repair `SemanticAudioProcessor`.**
Either wire up `_ensure_models_loaded` for real, or — given 3 sibling processors already exist —
delete the semantic path and have this class explicitly document itself as keyword-only until
someone wires it up on purpose. Fix the dropped `agent_audio` arg. Add the missing `else` branch
so a temp-file failure returns an error dict instead of `None`.
- Resolves: Bugs #1, #2 above, plus the missing-`else` `None`-return
  (`audio_pipeline/semantic_audio_processor.py:35-73,204,208-305`).

**Fix: route `quota_redistribution.py` through the public API.**
Call `lib/quota_manager.py:571 adjust_user_quota()` instead of poking
`_load_quota_data()`/`_save_quota_data()` directly.
- Resolves: Bug #3 above (`tools/quota_redistribution.py:144,150-156`).

**Fix: correct the import in `jobs.py`.**
Add `get_job` to the import line.
- Resolves: Bug #6 (`backend/api/jobs.py:8,91`).

**Fix: let `health.py`'s 503s reach the caller.**
Catch `HTTPException` separately (re-raise unchanged) before the generic `except Exception` in
all 6 handlers.
- Resolves: Bug #7 (`backend/api/health.py:25-186`, all 6 endpoints).

**Fix: three one-line frontend corrections.**
`AgentAuditDashboard.tsx:26` → invalidate `'flagged-count'`, not `'badge-count'`. `AuditTable.tsx`
→ actually apply `getRowClassName` to the `<tr>`. `CallCard` (`CallReviewPage.tsx`) → add the
Long VM/Dead branch `ActionsPage.tsx:277-283` already has.
- Resolves: Bugs #9, #10, #11.

**Fix: decide what `reset_user_to_isolated` should do, then make the phantom dict real or delete it.**
This one needs a product call (what *should* resetting sharing mode do?) before touching
[PROTECTED] `dashboard_manager.py:2168-2205` — flagging rather than just picking an answer.

**Fix: `setCurrentUser` in `badgeStore` — confirm intent.**
Either call it at login so the per-user "seen" partition the code already promises actually
happens, or delete the promise (and the dead `currentUser` plumbing) if one shared bucket per
browser is fine. Small, but a product call, not a mechanical one.
- Relates to: `store/badgeStore.ts:5-32`.

### Tier 2 — delete confirmed-dead code (grep-verified, low risk, big LOC win)

**Fix: delete the orphaned "optimizer" cluster.**
`lib/cpu_optimizer.py`, `simple_cpu_optimizer.py`, `parallel_processor.py`,
`enhanced_parallel_processor.py`, `audio_optimizer.py` — ~960 lines, zero live callers outside
the cluster itself (confirmed via repo-wide grep in `02-lib-audio-perf.md`).

**Fix: delete the dead half of `analyzer/rebuttal_detection.py`.**
`DataIngestionLayer`, `PreprocessingPipeline`, `TranscriptionEngine`,
`merge_segments_to_dialogue`, `PhoneticAdaptationLayer`'s 800+-entry dict, `ValidationFramework`,
`RebuttalDetectionModule` — confirmed unused outside the file; roughly half the file.

**Fix: delete dead automation/audio_pipeline code.**
`download_readymode_calls_playwright.py`'s ~1,100 unused lines plus its own duplicate function
defs; `audio_pipeline.OptimizedAudioProcessor` (whole class, never instantiated);
`processing/model_preloader.py` (whole file, already disabled); `audio_pipeline/detections.py`'s
dead `run_audit`; `AudioProcessor.process_batch`/`convert_to_dataframe_format`/
`convert_all_to_dataframe_format`.

**Fix: delete dead webapp decorative/streaming code.**
`AICanvasBackground.tsx`, `LoginCanvasBackground.tsx`, `ShockwaveOverlay.tsx`,
`AtmosphericOrbs.tsx` (~480 lines, unimported remnants of an earlier login design), the dead
`useAuditStream()` hook body, `Button`'s unused `destroy`/`ghost` variants.

**Fix: delete dead `lib/google_workspace.py` features.**
`build_docs`, `copy_template_doc`, `replace_doc_placeholders`, `style_report_doc`,
`create_scoring_spreadsheet`, `retry_api_call` — zero callers anywhere.

**Fix: delete Streamlit-era and half-removed-feature leftovers.**
`logging_config.setup_frontend_logging`, `html_sanitizer.safe_markdown`, `dashboard_manager.py`'s
`STREAMLIT_AVAILABLE`/`st` branches, the dead `verify_user_password` stub + the
`app_pass_hash`/`app_pass_salt` columns it was the only reader of, the never-instantiated
`TransactionManager`, `models/manager.py`'s ~95 unreachable Whisper lines + duplicate `return`,
`backend/core/config.py`'s unreachable Pydantic-V1 `Settings` class.

### Tier 3 — architectural redesigns (the real "untangling")

**Fix: one role/permission table for the webapp.**
Replace `App.tsx`'s `TAB_ROLES`, `Sidebar.tsx`'s `ALL_ITEMS` roles, `SettingsPage.tsx`'s
`SIDEBAR_NAV.forRoles`, and the ~7 scattered `role === 'X'` checks (`UsageCard`, `DashboardPage`,
`AuditPage`, `TlActionsPage`, `CreateUser`, `EditUser`, `ManageUsers`) with one
`canAccess(role, feature)` used everywhere a role decision is made.
- Resolves: all 10 "what can this role do" duplicates in `08-webapp-pages-shell.md`.

**Fix: one "is this call flagged" definition.**
Compute it once — ideally backend-side, shipped to the frontend as a field on the row — instead
of reimplementing it in `dashboard_service.get_flagged_calls`, `campaign_report_export._is_flagged`
(missing 2 of 4 conditions the first has), and `utils/audit.ts isRowFlagged` (mirrored again
across 3 dashboard components, and already violated once in the same file by `detectionVariant`).
- Resolves: the flagged-call duplication across backend + frontend; ties to the project's own
  `[[rebuttal-flag-polarity]]` memory.

**Fix: one quota-management surface — CORRECTED after investigation.**
Re-checked callers before merging: `DashboardManager.remove_user_with_quota` turned out to have
**zero callers anywhere** — it's `UserManager.remove_user` (with the broken import) that's the
live path, called via `backend/services/user_service.py`. So this isn't a merge, it's: fix
`remove_user`'s broken import, delete the dead `remove_user_with_quota`, and merge the 3 "protect
owner" checks + 2 owner-email allow-lists into one. Dispatched as part of the dashboard_manager.py
Tier 3 pass.
- Resolves: [PROTECTED] `dashboard_manager.py:1005-1076,1619-1669,717,724`, `quota_manager.py:718,819`.

**Schema-definition mechanism — INVESTIGATED, NOT ATTEMPTED.**
The original plan ("retire the hand-written schema in favor of Alembic alone") turned out to be
unsafe: Alembic's migrations only cover 4 narrow, recent additions (a `readymode_recordings`
table, some worker-secret columns) — the actual `users` table and most core schema exist ONLY via
the hand-written `CREATE TABLE` block and the `cloud-migration/*.sql` files. Retiring either of
those without first writing a complete Alembic baseline migration would break schema creation on
any fresh database (new Railway environment, new dev DB). The genuine overlap worth resolving is
narrower than first scoped — just the hand-written Python path vs. the SQL-file path, both of
which define `users` independently. This needs a dedicated pass tested against a real database,
not an autonomous Tier 3 fix — left alone for now. CLAUDE.md's "No database migration system →
Add Alembic" known issue also appears to already be done (Alembic is wired up and running), just
incomplete in coverage — worth updating that known-issues list once you've seen this.

**Fix: one password-hashing module — CORRECTED after investigation, turned out to be a safe deletion.**
Checked both "systems" for live callers before touching anything: `backend/core/security.py`'s
`hash_password`/`verify_password` (unsalted SHA256) had **zero callers anywhere in the repo**,
not even in tests — this app authenticates entirely via Google OAuth, so there was never a second
live password-hashing system, just a vestigial one sitting next to `lib/security_utils.py`'s real
salted-PBKDF2 implementation (which is actually used, for encrypting per-user API keys). Deleted
the dead pair directly — no migration needed since nothing live read or wrote a password hash
through it. Directly resolves CLAUDE.md known issues #1, #3, #5, and suggests that known-issues
list may be stale and worth a fresh look.

**Fix: one SSE-stream helper, each side.**
Backend: one async generator helper replacing the 6 copies in 3 styles across
`backend/api/readymode_users.py`/`scoring.py`/`readymode.py` (only 2 of 3 styles even handle
client disconnect). Frontend: one `useSSEStream` hook replacing `UsersPage.tsx`'s 6 inline copies,
the 3 parsers in `api/readymode.ts`/`scoring.ts`, and the already-dead `useAuditStream` hook.

**Fix: one "normalize a Yes/No/boolean detection value" helper + reconcile severity tiers.**
Replace `dashboard_manager.py`'s 5 independent normalizers with one; make
`campaign_metrics.classify_issue_rating` and `dashboard_manager._rating_from_ratio` agree at the
boundary (currently 50%/0.5 is "Medium" in one, "High" in the other).

**Fix: one "find busiest dialer" implementation in `AuditPage.tsx`.**
Campaign-mode and agent-mode currently duplicate this feature; agent-mode has a staleness guard
(`agentDialerCheckIsCurrent`) campaign-mode is missing. Share one implementation, keep the guard.

**Fix: honest module boundaries for automation/.**
`readymode_http.py` isn't pure HTTP — it transitively pulls in Chromium via
`readymode_browser_login.py`. Either rename/document that honestly, or make the browser fallback
an explicit, separately-imported call so the 6 caller scripts that claim "pure HTTP, no browser"
in their own docstrings are telling the truth. Alongside that: consolidate the 3x "build full
roster," 4x "per-dialer threadpool," and 3x "dialer-name-from-url" copies across
`automation/*.py` into the one shared helper most files already use.

**Fix: reconcile `phrase_learning.py`'s two diverged implementations.**
The two "merge duplicate phrases" methods disagree on tie-break order; the two "reload embeddings
after write" paths disagree on error handling. Pick one of each.

### Smaller independent fixes (no shared theme — one-liners)

- `app_settings_manager.py`: make the JSON-upsert escaping consistent across its 3 write paths.
- `database.py`/`db_health_monitor.py`: fix the `record_query_execution`→`log_query` name
  mismatch; have `database.py` own setting `self.health_monitor` instead of relying on whichever
  module happens to import it.
- `migration_lock.py`: the 1-hour stale-lock window is a product call, not a mechanical fix —
  flagging rather than changing it.
- `scripts/migrate_campaign_from_agent.py`: wrap the insert-then-delete in a transaction so a
  rerun after a partial failure can't double-insert.
- `lib/webdriver_manager.py`: an untracked planning doc already in this repo's working tree
  (`docs/superpowers/plans/2026-10-29-remove-chrome-readymode-connector.md`) suggests this whole
  module may already be scheduled for removal — worth checking with you before investing further
  here.

---

## What's next

Tests (`tests/`) and comment cleanup are Step 4 work, done last per the skill, once the fixes
above land — that's when the "remove restating comments" / "clean up weak tests" add-ons you
chose actually apply.
