# Clean code improvement plan

## Problem

VOS has Python and TypeScript application code spread across backend services, audio and rebuttal processing, shared libraries, automation scripts, and the frontend. The large scope and a few very large modules make a single broad rewrite hard to review and risky to scoring, authentication, quota, and deployment behavior.

## Options considered

1. Apply formatting and mechanical rewrites across the repository at once. This is fast, but can create a large diff and obscure behavior changes.
2. Refactor the project in small, behavior-preserving slices, starting with low-risk shared utilities and moving to domain modules only with clear boundaries. This keeps each change reviewable and makes regressions easier to localize.
3. Produce an audit only and leave all code unchanged. This avoids risk but does not directly improve maintainability.

## Chosen approach

Use staged, behavior-preserving refactors. Start with small independent utilities, then address larger modules after mapping their responsibilities and callers. Defer changes to authentication/routing, `lib/dashboard_manager.py` user/audit/quota logic, database schema, and scoring/detection behavior until a specific change is designed and its impact is understood. Preserve in-progress user files and avoid broad formatting churn.

## Initial repository findings

- The tracked application surface contains 202 Python, TypeScript, TSX, and JavaScript files across `backend/`, `analyzer/`, `audio_pipeline/`, `automation/`, `lib/`, `processing/`, and `webapp/src/`.
- `lib/dashboard_manager.py` and `analyzer/rebuttal_detection.py` are each around 3,000 lines; `lib/phrase_learning.py` and `processing/batch_engine.py` are also large. These carry domain or core processing behavior and need careful, focused work.
- The available test inventory is very small, so behavior-preserving changes should stay narrow and avoid claiming broad regression coverage.
- The current working tree contains untracked user files. They must remain untouched during cleanup.

## Progress and coverage

