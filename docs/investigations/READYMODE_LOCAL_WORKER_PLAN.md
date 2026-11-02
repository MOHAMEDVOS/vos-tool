# ReadyMode local worker — evaluation plan

**Status:** Implementation started for the reversible first phase: owner-controlled Railway/local selection and Scoring → Gather only. The authentication implementation is unchanged. See [`READYMODE_LOCAL_WORKER.md`](../READYMODE_LOCAL_WORKER.md) for setup. Audit audio and ReadyMode account operations remain future phases.

## Problem and goal

ReadyMode works from Mohamed's local network but Railway's backend receives a Cloudflare challenge. A local worker could make the same existing ReadyMode HTTP requests from the local computer, while VOS keeps its database, UI, scoring logic, audit logic, and dashboards on Railway.

The first goal would be to prove the worker can securely pick up and complete a small read-only ReadyMode task. It must not bypass Cloudflare, rotate IPs, imitate a browser, or change the ReadyMode authentication flow.

## Options considered

1. **Move the existing ReadyMode HTTP work to a local worker.** VOS creates a job on Railway; a signed-in worker makes the same requests through `ReadyModeHTTPClient` from the local internet and returns the results. This addresses the network-path difference while leaving the product UI and most processing in the cloud. **Recommended if the ReadyMode response does not resolve the challenge.**
2. **Run the whole VOS backend locally.** This could keep ReadyMode and processing near each other, but it also moves database access, AI calls, application secrets, and more of the VOS service onto the computer. It has a much larger setup and support burden.
3. **Keep making Railway network or region changes.** This is a smaller experiment, but the new Railway address could still receive a Cloudflare challenge, and it does not provide a reliable fallback.

The existing ReadyMode client uses ordinary `requests` calls. Its authentication/session behavior can stay the same; the main design work is how a local process receives jobs and returns results safely.

The worker must be optional. The same job interface should support a Railway executor and a local-worker executor, selected by a setting. If ReadyMode resolves the Railway challenge later, switch back to the Railway executor and leave the local worker stopped; no ReadyMode requests should need to be rewritten. Keep the local worker as a fallback only if it remains useful.

Add an owner-only selector in the Owner Settings panel, for example **ReadyMode runs on: Railway / Local worker**. Only the Owner can view or change it. Changing the selector affects new jobs only. Existing jobs finish on their current executor unless the user cancels them. When switched to Railway, the local worker receives no new jobs and can go idle/stop polling; the setting does not shut down the user's computer or forcibly terminate its process.

## Existing ReadyMode request inventory

The active backend calls the pure-HTTP client in [`automation/readymode_http.py`](../../automation/readymode_http.py). These are the ReadyMode requests the worker would need to support:

| Operation | ReadyMode request sequence | Used by |
|---|---|---|
| Login/session | `GET /` to seed the cookie jar; then `POST /login_new/?then=/` with the existing form and headers. Keep the resulting cookies in memory for that dialer session. | Every ReadyMode operation below |
| Call-log initialization | `POST /CCS%20Reports/call_log`; parse that dialer's live disposition IDs. | Call downloads, CSV exports, agent counts where live types are needed |
| Call report data | `GET /CCS%20Reports/call_log/update` with date range, disposition IDs, optional agent/campaign IDs, and page number. Loop pages as required. | Audits, campaign/agent counts, delete-name resolution, duplicate scans, scoring report queries |
| Call-log CSV | Initialize call log, `GET .../call_log/update` to set the report filters, then `POST /CCS%20Reports/call_log/ExportMenu/CL.csv` with the requested columns. | Scoring gather; campaign reachability and long-VM/dead-call scans |
| Recording audio | For each selected report row, `GET <RecId>?force_dl=1` using that dialer's session cookies. | Heavy audits and the scoring audit flow |
| Writable folders | `GET /Team/ManageUsers/createUser`; parse folder names and dialer-specific IDs. | ReadyMode user creation; user listing/deletion scans |
| Create a ReadyMode user | `POST /Team/ManageUsers/createUser/save`, once per target user, with that target's name, login, extension, folder, OU, and password. | Bulk ReadyMode user creation |
| List folder users | `POST /Folders/Folder=<folder_id>` once per folder; parse the folder roster. | Duplicate/inactive scans and deletion when a user isn't found in the call-log user list |
| Delete a ReadyMode user | `GET /Folders/fileAction/Delete/User=<uid>`. The UID is dialer-specific; deletion must stay behind the existing admin check and explicit UI action. | Bulk ReadyMode user deletion |
| Agent activity | `POST /CCS%20Reports/agent` to load preset `P134`, then POST again with the requested date range; one bounded repeat is currently allowed if the report echoes back the wrong range. | Inactive-user scan |

CSV and recording export details, including fields and report parameters, are documented in [`docs/READYMODE_HTTP_SPEC.md`](../READYMODE_HTTP_SPEC.md). The old Playwright downloader exists in the repository, but current backend routes call the pure-HTTP downloader; this plan follows the active pure-HTTP path.

## What does not need to move

