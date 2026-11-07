# lib-audio-perf — Problems (Step 2)

Scope: lib/phrase_learning.py, lib/google_workspace.py, lib/assemblyai_transcription.py,
lib/cpu_optimizer.py, lib/parallel_processor.py, lib/enhanced_parallel_processor.py,
lib/audio_optimizer.py, lib/transcription_caching.py, lib/simple_cpu_optimizer.py.

Dead-code claims below are based on `grep -rn` across the whole repo (excluding
`.claude/worktrees/`) for each symbol; a caller using dynamic dispatch/reflection would not
show up, but none was found.

## Hidden Links

- `lib/phrase_learning.py:288-320` — `_init_database()` defines `pending_phrases` and
  `repository_phrases` inline with `CREATE TABLE IF NOT EXISTS`; the same two tables (plus
  `rebuttal_phrases`) are *also* defined independently in `docs/sql/SUPABASE_SCHEMA_INIT.sql`,
  `cloud-migration/init.sql`, and `cloud-migration/migration_schema.sql` — four copies of the
  same schema with nothing checking they agree.
- `lib/phrase_learning.py:795-808, 824-833, 882-891, 963-993, 1813-1830` — `rebuttal_phrases` is
  read from and written to in five places, but this file's own `_init_database()` never creates
  it; every touch point assumes a table defined only in the external SQL files above, and every
  write to it is wrapped in a bare `try/except: pass` (e.g. 890-891) so a missing/out-of-sync
  table fails silently.
- `lib/phrase_learning.py:1116` vs `lib/phrase_learning.py:1592` — two independent
  "find-and-merge duplicate pending phrases" implementations (`_auto_cleanup_duplicates_lightweight`
  and `remove_duplicate_phrases`) that already disagree on tie-break order: one sorts
  `(detection_count, confidence)`, the other `(confidence, detection_count)`, so which duplicate
  survives depends on which method ran.
- `lib/phrase_learning.py:149-239, 1302-1374, 1376-1425, 1427-1500` — four separate "approve a
  batch of pending phrases" methods (`auto_approve_high_confidence_phrases`,
  `approve_by_quality_score`, `approve_by_category`, `approve_all_pending_phrases`) each
  re-implement the same SELECT → loop → `_add_to_repository` → UPDATE status → commit → stats-dict
  sequence instead of sharing one core loop.
- `lib/phrase_learning.py:469-470, 560-561, 791-792, 816-817, 853-854` — the two-line
  "`existing_conn` or open a new one via `nullcontext`" idiom is copy-pasted five times; a change
  to how optional-connection-reuse works needs all five found and fixed by hand.
- `lib/phrase_learning.py:547-549, 571-573` — "only commit if I opened the connection" is an
  unenforced convention a caller must know: pass `existing_conn` and forget to commit it
  yourself, and the write silently never lands.
- `lib/phrase_learning.py:491-506, 649-658, 762-772, 1203-1206, 1223-1226` — the same
  psycopg2-Decimal-to-float/int coercion (`try: x = float(x) except: x = default`) is copied at
  least six times instead of going through one helper.
- `lib/phrase_learning.py:859-891` vs `lib/phrase_learning.py:959-995` — the "write to
  `repository_phrases`, then best-effort write to `rebuttal_phrases`" dual-write is implemented
  twice (`_add_to_repository` and `flush_deferred_phrases`) instead of the latter calling the
  former.
- `lib/phrase_learning.py:900-904` vs `lib/phrase_learning.py:1009-1016` — the identical
  "reload semantic embeddings after writing a phrase" step is duplicated with two different
  error-handling philosophies: one swallows all failures silently (`except Exception: pass`), the
  other logs and records the error in `stats['errors']`.
- `lib/phrase_learning.py:1672-1675` vs `lib/phrase_learning.py:812-839` — "does this phrase
  already exist" is checked two inconsistent ways: `add_phrase_manually` loads the *entire*
  repository via `get_repository_phrases()` and loops in Python, while every other call site uses
  the indexed `_phrase_exists_in_repository` query.
- `lib/phrase_learning.py:28-34` vs `lib/transcription_caching.py:26-32` — the
  `_instance`/`_initialized`/`__new__` singleton block is copy-pasted verbatim between
  `PhraseLearningManager` and `TranscriptionCacheManager` (class name is the only difference).
