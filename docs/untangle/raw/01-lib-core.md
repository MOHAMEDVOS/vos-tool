# lib-core — Problems (Step 2)

Scope: lib/dashboard_manager.py, lib/quota_manager.py, lib/database.py, lib/db_health_monitor.py,
lib/security_utils.py, lib/migration_lock.py, lib/app_settings_manager.py, lib/path_utils.py,
lib/logging_config.py, lib/timeout_utils.py, lib/campaign_metrics.py, lib/scoring_audit.py,
lib/scoring_sampler.py, lib/html_sanitizer.py, lib/webdriver_manager.py.

Read-only analysis. No code changed. [PROTECTED] marks findings inside dashboard_manager.py's
user/audit/quota logic or security_utils.py, per CLAUDE.md's "don't touch without approval" list.

## Hidden Links

- [PROTECTED] `lib/quota_manager.py:718` and `lib/quota_manager.py:819` hardcode two *different*
  owner-email allow-lists (`["Mohamed Abdo", "mohamedibrahimpayonner@gmail.com", "mohamedabdo@res-va.com"]`
  vs `["Mohamed Abdo", "mohamedibrahimpayonner@gmail.com"]` — the second is missing the third email),
  and both overlap conceptually with `lib/dashboard_manager.py:717`/`:724` (`UserManager.PROTECTED_OWNER`,
  set once as a class attribute and redundantly again in `__init__`). Worse, the actual quota
  *enforcement* check in `record_user_usage` (`lib/quota_manager.py:738-758`) never consults any
  owner-email list at all — it compares straight against whatever `daily_quota` is stored in the DB.
  "Owner gets unlimited quota" is not a real system property, just three independent, already-drifted
  special cases, one of which (enforcement) doesn't even participate.
- [PROTECTED] `lib/dashboard_manager.py:1048` does `from quota_manager import quota_manager` (no
  `lib.` prefix) inside `UserManager.remove_user`, while every other call site in the same file/class
  — e.g. `:42`, `:1409` — uses `from lib.quota_manager import quota_manager`. The mismatched import is
  wrapped in a bare `except Exception` (`:1058-1060`) that silently skips quota cleanup on every user
  deletion that goes through `remove_user`.
- [PROTECTED] Two independent, divergent user-deletion paths exist: `UserManager.remove_user`
  (`lib/dashboard_manager.py:1005-1076`, role-checked, deletes via `DELETE FROM users`, quota cleanup
  broken per the item above) and `DashboardManager.remove_user_with_quota` (`:1619-1669`), which does
  **not** call `remove_user` at all — it re-implements its own "protect the owner" check (`:1647-1657`,
  a third copy of the same compound condition) and its own quota cleanup (working, via the correctly
  imported top-level `quota_manager`), then deletes the user by loading the *entire* users dict,
  `del`-ing one key (`:1660`), and calling `save_all_users()`, which — per its own docstring at `:896`
  ("Individual user operations should use add_user/update_user") — round-trips every *other* existing
  user through `update_user()` just to remove the one.
- [PROTECTED] The "migration in progress → block writes" guard is copy-pasted near-verbatim at 8+ call
  sites in `lib/dashboard_manager.py`: `save_all_users` (`:882-891`), `add_user` (`:914-923`),
  `remove_user` (`:1007-1016`), `update_user` (`:1080-1089`), `create_user_with_quota` (`:1557-1566`),
  `save_agent_audit_results` (`:2255-2265`), `save_lite_audit_results` (`:2606-2615`),
  `save_campaign_audit_results` (`:3255-3264`) — but is silently absent from other write paths in the
  same classes (`set_user_dashboard_mode`, `create_sharing_group`/`remove_sharing_group`/
  `update_sharing_group`, `increment_daily_download_count`, `clear_lite_audit_data`,
  `clear_agent_audit_data`, `clear_campaign_audit_data`). "Read-only during migration" is not actually
  enforced consistently — it depends on whether whoever wrote that method remembered to paste the block.
- [PROTECTED] In `create_user_with_quota` (`lib/dashboard_manager.py:1556-1578`), the migration-lock
  boilerplate was pasted *before* the method's own triple-quoted string, so that string is no longer a
  docstring — `create_user_with_quota.__doc__` ends up empty. Direct, visible cost of the copy-pasted
  block above.
- [PROTECTED] `add_user`'s NOT-NULL-violation error handler (`lib/dashboard_manager.py:995-997`) logs
  `app_pass_hash`/`app_pass_salt`, but neither name is ever assigned anywhere in `add_user` — leftover
  from password-hashing removal ("Password handling removed (OAuth only)", `:1146`) that never got
  cleaned out of this branch. Hitting this branch would raise `NameError`, masking the real DB error.
