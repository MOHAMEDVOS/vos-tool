# ReadyMode login 403 investigation

## Finding

The reported audit failure is at ReadyMode authentication, before call search or recording download. The HTTP login client requires the `stationId` cookie after submitting the login form; the reported response was HTTP 403 with Cloudflare's “Just a moment…” HTML instead.

## Local read-only probe

Using the same `ReadyModeHTTPClient` headers and session, an unauthenticated GET to both the dialer landing page and `/login_new/?then=/` returned HTTP 200 during this investigation. The session received `PHPSESSID`, `seH`, and Cloudflare's `__cf_bm` cookie, and neither response was the challenge page. This shows that the landing/login form is reachable from this machine; it does not reproduce the blocked login POST.

## Code path and likely cause

`ReadyModeHTTPClient.login()` submits credentials to `/login_new/?then=/` with `logout_other_sessions=on`, then raises the observed error if `stationId` is absent. Since manual browser sign-in succeeds but the automated POST returned a Cloudflare challenge, credentials are less likely to be the cause; Cloudflare is treating the automated login POST/session differently. The configured User-Agent string is abbreviated and may be one factor, but that has not been verified.

## Follow-up attempt

The user explicitly approved a full login attempt, including the possibility of ending other sessions. The local checkout could not retrieve the saved ReadyMode credentials: its PostgreSQL configuration points to localhost, where no server is running, and no system-level ReadyMode credential pair is configured. Therefore the login POST was not sent. No password or credential value was printed.

The user then supplied test credentials. Two local login submissions were made without logging or printing those values. Both returned HTTP 200, did not contain the Cloudflare challenge page, and did not establish a `stationId` cookie. A sanitized scan did not detect a clear invalid-password message or an existing-session interstitial, so this local result is inconclusive. It differs from the Railway failure (403 plus Cloudflare challenge) and cannot establish whether the supplied credentials are valid.

At the user's direction, the supplied test credentials were then tried only against `resva2.readymode.com`. Login succeeded locally, a `stationId` cookie was issued, and the read-only call-log form loaded with 17 disposition options. No recordings were downloaded. This confirms the credentials and HTTP client work with resva2 from the local machine. It does not yet confirm whether Railway can log in to resva2; the captured Railway 403 logs correspond to the earlier resva host.

After Railway access was restored, the same sanitized test was run from inside the deployed Backend VOS service against `resva2.readymode.com`: login succeeded, `stationId` was present, and the call-log form loaded with 17 disposition options. No recordings were downloaded. The temporary Railway SSH key was removed after the check. This confirms Railway can authenticate to resva2; the earlier failure is isolated to the resva host tested in the original error.

## Next diagnostic boundary

The original Railway failure still needs to be reproduced from the deployed environment that has the saved credentials. If the POST there still receives a Cloudflare challenge, ask ReadyMode support for a supported integration or allowlist path; do not try to bypass the challenge.
