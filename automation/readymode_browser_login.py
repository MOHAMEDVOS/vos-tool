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
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # playwright not installed in this environment
    sync_playwright = None

# Where failed-challenge screenshots/HTML get saved for later inspection via the
# /api/readymode/debug/challenges endpoint (backend/api/readymode.py). Lives on the
# same persistent volume as recordings (RECORDINGS_ROOT), not /tmp, so it survives
# past the request and can be viewed after the fact instead of only in logs.
def _debug_dir() -> Path:
    try:
        from config import RECORDINGS_ROOT
        base = Path(RECORDINGS_ROOT).parent
    except Exception:
        base = Path("/data")
    debug_dir = base / "readymode_debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    return debug_dir


def _save_challenge_debug_snapshot(page, dialer_url: str) -> None:
    """Best-effort: save a screenshot + the page HTML so a human can see exactly
    what the browser was looking at when it gave up. Never raises — a failure here
    must not mask the real ReadyModeLoginError."""
    try:
        host = urlsplit(dialer_url).hostname or "dialer"
        slug = re.sub(r"[^A-Za-z0-9_-]", "_", host)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        base_name = f"{slug}_{stamp}"
        debug_dir = _debug_dir()
        png_path = debug_dir / f"{base_name}.png"
        html_path = debug_dir / f"{base_name}.html"
        page.screenshot(path=str(png_path), full_page=True)
        html_path.write_text(page.content(), encoding="utf-8")
        logger.warning(
            "ReadyMode browser-login fallback: saved failure snapshot %s / %s "
            "(view via GET /api/readymode/debug/challenges)",
            png_path.name, html_path.name,
        )
    except Exception as snapshot_error:
        logger.warning(
            "ReadyMode browser-login fallback: could not save failure snapshot: %s",
            snapshot_error,
        )


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def browser_fallback_enabled() -> bool:
    return _env_flag("READYMODE_BROWSER_FALLBACK", True) and sync_playwright is not None


# Vanilla Playwright/Chromium sets several JS-detectable automation markers
# (navigator.webdriver=true, no window.chrome, empty plugin list) that Cloudflare's
# bot score checks for. One dialer (resva) was observed holding the "Just a moment"
# interstitial indefinitely against an un-patched browser while another (resva5) let
# it through, which is consistent with resva's zone having a stricter check. This
# script patches the most common markers before any page JS runs. It's not a
# guarantee against a true interactive/managed challenge, but it removes the cheap,
# well-known tells.
_STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = window.chrome || { runtime: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
if (originalQuery) {
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters)
    );
}
"""


# Confirmed via a saved failure screenshot (2026-11-04): resva's challenge is
# Cloudflare Turnstile's visible "Verify you are human" checkbox, not a silent/
# non-interactive block. Turnstile is specifically built to flag non-human click
# patterns (timing, mouse movement), so a scripted click is not guaranteed to pass —
# this is a deliberate, informed choice to try it anyway rather than a reliable fix.
#
# The checkbox itself lives deep inside Turnstile's iframe content (not a plain
# <input type="checkbox"> Playwright's frame_locator can select into directly — the
# first attempt at this via a DOM selector timed out and never clicked anything).
# Click by SCREEN POSITION instead: get the outer iframe element's bounding box on
# the page and click near its left edge, vertically centered — that's where the
# checkbox renders — the same way a real mouse click lands on whatever is visually
# there, regardless of what's inside the iframe's own DOM.
def _attempt_turnstile_click(page) -> bool:
    """Best-effort: click Cloudflare's Turnstile checkbox by screen position.
    Returns True if a click was attempted (not whether it was accepted)."""
    try:
        iframe_el = page.locator("iframe[src*='challenges.cloudflare.com']").first
        iframe_el.wait_for(state="visible", timeout=10000)
        box = iframe_el.bounding_box()
        if not box:
            logger.info(
                "ReadyMode browser-login fallback: Turnstile iframe found but has no "
                "bounding box (not rendered yet) — continuing without a click"
            )
            return False
        click_x = box["x"] + 30
        click_y = box["y"] + box["height"] / 2
        page.mouse.click(click_x, click_y)
        logger.info(
            "ReadyMode browser-login fallback: clicked the Turnstile checkbox area "
            "at (%.0f, %.0f)", click_x, click_y,
        )
        return True
    except Exception as click_error:
        logger.info(
            "ReadyMode browser-login fallback: could not click the Turnstile "
            "checkbox area (%s) — continuing without a click",
            click_error,
        )
        return False


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
    from automation.download_readymode_calls_playwright import (
        login_to_readymode,
        ReadyModeLoginError as PlaywrightLoginError,
    )

    headless = _env_flag("READYMODE_HEADLESS", False)
    slow_mo_ms = int(os.getenv("READYMODE_SLOW_MO_MS", "0") or "0")
    # login_to_readymode's own form-wait runs ~60s per attempt, so blindly retrying it
    # is expensive and does nothing by itself — it only helps if a Turnstile click
    # already set the cf_clearance cookie in this context. Keep this as a small safety
    # net (2, not 3+), not the primary mechanism.
    max_attempts = int(os.getenv("READYMODE_BROWSER_LOGIN_ATTEMPTS", "2") or "2")

    logger.info(
        "ReadyMode browser-login fallback: launching chromium (headless=%s) for %s "
        "(up to %d attempt(s))",
        headless, dialer_url, max_attempts,
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
                "--disable-blink-features=AutomationControlled",
            ],
        )
        try:
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            context.add_init_script(_STEALTH_INIT_SCRIPT)
            page = context.new_page()

            # Pre-step: navigate ourselves and try clicking past a visible Turnstile
            # checkbox before handing off to login_to_readymode (which does its own
            # navigation + form wait on each retry attempt below). Two short click
            # attempts (a few seconds each) are much cheaper than burning a full ~60s
            # login_to_readymode attempt on a challenge that was never clicked. If a
            # click succeeds, Cloudflare's cf_clearance cookie is set in this context
            # and carries over to login_to_readymode's subsequent navigation.
            page.goto(dialer_url, wait_until="domcontentloaded")
            for click_round in range(2):
                if not _attempt_turnstile_click(page):
                    break  # no Turnstile widget found at all — nothing more to click
                page.wait_for_timeout(4000)
                title = page.title()
                if "just a moment" not in title.lower():
                    logger.info(
                        "ReadyMode browser-login fallback: challenge appears cleared "
                        "after click round %d (title=%r)", click_round + 1, title,
                    )
                    break

            last_error: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    login_to_readymode(page, dialer_url, username, password)
                    last_error = None
                    break
                except PlaywrightLoginError as error:
                    last_error = error
                    logger.warning(
                        "ReadyMode browser-login fallback attempt %d/%d on %s did not "
                        "find the login form yet (likely still on the Cloudflare "
                        "challenge): %s",
                        attempt, max_attempts, dialer_url, error,
                    )
            if last_error is not None:
                _save_challenge_debug_snapshot(page, dialer_url)
                raise last_error

            cookies = {cookie["name"]: cookie["value"] for cookie in context.cookies()}
            logger.info(
                "ReadyMode browser-login fallback succeeded for %s (cookies=%s)",
                dialer_url, sorted(cookies.keys()),
            )
            return cookies
        finally:
            browser.close()
