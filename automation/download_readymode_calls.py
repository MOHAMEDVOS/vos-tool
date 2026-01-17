"""ReadyMode Call Recording Downloader - Playwright Complete Port.

This is a complete port of the Selenium automation to Playwright,
including ALL navigation steps discovered from analyzing the original code.
"""

import os
import time
import requests
import re
import logging
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

logger = logging.getLogger(__name__)

# System-level ReadyMode credentials (optional fallback)
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
    MAX_CONCURRENT_DOWNLOADS = 25


def _sanitize_path_component(value: str) -> str:
    """Sanitize strings for safe filesystem usage."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", value)


def get_next_run_counter(agent_name: str, username: str, subfolder: str) -> int:
    """Get the next sequential run counter for a given agent/date combination."""
    import glob
    
    today = datetime.now().strftime('%Y-%m-%d')
    from config import RECORDINGS_ROOT
    base_dir = str(Path(RECORDINGS_ROOT) / subfolder / username)
    pattern = os.path.join(base_dir, f"{agent_name}-{today}_*")
    matching_dirs = glob.glob(pattern)
    
    counters = []
    for dir_path in matching_dirs:
        dir_name = os.path.basename(dir_path)
        try:
            after_date = dir_name.split(f"{agent_name}-{today}_")[1]
            counter_str = after_date.split()[0]
            counter = int(counter_str)
            counters.append(counter)
        except (IndexError, ValueError):
            continue
    
    return max(counters) + 1 if counters else 1


def login_to_readymode(page, dialer_url, readymode_user=None, readymode_pass=None, cancellation_callback=None):
    """Login to ReadyMode using Playwright."""
    page.goto(dialer_url, wait_until="domcontentloaded")
    
    # Wait for login form
    page.wait_for_selector("input[name='login_account']", timeout=30000)
    
    login_username = readymode_user if readymode_user else USERNAME
    login_password = readymode_pass if readymode_pass else PASSWORD
    
    if not login_username or not login_password:
        raise ReadyModeLoginError(
            "ReadyMode credentials are not configured. "
            "Please set per-user ReadyMode credentials in the dashboard or "
            "set READYMODE_USER and READYMODE_PASSWORD in the environment."
        )
    
    print(f"DEBUG LOGIN: Using username='{login_username}' (length={len(login_username) if login_username else 0})")
    print(f"DEBUG LOGIN: Using password length={len(login_password) if login_password else 0}")
    
    # Fill login form
    page.fill("input[name='login_account']", login_username)
    page.fill("input[name='login_password']", login_password)
    
    # Check admin checkbox if not already checked
    admin_checkbox = page.locator("#login_as_admin")
    if not admin_checkbox.is_checked():
        admin_checkbox.check()
    
    # Click sign in
    page.click("input[type='submit']")
    
    # Handle potential "Continue" button
    try:
        page.wait_for_selector("input.button.primary.primary-l.sign-in[value='Continue']", timeout=5000)
        page.click("input.button.primary.primary-l.sign-in[value='Continue']")
    except PlaywrightTimeout:
        pass
    
    # Wait for login to complete
    page.wait_for_url(lambda url: "login" not in url, timeout=60000)
    print("✅ Login successful")


def format_agent_name_for_filename(agent_name):
    """Format agent name for use in filenames."""
    return agent_name.strip().replace(" ", "")


def extract_dialer_name_from_url(dialer_url: str) -> str:
    """Extract dialer name from ReadyMode URL."""
    try:
        if "://" in dialer_url:
            domain_part = dialer_url.split("://")[1]
            dialer = domain_part.split(".")[0]
            return dialer
        return "custom"
    except:
        return "unknown"


def download_single_file(session, cookies, headers, href, filepath, min_duration, max_duration, lock):
    """Download a single file with optional duration filtering."""
    try:
        response = session.get(href, cookies=cookies, headers=headers)
        if response.status_code != 200:
            return False, None, None
        
        temp_filepath = filepath + ".tmp"
        with open(temp_filepath, "wb") as f:
            f.write(response.content)
        
        # Duration filter
        if min_duration is not None or max_duration is not None:
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_file(temp_filepath)
                dur = audio.duration_seconds
                
                if (min_duration is not None and dur < min_duration) or (max_duration is not None and dur > max_duration):
                    os.remove(temp_filepath)
                    return False, None, dur
            except Exception:
                os.remove(temp_filepath)
                return False, None, None
        
        os.rename(temp_filepath, filepath)
        return True, filepath, None
    except Exception:
        try:
            temp_path = filepath + ".tmp"
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except:
            pass
        return False, None, None


def download_all_call_recordings(dialer_url, agent, update_callback=None,
                                  start_date=None, end_date=None,
                                  max_samples=50, campaign_name=None,
                                  call_type=None, min_duration=None,
                                  max_duration=None,
                                  username=None, keep_browser_open=False,
                                  readymode_user=None, readymode_pass=None,
                                  cancellation_callback=None, driver_storage=None,
                                  disposition=None):
    """Download call recordings from ReadyMode using Playwright - COMPLETE PORT."""
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
            # 1. LOGIN
            if update_callback:
                update_callback(0, 100)
            login_to_readymode(page, dialer_url, readymode_user, readymode_pass, cancellation_callback)
            
            if update_callback:
                update_callback(10, 100)
            
            # 2. NAVIGATE TO CALL LOGS (This was missing!)
            print("📊 Navigating to Call Logs...")
            call_logs_link = page.locator("a[href*='+CCS Reports/call_log']")
            call_logs_link.click()
            
            # 3. WAIT FOR CALL LOGS PAGE TO LOAD
            print("⏳ Waiting for Call Logs page to load...")
            time.sleep(5)  # Give page time to fully load
            page.wait_for_selector("input[name='report[time_from_d]']", timeout=30000)
            print("✅ Call Logs page loaded")
            
            if update_callback:
                update_callback(20, 100)
            
            # 4. SET DATE FILTERS (with correct field names and format!)
            if start_date and end_date:
                # CORRECT format: MM/DD/YYYY (not YYYY-MM-DD!)
                start_str = start_date.strftime("%m/%d/%Y")
                end_str = end_date.strftime("%m/%d/%Y")
                
                print(f"📅 Setting dates: {start_str} to {end_str}")
                
                # CORRECT field names: report[time_from_d] and report[time_to_d]
                page.fill("input[name='report[time_from_d]']", start_str)
                page.keyboard.press("Enter")
                time.sleep(1)
                
                page.fill("input[name='report[time_to_d]']", end_str)
                page.keyboard.press("Enter")
                time.sleep(1)
                
                print("✅ Date filters applied")
            
            # 5. APPLY AGENT FILTER (if not "All users")
            if agent and agent.strip().lower() not in ["any", "all users"]:
                print(f"👤 Applying agent filter: '{agent}'...")
                
                # Wait for dropdown to be ready
                page.wait_for_selector("#restrict_uid", timeout=10000)
                time.sleep(1)
                
                # Try to select agent
                try:
                    page.select_option("#restrict_uid", label=agent.strip())
                    print(f"✅ Agent filter applied: {agent}")
                except Exception as e:
                    print(f"⚠️ Could not select exact agent, will download all: {e}")
            
            # 6. APPLY CAMPAIGN FILTER (if provided)
            if campaign_name:
                print(f"🎯 Applying campaign filter: '{campaign_name}'...")
                try:
                    page.wait_for_selector("#restrict_campaign", timeout=10000)
                    page.select_option("#restrict_campaign", label=campaign_name)
                    print(f"✅ Campaign filter applied: {campaign_name}")
                except Exception as e:
                    print(f"⚠️ Could not select campaign: {e}")
            
            # 7. APPLY DISPOSITION FILTER (if provided)
            if disposition:
                print(f"📞 Applying disposition filter...")
                try:
                    page.wait_for_selector("#restrict_status", timeout=10000)
                    for disp in disposition if isinstance(disposition, list) else [disposition]:
                        page.select_option("#restrict_status", label=disp)
                    print(f"✅ Disposition filter applied")
                except Exception as e:
                    print(f"⚠️ Could not apply disposition filter: {e}")
            
            if update_callback:
                update_callback(30, 100)
            
            # 8. CLICK SUBMIT BUTTON
            print("🔘 Clicking Submit to apply filters...")
            submit_btn = page.locator("input[value='Submit']")
            submit_btn.click()
            
            # 9. WAIT FOR RESULTS TO LOAD
            print("⏳ Waiting for filtered results...")
            time.sleep(3)
            page.wait_for_selector("table", timeout=30000)
            print("✅ Results loaded")
            
            # 10. CLICK "LISTEN" LINK
            print("🎧 Clicking Listen link...")
            listen_link = page.locator("a[href*='listen.php']")
            listen_link.click()
            page.wait_for_load_state("networkidle", timeout=30000)
            print("✅ Listen page loaded")
            
            if update_callback:
                update_callback(40, 100)
            
            # 11. EXTRACT MP3 DOWNLOAD LINKS
            print("📥 Extracting MP3 links...")
            download_links = []
            all_links = page.locator("a[href*='.mp3']").all()
            
            for link in all_links[:max_samples]:
                href = link.get_attribute("href")
                if href and ".mp3" in href:
                    # Make absolute URL
                    if not href.startswith("http"):
                        base = dialer_url.rstrip("/")
                        href = f"{base}/{href.lstrip('/')}"
                    download_links.append(href)
            
            if not download_links:
                raise ReadyModeNoCallsError("No call recordings found for the specified criteria")
            
            print(f"✅ Found {len(download_links)} recordings")
            
            if update_callback:
                update_callback(50, 100)
            
            # 12. GET COOKIES FOR DOWNLOAD SESSION
            cookies_dict = {}
            for cookie in context.cookies():
                cookies_dict[cookie['name']] = cookie['value']
            
            # 13. DOWNLOAD FILES CONCURRENTLY
            print(f"⬇️ Starting concurrent download of {len(download_links)} files...")
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
                    filename = f"call_{idx:04d}.mp3"
                    filepath = os.path.join(DOWNLOAD_DIR, filename)
                    
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
                        # Pass downloaded count and total - exactly 2 params
                        update_callback(downloaded_count, total_count)
            
            if update_callback:
                update_callback(total_count, total_count)
            
            print(f"✅ DOWNLOAD_COMPLETE: {downloaded_count} files downloaded to {DOWNLOAD_DIR}")
            return DOWNLOAD_DIR
            
        except KeyboardInterrupt:
            print("Download cancelled by user")
            raise
        except Exception as e:
            print(f"Download failed: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            if not keep_browser_open:
                context.close()
                browser.close()
