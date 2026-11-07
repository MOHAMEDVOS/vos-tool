# Step 5 — Fresh re-scan of `backend/` (post-refactor)

Scanned fresh against current source (not the old findings doc). Context: today's
refactor added `backend/core/sse.py` (shared SSE helper), `is_call_flagged` in
`dashboard_service.py`, fixed a user-delete bug, consolidated owner-email constants,
deleted dead code, and cleaned up comments.

## Hidden Links

1. **Protected-owner identity defined three separate ways across backend/lib, each a
   silent duplicate of the others.** `backend/api/auth.py:82` and `backend/api/auth.py:101`
   both hardcode the literal `"mohamedibrahimpayonner@gmail.com"` inline (not even
   DRY'd within the same function — two separate string literals a few lines apart)
   to grant a hard owner-role bypass. Meanwhile `backend/api/settings.py:225`
   (`_assert_can_modify`) protects a *different* identifier — the literal display
   name `"Mohamed Abdo"` — from being modified. And `lib/quota_manager.py:30-31`
   defines `PROTECTED_OWNER_EMAIL` / `OWNER_EMAILS` as the actual consolidated
   constant the task description says was unified today — but `backend/api/auth.py`
   was never updated to import and use it. Four independent definitions of "who is
   the untouchable owner," three of them string literals with no shared source.
   Change the owner's email or display name and at least two of these silently stop
   working while looking identical. This is precisely the "shared helper that didn't
   reach every call site" pattern the refactor was supposed to finish — it reached
   `lib/dashboard_manager.py` (which does import `PROTECTED_OWNER_EMAIL`, see
   `lib/dashboard_manager.py:40`) but not `backend/api/auth.py` or
   `backend/api/settings.py`.

2. `backend/core/sse.py`'s cancellation story is split across two files by design
   (documented in its own docstring) — `run_sse_stream`'s `cancel_event` is set on
   client disconnect, but `backend/api/readymode.py`'s `_active_runs` registry
   (lines 80, 456-541) is what lets a *different* request (the cancel endpoint)
   reach into a run and set the same event externally. Nothing enforces that every
   future SSE endpoint added to `readymode.py` registers itself in `_active_runs` —
   a new streaming endpoint could use `run_sse_stream` correctly and still not be
   cancellable from outside. Not a bug today, but a link that only lives in a
   comment, not in types or structure.

3. `backend/services/dashboard_service.py:174-238` (`is_call_flagged`) and
   `backend/services/campaign_report_export.py:27-31` (`_is_flagged`) must agree on
   what counts as a flagged call, and currently do (by delegation) — but
   `is_call_flagged`'s docstring is the *only* place this contract is written down,
   and `campaign_report_export.py`'s wrapper gives no indication at the call site
   (`_select_report_rows`, line 39) that heavy-audit rows are *also* always included
   regardless of the flag. Anyone editing `is_call_flagged`'s rules without reading
   both docstrings could change campaign-export behavior without noticing.

## Needless Links

1. `backend/services/campaign_report_export.py:27-31` — `_is_flagged` is a
   single-line pass-through wrapper around `dashboard_service.is_call_flagged` that
   adds nothing (not even a differing signature). Its own comment says as much
   ("Delegates to ... so the campaign export always matches"). The one call site
   (`_select_report_rows:39`) could call `is_call_flagged` directly and drop the
   wrapper and its import-aliasing indirection.

2. `backend/core/config.py:9-17` — the `try/except ImportError` fallback for
   Pydantic v1 (`from pydantic import Field, validator`) is wired to a `Settings`
   class that no longer has a v1 branch (see Surplus #1 below) — the only thing
   still tying the file to "support both Pydantic major versions" is this import
   and the `PYDANTIC_V2` flag, which now gates a single class body instead of
   choosing between two. Needless now that there's only one implementation.

## Surplus

1. **Dead/broken fallback branch in `backend/core/config.py`.** The refactor deleted
   the entire Pydantic-v1 `Settings` class body (correctly, since
   `requirements.txt:10-11` pins `pydantic>=2.0.0` and `pydantic-settings>=2.0.0`),
   but left the `if PYDANTIC_V2:` guard (line 132) with no `else:` branch defining
   `Settings` for the v1 case, and left the v1-only `from pydantic import Field,
   validator` import (line 16) now unused (confirmed via pyflakes: `'pydantic.
   validator' imported but unused`). If pydantic ever resolved to v1 in some
   environment, `Settings` would be undefined and `settings = Settings()` (last
   line of the file) would raise `NameError` at import time — i.e. the whole
   backend would fail to start. Low real-world risk given the pin, but it's a
   half-finished deletion: either finish removing the `try/except` entirely (go
   pydantic-v2-only everywhere) or keep both branches; the current straddle is
   strictly worse than either.

2. `backend/api/readymode.py:44-46` — `MIN_CALL_DURATION_S` is imported from
   `automation.download_readymode_calls` but never referenced anywhere in
   `readymode.py` (confirmed via pyflakes and grep — only used inside
   `automation/download_readymode_calls.py` itself). Unused import, safe to drop.

3. `backend/main.py:67` — `_phrase_manager = PhraseLearningManager()` inside the
   startup `lifespan` is assigned to a local that's never read (flagged by
   pyflakes). Harmless (construction has the real side effect, logged on the next
   line) but the dead binding invites a reader to think something downstream uses
   it.

## Special Cases

1. `backend/api/readymode.py` `stream_readymode_audit`'s `worker` special-cases
   `ReadyModeNoCallsError` into a synthetic **`done`** event with zero counts
   (lines 528-530) rather than an `error` event, while every structurally similar
   failure (`ReadyModeLoginError`, generic `Exception`) becomes an `error` event.
   That's a deliberate product decision (no calls found isn't really a failure)
   but it's encoded only as an ad hoc branch in one worker, not as a documented
   convention — a new SSE endpoint added later has no way to know "zero results"
   should be `done`, not `error`, unless someone remembers this one call site.

2. `backend/api/auth.py:81-82` — the owner hard-bypass is itself a special case
   ("Hard bypass for primary owner to prevent lockout") layered on top of the
   normal whitelist lookup, duplicated a second time a few lines later (line 101)
   for the role-escalation check. Two special-cased branches for one person,
   independent of the `OWNER_EMAILS`/`PROTECTED_OWNER_EMAIL` mechanism that exists
   for exactly this purpose elsewhere in the codebase (see Hidden Links #1).

## Not re-flagged (checked, still fine)

- The three old independently-reinvented SSE scaffolds the `sse.py` docstring
  describes (`readymode_users.py` ×4, `scoring.py` ×2, `readymode.py` ×1) have all
  been fully migrated to `run_sse_stream`/`SSEEmitter` — no leftover
  `StreamingResponse`/local `_sse()` copies remain anywhere under `backend/`.
- `backend/core/security.py`'s SHA256 `hash_password`/`verify_password` were
  removed cleanly; no dangling callers remain in `backend/`.
- `backend/api/health.py`'s six endpoints all consistently re-raise
  `HTTPException` before the generic `except Exception` handler (no partial fix
  left on some endpoints but not others).
- `backend/api/jobs.py`'s previously-missing `get_job` import (which would have
  caused `get_job_status_endpoint` to `NameError` at call time) has been added.