- `lib/phrase_learning.py:1886-1894`, `lib/cpu_optimizer.py:288-297`,
  `lib/simple_cpu_optimizer.py:63-72`, `lib/parallel_processor.py:287-295`,
  `lib/enhanced_parallel_processor.py:337-345`, `lib/audio_optimizer.py:213-221` — six independent,
  hand-copied implementations of the same "module-level global + `get_X()` getter" singleton
  pattern, none referencing a shared helper.
- `lib/google_workspace.py:61-67` vs `lib/google_workspace.py:705-707` — the same dark-green
  header color is defined twice: once through the `_rgb()` helper as `_HEADER_BG` (for Sheets),
  once as a hand-typed literal dict inside `style_report_doc` (for Docs); changing the brand color
  means finding both.
- `lib/google_workspace.py:441` vs `lib/google_workspace.py:530` — `_FORMULA_CELLS` (local to
  `append_scoring_rows`) and the module-level `SCORING_FORMULA_CELLS` are two separate,
  textually-identical lists of the same five cell addresses; `append_scoring_rows` doesn't even
  reference the module constant sitting 90 lines above it.
- `lib/google_workspace.py:105-106` vs `lib/google_workspace.py:148-149` — the "this column might
  be spelled 'Reason For Calling' / 'Reason for calling' / 'Reason for Calling'" defensive
  three-way fallback is copy-pasted between `_build_agent_issues_summary` and `create_spreadsheet`.
- `lib/google_workspace.py:154-193` vs `lib/google_workspace.py:324-355` — `create_spreadsheet`
  and `create_scoring_spreadsheet` duplicate the same "create file, write header row, format dark
  green/bold/frozen, build `.../edit` URL" boilerplate instead of sharing it.
- `lib/assemblyai_transcription.py:350-356, 405-411, 705-711` — the save-global /
  mutate-to-instance-key / restore-global dance around `aai.settings.api_key` is copy-pasted three
  times; a fix to the isolation mechanism needs three edits, not one.
- `lib/assemblyai_transcription.py:359-366` vs `lib/assemblyai_transcription.py:714-720` —
  `transcribe_file`'s and `transcribe_url`'s "default AssemblyAI config" dicts are two copies that
  have already drifted: only `transcribe_file` sets `multichannel: True`, and `speaker_labels`
  defaults come from a function parameter in one and a different env var in the other.
- `lib/assemblyai_transcription.py:432-446` vs `lib/assemblyai_transcription.py:470-481,489-500` —
  the success-result dict carries `dialogue`/`agent_transcript`/`owner_transcript`; both
  copy-pasted failure-result dicts lack all three, so the "same shape on every return path"
  assumption has already broken.
- `lib/assemblyai_transcription.py:552-581` (and its callers at 605, 654) — this file's channel→
  role mapping is the kind of logic external files pin by exact line number instead of by a
  stable contract: `scripts/rebuttal_eval/dialogue_utils.py:4,13`, `scripts/rebuttal_eval/replay.py:139,168`
  and `analyzer/objection_gate.py:80` all cite `lib/assemblyai_transcription.py:553/587/621` for a
  channel-type bug that `_channel_roles`'s own docstring (556-563) says is already fixed — the
  external comments have drifted out of sync with the code they point at.
- `lib/assemblyai_transcription.py:620-622` vs `analyzer/objection_gate.py:80` (external) — the
  diarization branch of `format_as_dialogue` can emit whatever label AssemblyAI gives a speaker
  (`utterance.get('speaker', 'Unknown')`), not literally "Agent"/"Owner", yet the only consumer
  that parses this output hard-codes a `(Agent|Owner)` regex with nothing in this file guaranteeing
  that shape.
- Lower confidence, flagging rather than asserting: `lib/phrase_learning.py:81-85` (settings
  defaults: confidence 0.85 / auto_approve 0.80), `:712-719` (`get_quality_tier` cutoffs
  0.90/0.80/0.65) and `:733-737` (`get_adaptive_threshold` base thresholds 0.88/0.85/0.80) are
  three separate sets of similar-looking confidence/quality cutoffs defined independently; they
  may be intentionally distinct concepts (tier vs. per-category threshold vs. global setting), but
  nothing documents whether they're allowed to diverge or should move together.

## Needless Links

- `lib/phrase_learning.py:241-260` (`_get_db_connection`/`_return_db_connection`) reaches past
  `DatabaseManager`'s public `get_connection()` (lib/database.py:268) straight into its internal
  `self.db_manager.connection_pool.getconn()/.putconn()`, skipping whatever broken-connection
  handling the public method does (lib/database.py:305 passes `close=is_broken`).
  `lib/transcription_caching.py:76` uses the public method correctly for the same dependency —
  two different coupling depths to the same volatile internal.
