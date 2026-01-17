"""ReadyMode Call Recording Downloader with Concurrent Downloads (Playwright).

This module automates the download of call recordings from ReadyMode dialers.
Migrated from Selenium to Playwright for better container compatibility.

Features:
* ReadyMode credentials are never hardcoded.
* System-level credentials (READYMODE_USER / READYMODE_PASSWORD) are optional
  fallbacks and must be supplied via environment variables.
* Per-user credentials should usually be passed in from the dashboard layer.
"""

# Environment configuration (no hardcoded credentials)
import os
import time
import requests
import re
import shutil
import tempfile
import logging
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

logger = logging.getLogger(__name__)

# System-level ReadyMode credentials (optional fallback).
# For security, there are **no** hardcoded defaults:
# - If per-user credentials are not provided from the dashboard, and
# - These env vars are not set,
# a clear ReadyModeLoginError will be raised.
USERNAME = os.getenv("READYMODE_USER")
PASSWORD = os.getenv("READYMODE_PASSWORD")


class ReadyModeLoginError(Exception):
    pass


class ReadyModeNoCallsError(Exception):
    pass

# Concurrent download configuration
_max_downloads_env = os.getenv("MAX_CONCURRENT_DOWNLOADS", "25")
try:
    MAX_CONCURRENT_DOWNLOADS = int(_max_downloads_env)
except ValueError:
    # Fallback to safe default if env var is invalid
    MAX_CONCURRENT_DOWNLOADS = 25