- [PROTECTED] Dashboard "sharing mode" is tracked two incompatible ways. The real one: a per-username
  DB column read/written directly by `get_user_dashboard_mode`/`set_user_dashboard_mode`
  (`lib/dashboard_manager.py:2102-2139`), used everywhere (`create_sharing_group:1976`,
  `remove_sharing_group:2008`, `update_sharing_group:2050/2058`, `sync_group_user_modes:2092`). The
  phantom one: a `user_dashboard_mode` dict nested in the same table's JSON-blob 'global' row, always
  reconstructed as `{}` by `_load_sharing_config` (`:1907-1931`, see `:1922`/`:1928`/`:1931`) and never
  written by `_save_sharing_config` (only persists `sharing_groups`, `:1939`). `reset_user_to_isolated`
  (`:2168-2205`) operates entirely on the phantom dict, so `current_mode` is always the hardcoded default
  `"isolated"` (`:2180`) and the method's only branch (`:2182`) can never be taken — it always falls
  through to `return False` and does nothing.
- [PROTECTED] At least three independent reimplementations of "normalize a Yes/No/boolean-ish value" in
  one file: the module-level `convert_detection_to_string` (`lib/dashboard_manager.py:213-270`), an
  inline duplicate inside `save_lite_audit_results` (`:2640-2660`), the nested `normalize_detection_value`
  defined inside `get_combined_lite_audit_data`'s per-row loop (`:2785-2803`, redefined every iteration),
  and two more near-identical nested normalizers `normalize_releasing`/`normalize_late_hello` further
  down the same method (`:2888-2905`).
- The same Low/Medium/High severity-tiering rule (30%/50% cutoffs) is implemented independently in
  `lib/campaign_metrics.py:41-47` (`classify_issue_rating`, percentage scale, `pct <= 50` → "Medium")
  and `lib/dashboard_manager.py:54-59` (`_rating_from_ratio`, ratio scale, `ratio < 0.5` → "Medium") —
  and they have already diverged at the boundary: exactly 50%/0.5 is "Medium" in one, "High" in the other.
- `lib/database.py`'s `execute_query`/`execute_values_batch` read `self.health_monitor`
  (`DatabaseManager.__init__`, `:123`, "Will be set by health monitor module"), but it is only ever set
  by a *different* module reaching back in: `lib/db_health_monitor.py:421`
  (`db_manager.health_monitor = _health_monitor`, inside `get_health_monitor()`). Nothing in
  `database.py` enforces or signals this. Any caller that only imports `get_db_manager()` — which is
  exactly what `lib/quota_manager.py:19` and `lib/app_settings_manager.py:14` do — runs with
  `health_monitor` permanently `None`, and all the logging/alerting in `database.py` that depends on it
  is silently dead for that whole process.
- `lib/database.py`'s `execute_values_batch` calls `self.health_monitor.record_query_execution(...)`
  (`:656`, `:674`) — but `DatabaseHealthMonitor` (`lib/db_health_monitor.py:36-397`) has no method by
  that name; it has `log_query` instead. The call is wrapped in a bare `except Exception: pass`
  (`database.py:661-662`, `:679-680`) that silently swallows the resulting `AttributeError` every time
  this batch-insert path runs with a health monitor attached. The two APIs drifted and nothing noticed.
- `lib/database.py:156` (`_init_postgresql`) does `from lib.database import _parse_database_url` —
  the module importing a function from itself via its own dotted path instead of calling the
  module-level function directly.
- Two separate, duplicated `DatabaseManager()` construction blocks in `lib/database.py`: the lazy
  singleton inside `get_db_manager()` (`:760-767`) and the eager "initialize on import if DB_TYPE is
  set" block (`:770-774`). Both must independently stay correct; whichever runs first wins, and the
  eager block never runs at all when `DB_TYPE` isn't set.
- `lib/database.py`'s `retry_on_db_error` decorator decides whether an error is retryable by
  substring-matching its string message (`'pool' in error_str or 'exhausted' in error_str or 'timeout'
  in error_str ...`, `:70-72`) — this couples retry behavior to the exact wording of psycopg2/stdlib
  error messages, with nothing to flag it if a library upgrade changes that wording.
