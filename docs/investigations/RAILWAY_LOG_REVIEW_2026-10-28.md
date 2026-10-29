# Railway log review — 2026-10-28

## Scope

Read-only review of the Railway log pasted on 2026-10-28. The log shows a successful service start followed by normal API traffic, plus three warnings/failures that merit separate follow-up.

## Findings

### Service startup and request handling

The backend completed startup and began listening on port 8080. The semantic model and database initialized, the phrase-learning manager loaded, and later user, dashboard, and scoring requests returned HTTP 200. The model work took about two minutes: encoding 391 hardcoded phrases took 115.68 seconds, then learned phrases were loaded in the background. This is a startup delay, not a failed deployment in this log.

The Hugging Face unauthenticated warning and Google API Python 3.11 future warning did not stop startup. They are informational maintenance items here.

### ReadyMode dialer counts

At 15:23, login attempts to all seven configured `resva*` dialers received HTTP 403 with Cloudflare's “Just a moment…” challenge page. The API endpoint itself returned HTTP 200 after recording those dialers as failures. This means the request completed but the count results may be incomplete or empty. The failure occurs before ReadyMode session creation, not during report parsing. See the earlier [ReadyMode login 403 investigation](READYMODE_LOGIN_403.md); this log confirms the Railway-side Cloudflare challenge across the dialers.

### CORS preflight

At 15:31, `OPTIONS /api/auth/google` returned 400. A Google login completed successfully at 15:32, so the log does not show a persistent auth outage. `CORSMiddleware` allows only the origins in `CORS_ORIGINS` (or its configured defaults). The request log omits `Origin`, `Access-Control-Request-Method`, and `Access-Control-Request-Headers`, so the exact reason for the 400 cannot be determined from this capture. Compare the failing browser origin with the deployed backend's `CORS_ORIGINS`; also inspect the browser's preflight request and response headers.

### Timestamp parsing warnings

`POST /api/scoring/gather` returned HTTP 200, then `backend/services/dashboard_service.py:34` emitted a pandas warning because `pd.to_datetime` could not infer one consistent timestamp format and fell back to parsing each value individually. It may be a performance or data-consistency issue for mixed timestamp inputs; the log does not show parse failures or incorrect filtering. Inspect representative timestamp values and the scoring date filters before changing parsing behavior.

## Suggested order

1. Treat the ReadyMode Cloudflare challenge as the main functional issue; confirm whether the failed dialers caused missing counts. User preference: do not contact ReadyMode support.
2. If users reported login trouble, capture the failed browser preflight's origin and requested method/headers, then compare with Railway `CORS_ORIGINS`.
3. Check timestamp value formats only if scoring date filtering is inaccurate or slow; the captured scoring requests succeeded.

## Review plan followed

Considered (1) change code immediately, (2) inspect deployment configuration, and (3) document the findings and identify the missing evidence. Chose option 3 because the pasted log contains no explicit fix request, and the CORS and timestamp issues cannot be safely corrected without the missing request/value details. No runtime code or deployment settings were changed.

## Follow-up: Current ReadyMode path

The Chrome extension connector was removed on 2026-10-29 at the user's request. Agent and Campaign audit downloads now use the historical server-side Playwright implementation from before commit `7f489b1`; the auxiliary busiest-dialer checks continue to use the pure-HTTP client. The Cloudflare challenges documented above may still affect those HTTP checks.