- **VOS Settings:** `/api/settings/` reads and writes VOS settings in the database. Saving a user's ReadyMode username/password does not call ReadyMode. The worker would need a safe way to use the saved per-user credentials for a ReadyMode job.
- **VOS user administration:** `/api/settings/users` creates, edits, and deletes VOS accounts in the VOS database. This is separate from creating or deleting agent accounts on ReadyMode.
- **Scoring:** `/api/scoring/gather` needs ReadyMode CSVs. `/generate` uses the gathered data locally and makes no ReadyMode call. `/audit` also downloads recordings from ReadyMode. `/export-sheet` sends results to Google Sheets, not ReadyMode.
- **Call Review playback:** The player requests `/api/system/recordings/serve`, which serves the MP3 by the saved `File Path` (or filename/phone fallback) from Railway's recordings directory. Therefore, audio selected for Call Review must persist on Railway's mounted `RECORDINGS_ROOT` volume; deleting it immediately after analysis would break playback.
- **Audit analysis and storage:** Transcription, detection, scoring, saving audit results, and dashboard updates can remain on Railway in the first design. Recording bytes travel from ReadyMode through the local worker to the Railway backend over HTTPS, then playback files stay on Railway's volume. Retention duration and cleanup need a separate product decision.

## Proposed worker flow

1. The normal VOS user starts an operation in the existing UI. Railway validates the user's permissions and stores a durable job with operation, dialer, filters/targets, owner, and status. Passwords, cookies, and audio should not be written to the job record.
2. A selected executor claims the job: either the current Railway backend/worker or the local computer's worker. When local mode is selected, the worker opens an **outbound HTTPS** connection to Railway and polls or long-polls for work. It does not listen on a public port. Railway reports `waiting for local worker` when the computer is offline.
3. The worker claims one job, executes the existing ReadyMode HTTP calls locally, keeps ReadyMode cookies only in process memory, and posts progress and the result to Railway over HTTPS.
4. For CSV-only tasks, the worker returns CSV bytes or normalized rows. Railway continues its current scoring and reachability processing.
5. For audit tasks, the worker streams recording bytes directly from ReadyMode to an authenticated Railway upload route using a bounded in-memory buffer. It must never write recordings, CSVs, or other call data to local disk. Railway writes recordings needed for playback to its persistent `RECORDINGS_ROOT` volume, runs transcription and scoring, and keeps those files available to Call Review.
6. Railway records completion/failure and the existing UI continues to poll or stream job status. Cancellation marks the job cancelled and the worker stops between requests and downloads.

The worker control routes would need authenticated job claim, progress/heartbeat, completion/failure, cancellation, and (for audits) binary upload. These are new private-to-the-product endpoints, protected by a dedicated revocable worker credential and per-job authorization. No unauthenticated diagnostic or worker endpoint should be exposed. The existing user JWT should not be copied into the worker as a permanent credential.

## Credentials, privacy, and local storage

- Today the VOS database stores each VOS user's ReadyMode credentials. The worker needs the correct user's ReadyMode username/password for the task, plus any new agent password for a create-user job. A design decision is required: deliver credentials to the authenticated worker over TLS for memory-only use, or encrypt each short-lived credential payload to a worker key stored in the computer's OS keychain. Do not put ReadyMode passwords in Redis/Celery payloads, logs, local files, or job results.
- Cookies and session IDs stay only in the worker's in-memory `requests.Session` and are discarded when the dialer task ends.
- **No local call-data storage is allowed.** CSV data stays in memory and recording audio is streamed through a small bounded memory buffer from ReadyMode to Railway. The worker does not spool, cache, or queue call data on disk. Audio uses the local internet to download from ReadyMode and upload to Railway. Railway keeps the playback copies on its persistent volume for the chosen retention period; those files are not stored on the local computer.
- Creating users sends the new user's password through the worker to ReadyMode. Deleting users is destructive and should be implemented last, with the current admin authorization, exact dialer-scoped UID, confirmation, and a result check. ReadyMode's delete response is currently only confirmed by HTTP status, so it does not prove the user disappeared.
- A computer that sleeps, shuts down, or loses internet pauses local work. Jobs need leases, heartbeats, timeouts, safe resume rules, and visible waiting/error status.

## Suggested phases

1. **Read-only pilot (in progress):** add the authenticated worker connection and run scoring `gather`. It exercises login, CSV export, result upload, progress, and worker-offline behavior without downloading audio or changing ReadyMode accounts.
3. **Read-only roster tools:** duplicate and inactive scans; confirm job cancellation, multi-dialer limits, and accurate failure reporting.
4. **Audit recordings:** implement bounded-memory streaming of audio, cloud processing, persistent Railway storage for Call Review, and restart/cancel behavior. Confirm that interrupted transfers discard in-memory data and safely restart without local disk spooling.
5. **Account changes:** add ReadyMode create operations, then deletion last. Require confirmation and idempotency protections for retries.

## Decision and success checks

The main tradeoff is new worker security/maintenance and local internet use versus keeping ReadyMode access on the network where it currently succeeds. A CSV-only pilot is moderate work; full auditing plus safe user management is a larger feature.

Before deciding to build, confirm:

- ReadyMode's response and whether the existing Railway egress should be allowed to log in.
- The operating mode to use by default: Railway, local worker, or an explicitly selected fallback.
- Whether the local computer can stay awake and connected during audits.
- Whether short-lived credential delivery to that computer is acceptable.
- The required retention period for Call Review recordings stored on Railway's volume.
- Whether the pilot should use one ReadyMode account or preserve each VOS user's saved credentials.

Success would mean the pilot handles a real read-only gather from the local worker, shows clear progress and errors in the existing UI, stores no ReadyMode passwords/cookies in job data or logs, writes no call data to the local computer's disk, preserves Call Review playback from Railway's volume, leaves the normal ReadyMode HTTP request sequence unchanged, and can switch back to Railway execution without changing that sequence.
