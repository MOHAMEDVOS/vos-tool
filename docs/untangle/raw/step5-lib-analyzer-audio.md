# Step 5 — fresh re-scan of lib/, analyzer/, audio_pipeline/, processing/

Scanned fresh against current source (not the prior findings docs). Cross-checked
against `.claude/worktrees/ecstatic-noyce-fbf0dd/` (a stale worktree) only to confirm
whether something is genuinely dead in the current tree vs. just moved.

## Hidden Links

1. **`AudioProcessor.extract_agent_audio` diverges silently from the shared helper
   it duplicates.** `audio_pipeline/audio_processor.py:128-131` reimplements channel
   extraction instead of calling `audio_pipeline/audio_utils.py:8` `extract_agent_audio`
   (which `fast_audio_processor.py` and `semantic_audio_processor.py` both call via
   `_extract_agent_audio` wrappers, lines `fast_audio_processor.py:24-26` and
   `semantic_audio_processor.py:80-82`). The shared version falls back to
   `audio.set_channels(1)` for >2-channel audio; the class method just returns the
   untouched multi-channel audio unchanged in that case. Three of the four call
   sites are wired to one implementation, one is wired to a silently-diverging copy
   — nothing flags this if `audio_utils.extract_agent_audio` changes behavior.

2. **Two independent "is this disposition Wrong Number" checks that must agree but
   aren't linked.** `lib/wrong_dispo_detector.py:151` `_is_wrong_number()` normalizes
   dash variants and apostrophes before comparing; `analyzer/objection_gate.py:255`
   `_is_wrong_number()` only lowercases and collapses whitespace. Both exist because
   the two modules independently need to know whether the agent logged "Wrong Number,"
   but a disposition string that one module's normalization handles (e.g. an en-dash
   variant) and the other doesn't would make the two modules disagree about the same
   call. Nothing ties them together or tests that they agree.

3. **`lib/transcription_caching.py`'s `transcript_text` column is a plain-text copy
   that callers must remember to keep separate from the labeled `dialogue` field.**
   `lib/assemblyai_transcription.py:208` and `:234` pass
   `transcription_result.get('transcript', '')` (no Agent:/Owner: labels) into
   `cache_transcript()`, while the labeled text downstream consumers need (objection
   gate, Wrong Dispo) lives in the same dict's `'dialogue'` key. This happens to be
   safe today because callers read the whole cached dict back out and pull `dialogue`
   from it, not `transcript_text` — but nothing documents that `transcript_text` is
   cosmetic/search-only and must never become the field detection logic reads. A future
   caller "optimizing" by reading `transcript_text` directly (it already looks like the
   authoritative transcript name) would silently reintroduce the labels bug fixed in
   commit `2299399`.

## Needless Links

1. **`lib/assemblyai_transcription.py`'s `TranscriptionCache.db_manager` attribute
   (lines 130-140, used throughout `get`/`set`) is actually a `TranscriptionCacheManager`
   instance, not the real `DatabaseManager`** (from `lib/database.py`, used everywhere
   else in this codebase as `self._db_manager`/`get_db_manager()`). Naming it `db_manager`
   here needlessly ties this file's vocabulary to a name that means something different
   one module over, inviting a reader (or a future refactor) to assume it's the same
   object. No functional bug today, but it's a trap.

## Surplus

1. **`lib/optimized_pipeline.py` is entirely dead.** `OptimizedPipeline`/
   `get_optimized_pipeline()` are not imported anywhere in the current tree (verified:
   only match for `optimized_pipeline|OptimizedPipeline|get_optimized_pipeline` outside
   this file itself is the stale `.claude/worktrees/...` copy). It's a whole "beat 60.43s"
   benchmark harness, duplicating what `processing/batch_engine.py` and
   `lib/agent_only_detector.py` already do live, sitting unused.

2. **`lib/campaign_metrics.py` is entirely dead in the current tree.** Its docstring
   says these are the helpers for campaign performance report generation, and the stale
   worktree's `lib/dashboard_manager.py` does call into it — but the current
   `lib/dashboard_manager.py` has zero references to `campaign_metrics`, and no other
   file in the live tree imports it either. The refactor evidently inlined or replaced
   this logic in `dashboard_manager.py` and left the old module behind. (It also still
   uses en-dash disposition strings ("decision maker – nyi") inconsistent with the
   hyphen forms used elsewhere — moot while dead, but a trap if it's ever revived as-is.)

3. **Exact-duplicate helper pair, copy-pasted rather than shared.**
   `format_agent_name_with_spaces()` and `format_timestamp_for_display()` exist
   byte-for-byte identical (only docstrings differ) in both
   `audio_pipeline/audio_processor.py:70-80` and `processing/batch_engine.py:675-698`,
   each used extensively within its own file (`batch_engine.py` alone calls the pair at
   6+ call sites). `audio_pipeline/audio_utils.py` already exists as the "Shared
   audio-channel helpers for the single-file processors" module and already holds the
   sibling helper `extract_basic_file_metadata` (whose docstring claims it's shared by
   "the fast, optimized, and semantic processors" — "optimized" is the dead module from
   Surplus #1 above, so even that claim is half stale) — but these two formatting
   helpers were never moved there, so each file maintains its own copy that can drift.

## Special Cases

1. **`lib/dashboard_manager.py`'s per-user JSON file paths are marked dead but still
   actively wired into cleanup code.** `initialize_agent_audit_storage()` (line
   2164-2178) sets `self.agent_audit_file` with a comment "(DEPRECATED: Use DB instead)",
   and `clear_lite_audit_data()` (line 2643-2679) still unlinks
   `lite_audits_{username}.json` files and logs "Deleted legacy lite audit file." Nothing
   in the current flow writes these files anymore (DB-only writes per the comments at
   lines 2177, 3008, 2865), so this is special-cased cleanup code for a storage path that
   no longer gets populated — surplus that only exists to mop up files from before the
   DB migration, with no indication of when it's safe to delete.

2. **`increment_daily_download_count()` (dashboard_manager.py:2709-2727) special-cases
   "quota system unavailable or exceeded" by falling through to a comment-only no-op**
   ("Still record in legacy system but log the quota violation" / "Continue with legacy
   system if quota system fails") — but there is no legacy system left to fall through
   to in this function; it unconditionally proceeds to the DB `daily_counters` update
   regardless of the quota check's outcome. The comments describe behavior from before
   the DB migration and no longer describe what the code does.

## Counts

- Hidden Links: 3
- Needless Links: 1
- Surplus: 3
- Special Cases: 2

## Most important finding

The exact-duplicate `format_agent_name_with_spaces`/`format_timestamp_for_display`
pair (Surplus #3) is the clearest sign the refactor's "merge duplicated
implementations" pass didn't fully land in this scope — `audio_utils.py` was built
and partially adopted (for `extract_agent_audio`/`extract_basic_file_metadata`) but
these two sibling helpers were left behind as live, actively-growing duplicates in
`audio_processor.py` and `batch_engine.py`.