def _sanitize_path_component(value: str) -> str:
    """Sanitize strings for safe filesystem usage."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", value)


def get_next_run_counter(agent_name: str, username: str, subfolder: str) -> int:
    """Get the next sequential run counter for a given agent/date combination.
    Scans existing folders and returns the next available number.

    Args:
        agent_name: Name of the agent or campaign
        username: Username for the recordings folder
        subfolder: "Agent" or "Campaign"

    Returns:
        Next sequential counter (starting from 1)
    """
    import glob

    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')

    # Base directory for this user and type
    from config import RECORDINGS_ROOT
    base_dir = str(Path(RECORDINGS_ROOT) / subfolder / username)

    # Pattern to match folders: {agent}-{YYYY-MM-DD}_{counter} {dialer}
    # We need to find all folders that start with "{agent}-{today}_"
    pattern = os.path.join(base_dir, f"{agent_name}-{today}_*")

    # Find all matching directories
    matching_dirs = glob.glob(pattern)

    # Extract counter numbers from folder names
    counters = []
    for dir_path in matching_dirs:
        dir_name = os.path.basename(dir_path)
        # Extract the counter part: {agent}-{date}_{counter} {dialer}
        # We want the number between the date and space
        try:
            # Split on the date part and take what's after
            after_date = dir_name.split(f"{agent_name}-{today}_")[1]
            # Take everything before the first space (the counter)
            counter_str = after_date.split()[0]
            # Convert to int
            counter = int(counter_str)
            counters.append(counter)
        except (IndexError, ValueError):
            # Skip malformed folder names
            continue

    # Return the next available counter (max + 1, or 1 if none exist)
    return max(counters) + 1 if counters else 1


def login_to_readymode(page, dialer_url, readymode_user=None, readymode_pass=None, cancellation_callback=None):
    """Login to ReadyMode using Playwright page."""
    page.goto(dialer_url, wait_until="domcontentloaded")
    
    # Wait for login elements with cancellation checks
    timeout_ms = 30000  # 30 seconds
    start_time = time.time()
    
    while time.time() - start_time < 30:
        if cancellation_callback and cancellation_callback():
            print("CANCELLED Login cancelled by user during element wait")
            raise KeyboardInterrupt("Login cancelled by user")
        try:
            page.wait_for_selector("input[name='login_account']", timeout=500)
            break
        except PlaywrightTimeout:
            time.sleep(0.5)
    else:
        raise PlaywrightTimeout("Login page did not load within timeout")

    username_input = page.locator("input[name='login_account']")
    password_input = page.locator("input[name='login_password']")
    admin_checkbox = page.locator("#login_as_admin")
    sign_in_btn = page.locator("input[type='submit']")

    # Use provided credentials or fall back to environment-based defaults
    login_username = readymode_user if readymode_user else USERNAME
    login_password = readymode_pass if readymode_pass else PASSWORD

    # If we still don't have credentials, fail fast with a clear error
    if not login_username or not login_password:
        raise ReadyModeLoginError(
            "ReadyMode credentials are not configured. "
            "Please set per-user ReadyMode credentials in the dashboard or "
            "set READYMODE_USER and READYMODE_PASSWORD in the environment."
        )

    # Debug logging
    print(f"DEBUG LOGIN: Using username='{login_username}' (length={len(login_username) if login_username else 0})")
    print(f"DEBUG LOGIN: Using password length={len(login_password) if login_password else 0}")
    print(f"DEBUG LOGIN: Password preview: '{login_password[:3] if login_password else 'None'}...'")

    username_input.fill(login_username)
    password_input.fill(login_password)

    if not admin_checkbox.is_checked():
        admin_checkbox.check()

    sign_in_btn.click()

    try:
        continue_btn = page.wait_for_selector("input.button.primary.primary-l.sign-in[value='Continue']", timeout=5000)
        if continue_btn:
            continue_btn.click()
    except PlaywrightTimeout:
        pass

    # Wait for login completion with cancellation checks
    start_time = time.time()
    while time.time() - start_time < 60:  # 60 second timeout
        if cancellation_callback and cancellation_callback():
            print("CANCELLED Login cancelled by user during completion wait")
            raise KeyboardInterrupt("Login cancelled by user")
        if "login" not in page.url:
            break
        time.sleep(0.5)
    else:
        raise ReadyModeLoginError("Login failed – check ReadyMode username/password.")


def format_agent_name_for_filename(agent_name):
    """
    Format agent name for use in filenames (remove spaces for filesystem compatibility)
    but keep the original format for display purposes.
    """
    # Remove spaces for filename to avoid filesystem issues
    return agent_name.strip().replace(" ", "")

def extract_dialer_name_from_url(dialer_url: str) -> str:
    """Extract dialer name from ReadyMode URL."""
    try:
        if "://" in dialer_url:
            # Extract subdomain from https://resva.readymode.com/
            domain_part = dialer_url.split("://")[1]
            dialer = domain_part.split(".")[0]
            return dialer
        return "custom"
    except:
        return "unknown"

def download_single_file(session, cookies, headers, href, filepath, min_duration, max_duration, lock):
    """
    Download a single file with optional duration filtering.
    
    Args:
        session: requests.Session object
        cookies: dict of cookies
        headers: dict of headers
        href: URL to download
        filepath: local path to save file
        min_duration: minimum duration filter (seconds)
        max_duration: maximum duration filter (seconds)
        lock: threading lock for thread-safe operations
        
    Returns:
        tuple: (success: bool, filepath: str or None, duration: float or None)
    """
    try:
        response = session.get(href, cookies=cookies, headers=headers)
        if response.status_code != 200:
            return False, None, None
            
        # Write file atomically
        temp_filepath = filepath + ".tmp"
        with open(temp_filepath, "wb") as f:
            f.write(response.content)
            
        # Duration filter after download
        if min_duration is not None or max_duration is not None:
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_file(temp_filepath)
                dur = audio.duration_seconds
                
                if (min_duration is not None and dur < min_duration) or (max_duration is not None and dur > max_duration):
                    os.remove(temp_filepath)
                    return False, None, dur
            except Exception as e:
                os.remove(temp_filepath)
                return False, None, None
        
        # Rename temp file to final name
        os.rename(temp_filepath, filepath)
        return True, filepath, None
        
    except Exception as e:
        # Clean up temp file if it exists
        try:
            temp_filepath_var = filepath + ".tmp"
            if os.path.exists(temp_filepath_var):
                os.remove(temp_filepath_var)
        except:
            pass
        return False, None, None

def handle_duration_prompt(page, min_duration):
    """Handle the duration filter prompt."""
    pass  # Simplified for now


def download_all_call_recordings(dialer_url, agent, update_callback=None,
                                  start_date=None, end_date=None,
                                  max_samples=50, campaign_name=None,
                                  call_type=None, min_duration=None,
                                  max_duration=None,
                                  username=None, keep_browser_open=False,
                                  readymode_user=None, readymode_pass=None,
                                  cancellation_callback=None, driver_storage=None,
                                  disposition=None):
    """
    Download call recordings from ReadyMode using Playwright.
    
    Main entry point for the automation.
    """
    import sys
   
    # Validate agent name
    if not agent or not agent.strip():
        raise ValueError("Agent name cannot be empty")
    
    # Determine download directory
    from config import RECORDINGS_ROOT
    
    # Check if RECORDINGS_ROOT is writable
    try:
        test_file = Path(RECORDINGS_ROOT) / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
    except Exception as e:
        print(f"WARNING: RECORDINGS_ROOT ({RECORDINGS_ROOT}) is not writable: {e}")
        print("Falling back to /tmp/Recordings")
        from config import RECORDINGS_ROOT as fallback_root
        RECORDINGS_ROOT = "/tmp/Recordings"
        os.makedirs(RECORDINGS_ROOT, exist_ok=True)
    
    # Determine if Agent or Campaign
    if campaign_name:
        subfolder = "Campaign"
        display_name = campaign_name
    else:
        subfolder = "Agent"
        display_name = agent
    
    # Get next run counter
    counter = get_next_run_counter(display_name, username or "default", subfolder)
    
    # Extract dialer name
    dialer_name = extract_dialer_name_from_url(dialer_url)
    
    # Create final download directory
    today = datetime.now().strftime('%Y-%m-%d')
    safe_display_name = format_agent_name_for_filename(display_name)
    folder_name = f"{safe_display_name}-{today}_{counter:03d} {dialer_name}"
    
    DOWNLOAD_DIR = str(Path(RECORDINGS_ROOT) / subfolder / (username or "default") / folder_name)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    print(f"DEBUG DOWNLOAD_DIR: {DOWNLOAD_DIR}")
    print(f"DEBUG Current working directory: {os.getcwd()}")
    
    # Initialize Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
        
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        page = context.new_page()
        
        try:
            # Login
            if update_callback:
                update_callback(0, 100)  # Starting
            login_to_readymode(page, dialer_url, readymode_user, readymode_pass, cancellation_callback)
            
            if update_callback:
                update_callback(10, 100)  # Login complete
            
            # Navigate to agent or campaign stats
            if campaign_name:
                nav_url = f"{dialer_url}/vicidial/AST_campaign_stats.php"
            else:
                nav_url = f"{dialer_url}/vicidial/AST_agent_performance_detail.php"
            
            page.goto(nav_url, wait_until="domcontentloaded")
            
            # Set date range if provided
            if start_date:
                start_input = page.locator("input[name='query_date']").first
                start_input.fill(start_date.strftime("%Y-%m-%d"))
            
            if end_date:
                end_input = page.locator("input[name='end_date']").first
                end_input.fill(end_date.strftime("%Y-%m-%d"))
            
            # Select agent/campaign from dropdown
            if campaign_name:
                select_locator = page.locator("select[name='group[]']")
                select_locator.select_option(label=campaign_name)
            else:
                select_locator = page.locator("select[name='user_group[]']")
                select_locator.select_option(label=agent)
            
            # Submit form
            submit_btn = page.locator("input[type='submit'][value='SUBMIT']")
            submit_btn.click()
            page.wait_for_load_state("networkidle", timeout=30000)
            
            if update_callback:
                update_callback(20, 100)  # Loading calls
            
            # Navigate to listen page
            listen_link = page.locator("a:has-text('Listen')").first
            listen_link.click()
            page.wait_for_load_state("networkidle", timeout=30000)
            
            # Extract download links
            download_links = []
            all_links = page.locator("a[href*='recording']").all()
            
            for link in all_links[:max_samples]:
                href = link.get_attribute("href")
                if href and "recording" in href:
                    # Make absolute URL
                    if not href.startswith("http"):
                        base = dialer_url.rstrip("/")
                        href = f"{base}/{href.lstrip('/')}"
                    download_links.append(href)
            
            if not download_links:
                raise ReadyModeNoCallsError("No call recordings found for the specified criteria")
            
            if update_callback:
                update_callback(30, 100)  # Found recordings
            
            # Get cookies for download session
            cookies_dict = {}
            for cookie in context.cookies():
                cookies_dict[cookie['name']] = cookie['value']
            
            # Download files concurrently
            session = requests.Session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            lock = threading.Lock()
            downloaded_count = 0
            skipped_count = 0
            total_count = len(download_links)
            
            with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS) as executor:
                futures = []
                
                for idx, href in enumerate(download_links, start=1):
                    # Generate filename
                    filename = f"call_{idx:04d}.mp3"
                    filepath = os.path.join(DOWNLOAD_DIR, filename)
                    
                    # Submit download task
                    future = executor.submit(
                        download_single_file,
                        session, cookies_dict, headers, href, filepath,
                        min_duration, max_duration, lock
                    )
                    futures.append(future)
                
                # Collect results
                for future in as_completed(futures):
                    if cancellation_callback and cancellation_callback():
                        print("CANCELLED Download cancelled by user")
                        raise KeyboardInterrupt("Download cancelled by user")
                    
                    success, filepath, duration = future.result()
                    if success:
                        downloaded_count += 1
                    else:
                        skipped_count += 1
                    
                    if update_callback:
                        # Pass downloaded, total - exactly 2 params!
                        update_callback(downloaded_count, total_count)
            
            if update_callback:
                update_callback(total_count, total_count)  # Complete
            
            print(f"DOWNLOAD_COMPLETE: {downloaded_count} files downloaded to {DOWNLOAD_DIR}")
            return DOWNLOAD_DIR
            
        except KeyboardInterrupt:
            print("Download cancelled by user")
            raise
        except Exception as e:
            print(f"Download failed: {e}")
            raise
        finally:
            if not keep_browser_open:
                context.close()
                browser.close()