- Inventory: 202 tracked application source files and 56,801 lines; 133 Python, 25 TypeScript, 39 TSX, and 5 JavaScript files. This pass also covered the tracked Python tooling under `.agents/skills/007/`.
- Python syntax review: all 133 tracked Python files plus the new `audio_pipeline/audio_utils.py` parsed successfully. A simple AST inventory found 427 functions longer than 25 lines; this is a review queue, not an instruction to split every function.
- Python cleanup: removed statically unused imports from independent utilities, services, processing modules, and scripts. Removed unused batch/audio imports from the single-file audio service and stale platform-locking imports from `lib/dashboard_manager.py`; removed a redundant method-local NumPy import in `analyzer/rebuttal_detection.py`. The whole-tree AST import scan's remaining findings are intentional: `__future__` annotations, package re-exports, psycopg2 pool initialization, optional Flash Attention detection, and imports that install ReadyMode stdout handling.
- Frontend review: ESLint originally reported 90 findings across 25 files. Dead imports/state and unused declarations were removed, `any` types were replaced with `unknown` or explicit API types, shared error guards were added, and several state patterns were simplified. Necessary server-to-form synchronization and intentionally randomized progress text retain brief rule suppressions with explanations.
- Initial validation: `npm run lint` passes and `npm run build` succeeds. The build still reports the existing large-chunk warning. Tests were added and run during the follow-up verification below.
- Code changed so far: `lib/timeout_utils.py` consolidates timeout scaling; `backend/services/campaign_report_export.py` separates row filtering from Google API orchestration; `lib/dashboard_manager.py` drops unused performance-report locals/imports and extracts rating/note/table formatting helpers without changing calculations or output fields; `backend/services/worker_pool_manager.py` corrects the stats return annotation; unused Python imports were removed across backend, processing, audio, and tooling modules; frontend improvements are in `webapp/src/` including API types, audit utilities, the karaoke transcript, and shared error handling.
- Batch-engine mapping: `batch_analyze_folder_lite` is called through the `processing` package by the ReadyMode API; `process_single_file_lite` feeds its per-file processing. Consolidated repeated filename parsing and failure-row creation into typed helpers while preserving each error status and output fields, and removed a duplicate identical `Reason for Calling` key from one error row. `PhraseLearningManager` is called by detection, phrase-management APIs, and batch completion, so its database and detection responsibilities remain a separately mapped review area.
- Rebuttal-engine review: `SemanticDetectionEngine._detect_regex_matches` had an earlier same-name implementation shadowed by a later definition; removed the unreachable definition, duplicate whitespace-normalization step, and unreachable duplicate return without changing the active detection path. An AST scan now finds no duplicate class methods or module-level functions among tracked Python files.
- Detection dictionary cleanup: removed repeated phonetic-correction entries with identical values; dictionary order and effective mappings are unchanged. The full static scan confirms conflicting repeats remain (`bi`, `bey`, `der`, `yur`, `yor`, `yoor`, `yar`, `fiet`, `wi`, `way`, `wer`, `wir`, `doz`, `dan`, `nou`, `al`, and `gat`). Their later values currently win, and deleting or reordering entries can change correction order, so their intended mappings need domain review.
- Dashboard review: removed unused row-level calculations in `get_audit_metrics` and dead locals in the performance report. Simplified `_generate_ai_insights` by removing unused inputs and branches shadowed by earlier `elif` conditions; current observations remain unchanged because the removed branches could never execute.
- Additional low-risk cleanup: removed the unused ReadyMode download-path binding and discarded an unused UID loop value in duplicate-user grouping; neither output nor selection logic changed.
- Phrase-learning review: mapped detection, API, and batch callsites. Removed redundant Decimal type branches from numeric coercion, an unused loop index, and unused timeout/retry parameters that the private connection helpers never applied. The database operations and conversion fallbacks remain unchanged.
- Audio-service review: removed unreachable config fallback/imports because the module already imports the same settings and dashboard manager at module scope; processing and result persistence paths are unchanged.
- Job-store review: removed a redundant SQLite/PostgreSQL branch that serialized non-null job options identically in both cases; SQL statements and persisted values are unchanged.
- Quota health-check review: removed the unused local binding for loaded usage data; the database load still runs before `can_load_usage` is marked true, so the health-check result is unchanged.
- TL Actions reconciliation cleanup: marked the unused HTML parser attributes parameter as intentionally unused and reused the existing module-level `timedelta` import in Sheets date conversion.
- Utility review: removed unused sheet-row counters and a never-read task list from Google Sheets formatting and parallel detection setup; request payloads and executed tasks are unchanged.
- TL Actions submission review: removed the source-row number from a private payload builder because row validation and lookup already happen in its caller; generated prefill payloads are unchanged.
- Follow-up static review: removed an unreported failed-download counter and unused returned-value bindings in the ReadyMode downloader, plus dead date/string locals in the dashboard manager.
- Async detection review: removed an unused timeout classification from the transcription-failure path; that path already returned the same "No" result and error metadata for every failure.
- Whole-tree unused-local follow-up: removed unused selected tuple fields and clarified intentionally ignored values in phrase learning, semantic model setup, and dashboard file parsing. The SQL query filters/sort and model initialization calls remain intact.
- Additional unused-local pass: removed an unused computed batch total, used an ignored binding for the unused phrase quality value, and clarified that the AssemblyAI submission retry index is intentionally unused. Retry count and error handling are unchanged.
- Static unused-local follow-up: removed dead transcribed-word retrieval, unused retry/evaluation placeholders, and an empty Whisper-optimization conditional. These values had no effect on returned results or processing; the actual transcript segments and detection flow are unchanged.
- Batch-processing review: removed the non-async folder processor's completion counter, which was only incremented and never read; the async and lite processors retain their counters because they drive progress and warnings.
- Evaluation and quota utility review: removed unused report calculations and an unused total-usage calculation in quota suggestions. The rebuttal analysis script continues loading its `--replay` file to preserve input validation even though its report does not use replay rows.
- Frontend API review: consolidated duplicated HTTP error-body parsing in the shared fetch client; JSON detail and HTTP-status fallback behavior stay the same for normal requests and uploads.
- Whole-tree unused-local review: the only remaining intentional local is the startup construction of the phrase-learning singleton; its name now marks that it exists for initialization side effects.
- Large dashboard method review: moved the repeated `re` and `Path` imports used by `get_combined_lite_audit_data` to the module import block, removing per-row imports without changing filename parsing.
- Dashboard import cleanup: removed redundant local `re` and `Path` imports, and reused the existing `datetime` class in `_format_time`; the other local datetime imports remain in security logging and audit persistence paths.
- Audit time parsing: consolidated the identical filename time extraction used by agent and lite audit loaders; both still use filename time first, then the existing stored-timestamp formatter.
- Fast audio processor cleanup: removed its empty constructor and reused the module logger inside `process_single_file_fast`; instance defaults and processing flow are unchanged.
- Audio channel handling: centralized the identical mono/stereo/multichannel agent-channel selection used by fast, optimized, and semantic processors; their existing method entry points now delegate to the shared helper.
- Audio filename metadata: centralized the matching metadata parser used by those same three processors; the main `AudioProcessor` keeps its separate formatting path because its output normalization differs.
- Audio logging cleanup: removed per-call logger lookups where the module-level logger already provides the same logger instance.
- Audio duration cleanup: removed three unused private three-second validators from those processors; their active one-second file checks remain unchanged.
- Campaign metrics cleanup: used `Counter` for disposition bucket counting and converted back to dictionaries in the result, preserving the existing counts, insertion order, and output shape.
- Campaign ratio cleanup: count the three detection flags in one row pass while retaining the existing percentage rounding, return keys, and empty-input behavior.
- Campaign metrics typing: updated the ratio-helper return annotation to cover its existing floating-point percentages and integer counts.
- Batch-engine logging cleanup: reused the existing module logger in the synchronous and lite folder-processing entry points.
- Google Workspace summary-sheet cleanup: build displayed rows and per-row formatting requests in one pass over summary rows; the values update still occurs before the formatting batch request.
- Long-call summary cleanup: counted voicemail and dead-call rows in one pass instead of scanning the flagged list twice; result keys and counts are unchanged.
- Lite-audit parsing: extracted filename-to-phone/timestamp/disposition parsing into a private helper, keeping the existing format branches, timestamp normalization, and error fallback together and unchanged.
- Lite-audit dialer parsing: moved the parent-folder suffix extraction into its own helper, preserving stored-dialer precedence and the same empty fallback when the path has no usable suffix.
- Phrase deduplication: narrowed both duplicate-cleanup queries to the five selected fields the algorithms use, and aligned their row mappings; category/similarity values never affected grouping, ranking, merges, or deletion.
- TL Actions tracker: separated construction of the Google Sheets formatting request list from the API call; the same ordered request payload is submitted, while its formatting logic can now be reviewed independently.
- TL Actions tracker follow-up: split the formatting payload into sheet setup, action-table, summary-cell, table-control, and date-format helpers. An AST comparison against the prior implementation confirms all 21 static request payloads are unchanged and remain in the same order; deletion and conditional row-resize requests retain their original positions.
- ReadyMode downloader review: removed an unreferenced private path-sanitizing helper after confirming there are no callsites anywhere in tracked Python code.
- ReadyMode naming: consolidated identical dialer-hostname formatting across create, delete, duplicate-scan, and inactive-scan scripts; each script still derives the name from the same hostname segment.
- Detection cleanup: removed `AgentOnlyTranscriptionEngine._validate_audio_quality`, a private helper with no tracked callsites; transcription and rebuttal paths do not invoke it, so active detection behavior is unchanged.
- Quota cleanup: removed the unreferenced `_save_usage_data` database writer; `record_user_usage` remains the active atomic upsert path, and no tracked callers used the legacy writer.
- Duplicate local-import cleanup: reused module-level imports in analyzer, agent detection, ReadyMode API, and batch processing, including `os`, `re`, `json`, `AudioSegment`, `time`, `TimeoutError`, and `threading`. Kept function-local imports where they preserve lazy loading or use a distinct module/class name.
- PostgreSQL pool import: changed pool construction and `PoolError` references to use the already imported `pool` module directly, eliminating reliance on `psycopg2` exposing a submodule as an attribute. The same pool classes and error handling remain in use.
- Deployment/schema review: checked both tracked shell entrypoints, SQL/migration files, Terraform, Kubernetes manifests, and Nginx configuration. The entrypoint is already concise; the AWS deployment script and schema/config files define deployment or database behavior, so they were left unchanged in this behavior-preserving maintainability pass.
- Deferred detection finding: `SemanticAudioProcessor._ensure_models_loaded` has no tracked caller even though the processor later checks `semantic_engine`; invoking it would change the current detection path, so it remains untouched in this behavior-preserving pass.
- Whole-project pass complete: reviewed the tracked Python, TypeScript/TSX, and JavaScript application/tooling surface with import/local/deduplication scans and focused inspections; frontend lint/build, Python syntax, shell syntax, and diff checks pass. All 202 tracked source files were in scope. Large domain functions remain intact where a split would broaden behavior risk; the AST size scan found 104 functions at 80+ lines, including existing auth, database, scoring, detection, reporting, and audit paths that need focused changes with domain-specific validation.
- Follow-up verification: the tracker-order regression tests pass, and the complete suite passes with `DB_TYPE=sqlite` from a temporary working directory, keeping writes out of the project database (32 passed). The direct test invocation without these settings fails during collection because session-manager initialization requires a database.

## Work sequence

1. Keep large modules in focused follow-up slices, mapping callers and responsibilities before splitting them.
2. Keep sensitive auth, quota, database, detection, and scoring paths isolated from unrelated cleanup.

## Success criteria

- Each cleanup diff has a clear purpose and does not mix formatting with logic changes.
- Public behavior and interfaces stay stable unless a separate change explicitly calls for behavior changes.
- Duplicated logic is reduced where one implementation makes the code easier to follow.
- Each phase can be reviewed and reverted independently.

## Risks and verification

Refactoring core paths can change behavior even when intent is unchanged. Keep diffs narrow and review affected callers. The full Python suite needs a database configuration; use temporary SQLite for local verification to avoid writes to the project database.
