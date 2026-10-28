# ReadyMode browser connector plan

## Problem

The ReadyMode HTTP client gets Cloudflare challenges when VOS logs in from Railway. The captured failing workflow is the read-only agent dialer count check in `backend/api/readymode.py`; the user asked for a no-support option.

## Options considered

1. Change HTTP headers. Local requests also receive challenge HTML, so this does not address the session gate.
2. Use ReadyMode's official API. Public docs do not provide a self-serve call-log API specification, and the user does not want to involve support.
3. Use the user's existing signed-in Chrome session through a narrowly scoped extension. This avoids moving passwords or cookies and is the selected approach.

## Implementation

The MV3 extension uses the signed-in Chrome session to read report pages, download selected audio, and upload it to an authenticated VOS endpoint. VOS then uses its existing duration checks, recording deduplication, analysis, and audit-saving path. It never reads or exports cookie values or ReadyMode passwords. The existing server login remains as a fallback when the extension is not installed.

The extension is restricted to the VOS app/API and the seven ReadyMode dialer hosts. Voicemail is excluded in both the extension and backend. The browser import endpoint validates dialer hosts and audio files, claims recording IDs through the existing registry, and limits each request to 90 MB to fit the VOS Nginx proxy.

## Success and limits

The earlier live count test returned counts from the two ReadyMode dialers signed in to this Chrome profile. The new download/import path passes mocked browser-flow tests and backend import tests, and the webapp builds. A full live audio audit has not been run and these changes have not been deployed, so production is not fixed yet. Campaign counting and ReadyMode user management still use the existing server login flow.

## Security

The extension uses host permissions for the VOS app/API and seven ReadyMode hosts only. It requests no `cookies`, `tabs`, or storage permission and does not automate login or challenges. For audits, selected call audio is sent to the authenticated VOS account that started the run.