- `lib/phrase_learning.py` mixes two DB-resource-management idioms in one class: the
  `with self._db_connection() as conn:` contextmanager used almost everywhere, vs. manual
  `conn = self._get_db_connection(); ...; self._return_db_connection(conn)` with hand-written
  try/finally in `approve_phrase:1253-1293`, `get_repository_stats:1736-1794`, and
  `get_repository_phrases:1797-1849` — a connection-handling fix now has to be applied twice, in
  two different shapes.
- `lib/google_workspace.py:381-527` (`append_scoring_rows`) — nominally a generic "append rows to
  a sheet" utility, but 464-484 branches on a `scores` dict shape
  (`late_hello`/`releasing`/`agent_intro`/`reason`/`rebuttal_ok`) and magic codes `"AE"`/`"OH"`
  that only the heavy-audit scoring workflow understands; any other caller of this "general"
  function inherits that vocabulary whether it wants it or not.
- `lib/enhanced_parallel_processor.py:32-35` pulls three full config dicts out of
  `IntelCPUOptimizer` (`get_optimal_parallel_config`, `get_optimal_whisper_config`,
  `get_memory_optimization_config`) but only ever reads one key from them (`max_workers`, line 38)
  — tight coupling to the optimizer's whole interface to get one value.
- `lib/parallel_processor.py:122` and `lib/enhanced_parallel_processor.py:146` both import
  `lib.agent_only_detector.AgentOnlyRebuttalDetector` inside a function body "to avoid circular
  imports" — a layering/import-order workaround callers (here, the module itself) have to know
  about rather than a clean dependency direction.
- `lib/assemblyai_transcription.py:39` — merely importing this module runs a live database lookup
  (`from lib.dashboard_manager import user_manager; user_manager.get_user_assemblyai_key(...)`) as
  an import-time side effect, before any class is constructed; a low-level transcription module
  taking on import-time behavior that belongs to the higher, more volatile user/session layer.

## Surplus

- `lib/simple_cpu_optimizer.py` (whole file) — `SimpleCPUOptimizer`/`apply_simple_cpu_optimizations`
  has zero references anywhere in the repo, including from the other optimizer files.
- `lib/parallel_processor.py` (whole file) — `ParallelDetectionProcessor`/`get_parallel_processor`
  has zero callers outside the file itself.
- `lib/enhanced_parallel_processor.py` (whole file) —
  `EnhancedParallelProcessor`/`get_enhanced_processor` has zero callers outside the file itself.
- `lib/audio_optimizer.py` (whole file) — `AudioOptimizer`/`get_audio_optimizer` is only consumed
  by `lib/parallel_processor.py:126-127` and `lib/enhanced_parallel_processor.py:147-150`, both of
  which are themselves unused, so it is transitively dead in the running app.
- `lib/cpu_optimizer.py` (whole file) — `IntelCPUOptimizer`/`get_cpu_optimizer` is only imported by
  `lib/enhanced_parallel_processor.py:24`, which is itself unused outside this cluster.
- `lib/assemblyai_transcription.py:62-118` — `retry_api_call` is a fully-built retry decorator
  (rate-limit/5xx/timeout/connection backoff) that is never applied anywhere, not even in this
  file, which hand-rolls a separate, simpler retry loop instead (379-390).
- `lib/google_workspace.py:40-41, 54-58, 674-690, 692-816` — `build_docs`, `copy_template_doc`,
  `replace_doc_placeholders`, and `style_report_doc` have zero callers anywhere in the repo; the
  entire "copy template → fill placeholders → style the Doc" feature appears orphaned.