- The "where does persistent app data live" problem is solved once, properly, in `lib/path_utils.py`
  (env var → Docker-detection → fallback chain, `:8-76`) — but `lib/database.py:262`,
  `lib/migration_lock.py:28`, `lib/app_settings_manager.py:27`, and [PROTECTED] `lib/dashboard_manager.py:725`
  (`UserManager.base_dir`) and `:1803` (`DashboardManager.base_dir`) each independently hardcode a bare
  relative `Path("dashboard_data...")` instead of reusing it.
- `lib/app_settings_manager.py`'s INSERT…ON CONFLICT upsert into `app_settings` is written out three
  separate times (`_save_settings:140-149`, `set_setting:191-198`, `update_category:229-236`), and the
  JSON-serialization step is subtly different between them: `_save_settings` always does
  `json.dumps(value)` (`:148`), while `set_setting`/`update_category` use
  `json.dumps(value) if not isinstance(value, str) or not value.startswith('{') else value`
  (`:190`, `:228`) — a string value that happens to start with `{` is stored unescaped by two of the
  three write paths but not the third.
- `lib/app_settings_manager.py` stores each default twice: once in `self.default_settings` (`:39-71`)
  and again as a literal fallback in each convenience getter — `get_vad_threshold` hardcodes `600`
  (`:286`) vs `:41`; `get_vad_min_duration` hardcodes `120` (`:290`) vs `:42`; `get_rebuttal_sensitivity`
  hardcodes `0.68` (`:294`) vs `:47`; `get_semantic_threshold` hardcodes `0.68` (`:298`) vs `:51`;
  `get_default_daily_limit` hardcodes `5000` (`:302`) vs `:54`; `is_accent_correction_enabled` hardcodes
  `True` (`:306`) vs `:49`; `is_maintenance_mode` hardcodes `False` (`:310`) vs `:69`.
- `lib/quota_manager.py:18-24` and `lib/app_settings_manager.py:12-19` each copy-paste the identical
  `try: from lib.database import get_db_manager; DB_AVAILABLE = True / except ImportError:
  DB_AVAILABLE = False` guard rather than sharing one.
- `lib/scoring_sampler.py:137-147`'s agent-name matching (`_match_key`) is, by its own docstring
  ("mirrors resolve_agent_id"), a duplicate of `automation/readymode_http.resolve_agent_id` (outside
  this file set) — the two must stay in lockstep purely by convention.
- `lib/scoring_audit.py:60-69` (`_detected_flags`) and `lib/scoring_sampler.py:107-116`
  (`flags_for_call`) independently reimplement the identical "map a detection row to its flag list"
  logic, and have already drifted: `_detected_flags` tolerates both `"Releasing Detection"` and
  `releasing_detection` key spellings via its `_get()` helper; `flags_for_call` only checks the
  Title-case key.
- `lib/campaign_metrics.py:12`'s `_GOOD_ENGAGEMENT` set hardcodes en-dash characters
  (`"decision maker – nyi"`, `"dnc – decision maker"`, `"dnc – unknown"`) as substring-containment keys
  against lower-cased disposition strings — the exact hyphen-vs-en-dash format inconsistency the
  project's own memory notes (`disposition-string-format-inconsistency`) warn about elsewhere. If
  upstream data ever uses a plain hyphen here, these specific checks silently stop matching.
- `lib/campaign_metrics.py:build_doc_field_mapping` (`:93-146`) returns a dict keyed by literal
  `"{{placeholder}}"` strings that must match an external Google-Doc template's placeholder names
  exactly, plus two keys (`{{sheet_url}}`, `{{summary_ratios}}`, `:144-145`) deliberately left as
  sentinels for some other, undocumented caller to fill in afterward — none of this contract is visible
  from this file alone.

## Needless Links

- `lib/database.py`'s `get_pool_stats`/`is_pool_healthy`/`cleanup_idle_connections`
  (`:484`, `:698-728`, `:730-750`) reach into psycopg2 `ThreadedConnectionPool`'s private `_used`/`_pool`
  attributes — undocumented implementation details of a library this module doesn't own.
- `lib/webdriver_manager.py:164-173` (`managed_chrome_driver`) reaches into Selenium's
  non-public-API internals — `driver.service.process.pid` and `driver.capabilities['chrome']
  ['userDataDir']` — to track PIDs/profiles for cleanup, rather than anything Selenium documents as stable.
- `lib/scoring_audit.py:33` imports `_FLAG_ORDER` directly from `lib/scoring_sampler.py:28` — a
  leading-underscore name that signals "private to this module," reached into across a file boundary anyway.
