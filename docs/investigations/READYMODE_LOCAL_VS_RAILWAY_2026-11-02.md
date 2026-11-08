# ReadyMode initial GET: matched local runtime vs Railway

**Date:** 2026-11-02  
**URL:** `https://resva.readymode.com/`  
**Test scope:** Initial GET only. No credentials were loaded and no login POST was sent.

## Runtime and dependency files

| Package | Local original | Local matched test | Railway running image |
|---|---:|---:|---:|
| Python | 3.12.14 | 3.11.18 | 3.11.18 |
| requests | 2.34.2 | 2.34.2 | 2.34.2 |
| urllib3 | 2.7.0 | 2.8.0 | 2.8.0 |
| certifi | 2026.07.22 | 2026.10.23 | 2026.10.23 |
| charset-normalizer | 3.5.1 | 3.5.2 | 3.5.2 |

Railway versions came from its running backend diagnostic startup log. The requirements files use minimum-version ranges (`requests>=...`); no `pyproject.toml` or `poetry.lock` is present. The backend Dockerfile uses `python:3.11-slim`, while the observed running image reports Python 3.11.18.

## Initial GET comparison

| Signal | Local Python 3.11.18 with Railway package versions | Railway | Difference |
|---|---|---|---|
| Method / request URL | `GET https://resva.readymode.com/` | Same | None |
| User-Agent | `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36` | Same | None |
| Accept | `text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8` | Same | None |
| Accept-Language | `en-US,en;q=0.9` | Same | None |
| Accept-Encoding | `gzip, deflate` | Same | None |
| Other safe request headers | Origin, Referer, Sec-Fetch, Upgrade-Insecure-Requests match | Same | None among captured headers |
| Redirect history | 302 `/` → 301 `/login_new?then=%2F` | 302 `/` only | Railway is blocked before the slash-canonicalization redirect completes. |
| Final status / URL | 200, `/login_new/?then=%2F` | 403, `/login_new?then=%2F` | Different response path after the first redirect. |
| CF-Mitigated | Absent | `challenge` | Cloudflare explicitly marks the Railway response as a challenge. |
| CF-Ray | `a544bbefec7e8a1c-MRS` | `a544a3892d413117-SJC` | Different edge suffixes; not evidence of the source IP or rule. |
| Retry-After | Absent | Absent | None |
| Other response headers | `Server: cloudflare`, `CF-Cache-Status: DYNAMIC`, HTML content type, `X-Robots-Tag` | `Server: cloudflare`, HTML content type, CSP, `X-Content-Type-Options`, `X-Frame-Options` | Consistent with a normal login page locally and a Cloudflare challenge page on Railway. |
| Body classification | Normal ReadyMode login HTML; `security_block=no known marker` | `Just a moment...` Cloudflare challenge HTML | Challenge only on Railway. |
| Initial cookie names | `PHPSESSID`, `__cf_bm`, `seH` | Same | Names match; values were not captured, so value-level comparison is intentionally unavailable. |

## Result

Matching Python 3.11.18 and all four HTTP dependency versions **did not change the local result**: the initial GET still returned HTTP 200 and the ReadyMode login page. Railway returned HTTP 403 with `CF-Mitigated: challenge`.

This rules out the observed Python and Requests dependency versions as the cause of the difference. The logged request headers and initial cookie names also match. It does **not** prove an outbound-IP block: Cloudflare's source-IP decision, rule, and bot score are not exposed in these logs. TLS/runtime fingerprint details beyond the reported package versions were not compared.

The classifier was corrected in `automation/readymode_http.py`: a normal response below 400 is no longer classified from body text alone; `CF-Mitigated: challenge` remains an explicit challenge signal. The matched local run now reports `security_block=no known marker`.

## Next legitimate troubleshooting step

Investigate Railway's outbound network/IP path and the applicable Cloudflare security decision next. Check the Railway service's egress-IP/network information and, if you have access to the ReadyMode Cloudflare settings, inspect the rule associated with the Railway `CF-Ray`. Treat IP-based blocking as a hypothesis until a rule or source-IP decision confirms it. Do not alter headers, credentials, or authentication behavior based on this test.

No passwords, cookie values, authorization headers, CSRF tokens, or session identifiers are included here.
