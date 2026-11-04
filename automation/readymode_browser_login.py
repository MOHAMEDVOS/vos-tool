"""Browser-based ReadyMode login fallback for Cloudflare's JS challenge.

``ReadyModeHTTPClient.login()`` (automation/readymode_http.py) is pure HTTP and cannot
execute JavaScript, so it can never pass Cloudflare's "Just a moment..." challenge on
its own. This module launches a real (optionally headful, under Xvfb) Chromium via
Playwright ONLY to solve that one challenge, then hands the resulting cookies back so
the caller can keep using its fast requests.Session for everything else (user creation,
scoring, report fetches). Nothing else in the project switches to browser automation.

Reuses the login form-filling logic from ``download_readymode_calls_playwright.py``
(the project's previous, proven-working Playwright login) rather than duplicating it.

Toggle with READYMODE_BROWSER_FALLBACK=0 to disable this fallback entirely (falls back
to the original "raise ReadyModeLoginError" behavior) if it causes problems on Railway.
"""

import logging
import os

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # playwright not installed in this environment
    sync_playwright = None


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def browser_fallback_enabled() -> bool:
    return _env_flag("READYMODE_BROWSER_FALLBACK", True) and sync_playwright is not None


def solve_login_with_browser(dialer_url: str, username: str, password: str) -> dict:
    """Log into ``dialer_url`` with a real browser and return the resulting cookies.

    Raises RuntimeError if playwright isn't installed, or whatever error
    ``login_to_readymode`` raises (automation.download_readymode_calls_playwright's
    own ReadyModeLoginError) if the browser login itself fails for a non-Cloudflare
    reason (bad credentials, form not found, etc.) — the caller should treat that the
    same as the original HTTP failure.
    """
    if sync_playwright is None:
        raise RuntimeError(
            "playwright is not installed; cannot fall back to a browser login for the "
            "Cloudflare challenge. Install it with `pip install playwright` and "
            "`playwright install --with-deps chromium`."
        )
    # Local import: avoids a circular import (download_readymode_calls_playwright
    # imports from readymode_http, which would import this module, which would
    # import download_readymode_calls_playwright back) and keeps this module
    # importable even when that sibling module's other dependencies aren't needed.
    from automation.download_readymode_calls_playwright import login_to_readymode

    headless = _env_flag("READYMODE_HEADLESS", False)
    slow_mo_ms = int(os.getenv("READYMODE_SLOW_MO_MS", "0") or "0")

    logger.info(
        "ReadyMode browser-login fallback: launching chromium (headless=%s) for %s",
        headless, dialer_url,
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            slow_mo=slow_mo_ms,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        try:
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            page = context.new_page()
            login_to_readymode(page, dialer_url, username, password)
            cookies = {cookie["name"]: cookie["value"] for cookie in context.cookies()}
            logger.info(
                "ReadyMode browser-login fallback succeeded for %s (cookies=%s)",
                dialer_url, sorted(cookies.keys()),
            )
            return cookies
        finally:
            browser.close()