- `lib/timeout_utils.py` is a generic `lib/` utility (`_calculate_timeout`, `:8-20`) but is hard-wired to
  `config.ProcessingConfig`'s specific constant-naming convention (`_BASE`/`_PER_MINUTE`/`_MIN`/`_MAX`
  suffixes, `:5`, `:27-30`, `:37-40`) — an implicit naming contract with a more volatile, app-specific
  module, enforced by nothing but matching variable names.
- [PROTECTED] `_performance_issue`/`_performance_issue_note` (`lib/dashboard_manager.py:62-104`) are
  "general" helpers whose `kind` parameter (`"effort"`/`"rebuttal"`/`"releasing"`/`"tonality"`/
  `"coaching"`/`"allocation"`/`"campaign_list"`) is only fully understood by their single caller,
  `generate_performance_report`'s `issue_table` construction (`:4009-4031`) — a general-looking function
  that in practice changes whenever that one workflow does.
- [PROTECTED] `quota_manager.get_user_quota_status` (`lib/quota_manager.py:833-842`) includes a
  `"managed": True` key with the comment `# For compatibility with dashboard_manager` (`:835`) — a
  general-purpose return shape permanently carrying a field that exists for exactly one external caller.

## Surplus

- [PROTECTED] `TransactionManager` (`lib/dashboard_manager.py:276-343`) is a fully-built rollback
  mechanism with its own docstring example (add a user, then assign quota, roll back both on failure,
  `:288-299`) — but nothing in this file ever instantiates it. `create_user_with_quota`
  (`:1556-1617`), the method matching that exact scenario, handles a failed quota assignment by just
  logging a warning and returning success-with-caveat (`:1607-1615`), even though its own comment
  (`:1605-1606`) says "If quota assignment fails, we'll remove the user manually" — the code doesn't
  do that removal.
- [PROTECTED] `UserManager.verify_user_password` (`lib/dashboard_manager.py:1252-1255`) is a dead stub:
  "Obsolete: All authentication is handled via Google OAuth", logs a warning, always returns `False`.
- [PROTECTED] `UserManager.get_user` (`lib/dashboard_manager.py:1223-1224`) still selects and returns
  `app_pass_hash`/`app_pass_salt` from the `users` table even though the only plausible consumer,
  `verify_user_password`, is the dead stub above — a half-removed password system.
- [PROTECTED] `user_manager = UserManager()` is instantiated twice at module scope: once right after the
  class definition (`lib/dashboard_manager.py:1796`) and again in the "Global instance" block at the
  end of the file (`:4180`) — the second silently shadows the first, and `_initialize_users()`'s
  default-user-seeding work runs twice on import.
- [PROTECTED] `get_combined_agent_audit_data` (`lib/dashboard_manager.py:2407-2549`): the `try` block
  either `return`s (`:2539`) or the `except` `raise`s (`:2542`), so the "sort and dedupe" lines right
  after it (`:2543-2547`) are unreachable dead code. Worse, if `self._db_manager` is falsy, control
  skips the whole `if self._db_manager:` block and reaches `return combined_df` (`:2549`) with
  `combined_df` never assigned — a `NameError` instead of an empty DataFrame. Comment at `:2542`
  ("Re-raise exception instead of falling back to JSON") confirms this is leftover from removing an
  old JSON-fallback path.
