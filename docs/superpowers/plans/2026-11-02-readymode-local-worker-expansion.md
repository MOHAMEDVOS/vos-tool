# Plan: Expand ReadyMode Local Worker

## Problem

The local worker currently runs Scoring → Gather only. Audit recording downloads, the Find busiest dialer lookup, and ReadyMode user creation still run on Railway, where ReadyMode may challenge the cloud request.

## Chosen approach

Extend the existing authenticated worker queue without changing ReadyMode authentication. Keep audit audio in Railway storage by streaming it from ReadyMode through the local worker directly to Railway. Store temporary user-creation passwords separately as encrypted, short-lived job secrets. Keep Railway as the default execution mode and route each feature locally only when the Owner setting selects Local worker.

## Files

- `automation/readymode_local_worker.py`: handle dialer counts, streamed audit recordings, and ReadyMode user creation.
- `backend/api/readymode.py`: route Find busiest dialer and audit streaming through local jobs.
- `backend/api/scoring.py`: route Scoring Audit recordings through the worker.
- `backend/api/readymode_worker.py`: claim and validate recording uploads on Railway storage.
- `backend/services/readymode_worker_service.py`: encrypt short-lived user-creation secrets and clean them up.
- `backend/api/readymode_users.py`: stream local user-creation progress and results.
- `webapp/src/pages/SettingsPage.tsx`: describe the expanded Owner execution-mode setting.
- `migrations/versions/0005_readymode_worker_secrets.py`: store encrypted job secrets with expiry.
- `docs/READYMODE_LOCAL_WORKER.md`: document the expanded scope and storage behavior.

## Verification

- Review the affected request paths and secret handling manually.
- Run `git diff --check` only; do not submit ReadyMode credentials or make live calls during implementation.

## Risks

The local worker must remain running while a job is active. Recording bytes travel through the worker in chunks and are written to Railway's configured recording storage; no audio files are written to the worker computer. If upload or analysis fails, claimed recordings must be released for a later run.