- `lib/google_workspace.py:284-378` — `create_scoring_spreadsheet` has zero callers anywhere in
  the repo (and duplicates `create_spreadsheet`'s creation/formatting boilerplate besides).
- `lib/audio_optimizer.py:24` — `self.target_bit_depth` is set in `__init__` but never read; the
  actual 16-bit enforcement is a separate hardcoded `2`/`"s16"` at lines 62-64 and 142-147.
- `lib/enhanced_parallel_processor.py:34-35` — `self.whisper_config` and `self.memory_config` are
  computed in `__init__` and never read again anywhere in the class.
- `lib/phrase_learning.py:1295-1300` — `approve_all_high_priority_phrases` is a pure pass-through
  wrapper (`return self.auto_approve_high_confidence_phrases(...)`) with no logic of its own.
- `lib/phrase_learning.py:744-757, 795-808, 814-839` — `self.use_postgresql` is set unconditionally
  `True` at line 49 ("Phase 4: Always use PostgreSQL") and never set otherwise anywhere in the
  file, under a class whose own docstring says "PHASE 4: PostgreSQL-Only Implementation" (line 4);
  the SQLite-style `else`/fallthrough branches at these three sites are unreachable, and would be
  wrong if ever reached (they pass `?` placeholders to a psycopg2 connection).
- `lib/phrase_learning.py:1886-1894` — the module-level `get_phrase_learning_manager()` getter is
  redundant with the `__new__`-based singleton already on the class (28-34); calling
  `PhraseLearningManager()` directly already returns the same instance.

## Special Cases

- `lib/phrase_learning.py:1037-1077` (`flush_deferred_phrases_in_background`) — the comments at
  1063-1075 are the developer visibly reasoning through an unresolved race between the background
  flush thread and `self.deferred_mode`/`self._deferred_phrases` ("Wait... if we set
  deferred_mode=False, flush_deferred_phrases checks this flag and returns error! ... let's keep
  it simple") and settling for a flag toggle instead of a real fix.
- `lib/phrase_learning.py:424-452` — a hardcoded list of English "polite closing" phrases
  (`closing_keywords`/`content_keywords`) is carved out as a one-off exception inside the
  otherwise general `track_semantic_match`.
- `lib/phrase_learning.py:890-891` — swallowed exception: a failed write to `rebuttal_phrases` is
  dropped with a bare `except Exception: pass`, no log at all.
- `lib/assemblyai_transcription.py:24-59` — module-import-time block that tries
  `import streamlit as st` (30) to guess the "current user" for an AssemblyAI key lookup, falling
  back to `os.getenv('VOS_USER', 'Mohamed Abdo')` (37) — a specific person's name hardcoded as a
  library default, left over from what looks like a pre-FastAPI Streamlit UI.
- `lib/assemblyai_transcription.py:346-356, 403-411, 702-711` — the global `aai.settings.api_key`
  save/mutate/restore sequence, marked "CRITICAL FIX" in its own comments, narrows a concurrency
  race between simultaneous users instead of removing the shared global it's working around.
- `lib/assemblyai_transcription.py:377-390` — a hand-rolled "retry the submit call up to 3 times,
  sleep(1) between attempts" loop exists solely for this one call site, duplicating in spirit (but
  not in code) the unused general-purpose `retry_api_call` decorator defined earlier in the same
  file.
- `lib/transcription_caching.py:127-130` — comment admits the `last_accessed_at` column is
  deliberately never updated on a cache read ("let's keep it simple"), so a column named for reads
  only ever reflects writes.
- `lib/transcription_caching.py:132-138` — a "(sqlite fallback)" JSON-string-parsing branch for a
  database backend this class never actually supports (`_init_database` only ever creates a
  PostgreSQL `JSONB` column); looks copied from `lib/phrase_learning.py`'s genuine dual-backend
  code without checking whether the sqlite path applies here.
- `lib/transcription_caching.py:39-48` — two early `return` paths in `__init__` skip setting
  `self._initialized = True` (only set at line 52), so the copied "run `__init__` once" singleton
  guarantee silently doesn't hold whenever the DB import fails or the manager can't initialize —
  every later construction re-runs the whole init body.
- `lib/google_workspace.py:409-523` (`append_scoring_rows`) — the header-guard plus
  formula-snapshot/restore machinery exists purely to cope with one external spreadsheet's fragile
  ARRAYFORMULA layout (columns A/B/E/F/S anchored at row 3 on one specific "Auditors-Scoring MOP"
  template).
- `lib/cpu_optimizer.py` (whole file) — hardcoded for one developer's one past laptop CPU (12th
  Gen Intel i7-1255U): fixed P-core range `range(0, 4)` and E-core range `range(4, 12)` at lines
  216 and 222, `base_frequency`/`max_frequency` constants at 42-43, and a "hybrid architecture"
  detector (line 41) that's really just "logical cores >= 10" — meaningless on the Railway
  containers this app actually deploys to, or on non-Intel hardware, and silently absorbed by the
  broad `except Exception` at 226-227 when it doesn't apply.
- `lib/parallel_processor.py:144-148` vs `lib/enhanced_parallel_processor.py:162-166` — both clean
  up an optimizer-created temp file with a bare `except: pass`, but decide whether cleanup is
  needed two different ways (`'temp_file' in optimization_stats` vs. `optimized_file != file_path`).