- Vestigial Streamlit-era code, from when VOS likely had a Streamlit frontend (the project is now
  React/Vite per CLAUDE.md's architecture diagram): `lib/logging_config.py:43-52`
  (`setup_frontend_logging`, "Configure logging for Streamlit frontend"); `lib/html_sanitizer.py:99-104`
  (`safe_markdown`, framed entirely around `st.markdown()`); [PROTECTED] and inside
  `lib/dashboard_manager.py`, the `STREAMLIT_AVAILABLE`/`st` branches in `SessionManager.create_session`
  (`:413-419`, `st.request` isn't even a real Streamlit attribute) and the ~8
  `if STREAMLIT_AVAILABLE and st: st.warning(...)` calls riding along with the migration-lock
  boilerplate listed under Hidden Links.
- `lib/webdriver_manager.py` manages Chrome/Selenium WebDriver lifecycle for ReadyMode automation; an
  untracked planning doc already in this repo's working tree is named
  `docs/superpowers/plans/2026-10-29-remove-chrome-readymode-connector.md` (seen in git status, content
  not read as part of this pass) — its filename alone suggests this whole module's reason for existing
  may already be scheduled for removal. Flagged here for visibility, not asserted as fact.
- [PROTECTED] Stray trailing `pass` statements with no effect, at the end of
  `clear_lite_audit_data` (`lib/dashboard_manager.py:2982`) and `clear_agent_audit_data` (`:3194`).
- [PROTECTED] `lib/security_utils.py:344-380` (`if __name__ == "__main__":`) is a demo/smoke-test block
  embedded in the production security module — it encrypts and hashes a hardcoded plaintext
  `test_password = "MySecretPassword123!"` and prints intermediate values to stdout.
- `lib/database.py:cleanup_idle_connections` (`:479-497`) has no caller anywhere in this 15-file scope;
  may be called from outside it (not verified here).
- `lib/html_sanitizer.py`'s `sanitize_html`/`sanitize_text`/`safe_markdown` (`:34-124`) have no caller
  anywhere in this 15-file scope; may be called from outside it (not verified here).
- [PROTECTED] `lib/quota_manager.py:test_quota_recording` (`:903-936`) is a manual-debugging helper
  ("Test quota recording for debugging") shipped inside the production `QuotaManager` class, with no
  caller found in this scope.

## Special Cases

- [PROTECTED] `UserManager._is_protected_owner_variant` (`lib/dashboard_manager.py:742-748`) always
  returns `False`, and `PROTECTED_VARIANTS = []` (`:721`) is permanently empty — a disabled security
  check kept as inert scaffolding. The `if self._is_protected_owner_variant(...):` guards it feeds at
  `remove_user:1031`, `update_user:1119`, `can_end_sessions:1452`, `can_modify_user:1478`, and
  `remove_user_with_quota:1654` can never fire.
- [PROTECTED] `UserManager.update_user`'s `allowed_fields` set (`lib/dashboard_manager.py:1114`) is a
  hardcoded field-allowlist that only applies when both `updated_by` and `username` equal
  `PROTECTED_OWNER` — a parameter carved out for exactly one caller editing exactly one account.
- [PROTECTED] `SessionManager.validate_session` (`lib/dashboard_manager.py:446-526`) hardcodes
  `max_retries = 2`, `retry_delay = 0.5` (`:460-461`), a string-matched list of "connection error"
  keywords (`:497-500`), and a fail-open "benefit of the doubt" default (`return True`,
  `:519`/`:526`) for one specific failure mode (transient DB errors during session checks).
- [PROTECTED] `quota_manager.record_user_usage` (`lib/quota_manager.py:696-732`) silently auto-creates
  a whole new "admin" quota group (`max_users=1000, total_daily_quota=1_000_000`, `:711`) the first
  time any user with no quota assignment records usage — a magic-number special case triggered as a
  side effect of what looks like a simple "record usage" call.
- `lib/database.py`'s connection/query path stacks four independent retry mechanisms for the same
  failure class (pool exhaustion / broken connection): the `@retry_on_db_error` decorator on
  `get_connection` (`:267`), `get_connection`'s own 30-second poll loop (`:273-294`),
  `execute_query`'s 3-attempt connection-acquisition loop (`:341-355`), and `execute_query`'s own outer
  `while retry_count < max_retries` loop (`:337-428`) — each with its own hardcoded timeout/sleep constants.
- `lib/migration_lock.py:is_migration_in_progress` (`:48-63`) treats any lock file older than exactly
  one hour (`lock_age > 3600`, `:55`) as stale and deletes it unconditionally, letting a new process
  steal the lock out from under a still-running migration that simply takes longer than that.
- `lib/security_utils.py:check_environment_security` (`:288-342`) "checks for hardcoded credentials" in
  `app.py`/`config.py` (`:325-334`) by only checking whether those files exist, then appending the same
  canned recommendation string regardless of their contents — it never actually inspects the files it
  claims to review.
- `lib/dashboard_manager.py:remove_sharing_group` (`:1987-2029`) has a nested
  `except KeyError ... try: ... except: pass` fallback (`:2016-2026`) that retries the group deletion a
  second way and swallows any error from that retry too.

## Scope note

No SHA256-no-salt password hashing or second/duplicate hash-verification system was found inside this
15-file scope. `lib/security_utils.py`'s `hash_password`/`verify_password` (`:159-210`) already use
salted PBKDF2-SHA256 with a constant-time `kdf.verify()`, and `dashboard_manager.py`'s own password
check is the dead `verify_user_password` stub above. CLAUDE.md's "SHA256 password hashing (no salt)" /
"verify_password not constant-time" known issues almost certainly live in `backend/api/auth.py`, which
is outside this pass's scope and wasn't read.
