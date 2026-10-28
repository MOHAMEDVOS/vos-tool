# Plan: Skip ReadyMode recordings that were already audited

## Problem

Repeated ReadyMode searches can return the same recording. The tool downloads it into a new run folder and audits it again, spending download time and AssemblyAI/LLM usage.

## Findings

- `automation/download_readymode_calls.py::_collect_tasks_for_dialer` reads ReadyMode's `RecId` and only deduplicates it in a local `seen_links` set. That set is reset for every request.
- Each request gets a new timestamped run directory, so the existing file paths do not prevent a later download.
- Agent and Lite audit rows save filenames, file paths, and metadata, but do not save ReadyMode's `RecId`. Existing rows therefore cannot be matched to future report rows with certainty.
- `docs/READYMODE_HTTP_SPEC.md` documents `RecId` as the MP3 path. It is the best stable source identity available; the dialer host should be included in the key.

## Options

1. Search old filenames for matching agent, time, phone, and disposition. This avoids a schema change, but those fields are not guaranteed unique and cannot prove that two rows are the same recording.
2. Keep a JSON manifest beside downloaded files. This is simple, but concurrent requests can race and a lost/removed volume loses the deduplication history.
3. Keep a database ledger keyed by VOS audit scope, dialer host, and normalized `RecId`. A unique key prevents concurrent requests from claiming the same recording twice and the row can track download/audit status.

## Implementation

Use a database ledger with a unique key of VOS username, canonical dialer host, and normalized `RecId`. The downloader claims report rows before queuing downloads, skips records already audited or actively claimed, and releases failed downloads. The API marks records audited only after audit results have been saved, then releases any remaining claims. Claims expire after six hours so interrupted work can be retried. The Audit page has an explicit re-audit checkbox.

The `/stream` result reports downloaded, analyzed, and skipped counts. Saved audit metadata includes the ReadyMode recording ID and dialer host. A versioned Alembic migration creates the ledger; backend startup applies it after the existing schema setup.

## Historical records

Old audit rows have no ReadyMode `RecId`, and filenames omit it. Exact deduplication starts after deployment; existing history cannot be safely backfilled from those fields alone. A one-time best-effort match on phone, agent, timestamp, dialer, and disposition could confuse two distinct calls with matching metadata, so it is not used.

## Files and work

- `automation/readymode_http.py` and `automation/download_readymode_calls.py`: normalize ReadyMode IDs, claim rows before download, and write a per-run manifest.
- `backend/api/readymode.py`: attach source identity to audit rows, mark successful saves, release failed work, and report skipped counts.
- `backend/services/readymode_recording_registry.py`: maintain claim, completion, failure, and re-audit state.
- `backend/core/database.py` plus a versioned migration: create the unique recording ledger and apply it during backend startup.
- `lib/dashboard_manager.py`: save recording identity with Lite audit metadata.
- `tests/test_readymode_record_deduplication.py`: cover ledger state, user/dialer isolation, deliberate re-audits, ID normalization, and skipping before download.

## Verification and risks

- SQLite migration and registry-state checks pass; repeated claimed IDs are excluded before `download_single_file` runs.
- Different users and dialer hosts have independent ledger entries; an explicit re-audit can claim an audited record.
- PostgreSQL behavior uses the same unique key and `ON CONFLICT` claim path but still needs deployment verification against the configured Railway database.
- Exact matching is only possible for records audited after the ledger is deployed.
