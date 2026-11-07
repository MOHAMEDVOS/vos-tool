"""ReadyMode Call Recording Downloader - Playwright EXACT Selenium Port.

This is a line-by-line port of the Selenium automation WITHOUT any assumptions.
Following the actual workflow discovered from analyzing working Selenium code.
"""

import os
import time
import logging
from urllib.parse import urlsplit
try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
except ImportError:
    PlaywrightTimeout = Exception

logger = logging.getLogger(__name__)

# System-level ReadyMode credentials (optional fallback)
USERNAME = os.getenv("READYMODE_USER")
PASSWORD = os.getenv("READYMODE_PASSWORD")


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class ReadyModeLoginError(Exception):
    pass


def _visible_text(page, selector: str) -> str:
    try:
        locator = page.locator(selector).first
        if locator.count() and locator.is_visible():
            return locator.inner_text(timeout=1000).strip()
    except Exception:
        return ""
    return ""


def login_to_readymode(page, dialer_url, readymode_user=None, readymode_pass=None, cancellation_callback=None):
    """Login to ReadyMode using Playwright."""
    response = page.goto(dialer_url, wait_until="domcontentloaded")

    # Wait for login form
    login_selector = "input[name='login_account']"
    try:
        page.wait_for_selector(login_selector, timeout=30000)
    except PlaywrightTimeout as error:
        final_url = urlsplit(page.url)._replace(query="", fragment="").geturl()
        try:
            title = page.title()
        except Exception:
            title = ""
        try:
            status = response.status if response else None
            content_type = response.headers.get("content-type", "") if response else ""
        except Exception:
            status = None
            content_type = ""

        selector_count = 0
        selector_visible = False
        try:
            selector = page.locator(login_selector)
            selector_count = selector.count()
            selector_visible = selector.first.is_visible() if selector_count else False
        except Exception:
            pass

        page_markers = []
        try:
            body_text = page.locator("body").inner_text(timeout=1000).lower()
            for label, phrases in {
                "cloudflare_challenge": ("just a moment", "verify you are human", "checking your browser"),
                "access_denied": ("access denied", "forbidden", "not authorized"),
                "not_found": ("404", "page not found"),
            }.items():
                if any(phrase in body_text for phrase in phrases):
                    page_markers.append(label)
        except Exception:
            pass

        details = (
            f"url={final_url}, status={status}, content_type={content_type!r}, "
            f"title={title!r}, selector_count={selector_count}, "
            f"selector_visible={selector_visible}, page_markers={page_markers}"
        )
        logger.error("ReadyMode login form was not found: %s", details)
        raise ReadyModeLoginError(f"ReadyMode login form was not found ({details})") from error

    login_username = readymode_user if readymode_user else USERNAME
    login_password = readymode_pass if readymode_pass else PASSWORD

    if not login_username or not login_password:
        raise ReadyModeLoginError(
            "ReadyMode credentials are not configured. "
            "Please set per-user ReadyMode credentials in the dashboard or "
            "set READYMODE_USER and READYMODE_PASSWORD in the environment."
        )

    # Let page JS run (sets user_tz hidden field; required for login)
    import time as _time
    _time.sleep(2)

    # Fill login form
    page.fill("input[name='login_account']", login_username)
    page.fill("input[name='login_password']", login_password)

    # Set user_tz via JS in case the page script didn't fire
    page.evaluate("() => { try { document.querySelector('input[name=user_tz]').value = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch(e){} }")

    # Check admin checkbox if not already checked
    admin_checkbox = page.locator("#login_as_admin")
    if not admin_checkbox.is_checked():
        admin_checkbox.check()

    # Click sign in
    page.click("input[type='submit']")

    # Handle "already logged in" Continue dialog
    try:
        page.wait_for_selector("input[type='submit'][value='Continue']", timeout=8000)
        page.click("input[type='submit'][value='Continue']")
        print("SUCCESS Clicked Continue (already logged in dialog)")
    except PlaywrightTimeout:
        pass

    # Wait for login to complete. ReadyMode sometimes keeps the same URL while
    # showing an error, MFA/interstitial, or an already-logged-in page, so poll
    # visible state instead of waiting only for a full navigation event.
    deadline = time.time() + 60
    last_state = ""
    while time.time() < deadline:
        current_url = page.url
        try:
            title = page.title()
        except Exception:
            title = ""

        login_visible = False
        try:
            login_visible = page.locator("input[name='login_account']").first.is_visible(timeout=1000)
        except Exception:
            pass

        error_text = (
            _visible_text(page, ".alert-danger")
            or _visible_text(page, ".error")
            or _visible_text(page, ".errors")
            or _visible_text(page, "#login_error")
        )
        if error_text:
            raise ReadyModeLoginError(f"ReadyMode login error: {error_text}")

        if "login_new" not in current_url and not login_visible:
            print(f"SUCCESS Login successful: url={current_url}, title={title}")
            return

        post_login_markers = [
            "a[href*='+CCS Reports/call_log']",
            "text=Call Logs",
            "text=CCS Reports",
            "text=Logout",
            "text=Sign Out",
        ]
        for marker in post_login_markers:
            try:
                if page.locator(marker).first.is_visible(timeout=500):
                    print(f"SUCCESS Login successful via marker '{marker}': url={current_url}, title={title}")
                    return
            except Exception:
                pass

        state = f"url={current_url}, title={title}, login_visible={login_visible}"
        if state != last_state:
            print(f"WAIT Login pending: {state}")
            last_state = state
        time.sleep(1)

    screenshot_path = Path.cwd() / "readymode-login-timeout.png"
    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"DEBUG Login timeout screenshot saved: {screenshot_path}")
    except Exception as screenshot_error:
        print(f"WARNING Could not save login timeout screenshot: {screenshot_error}")

    raise ReadyModeLoginError(
        "ReadyMode login did not complete within 60 seconds. "
        f"Current URL: {page.url}. Title: {page.title() if page else ''}"
    )
