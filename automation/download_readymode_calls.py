"""ReadyMode Call Recording Downloader - Playwright EXACT Selenium Port.

This is a line-by-line port of the Selenium automation WITHOUT any assumptions.
Following the actual workflow discovered from analyzing working Selenium code.
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
        response = session.get(href, cookies=cookies, headers=headers, timeout=30)
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
    """
    Download call recordings from ReadyMode using Playwright.
    
    EXACT PORT OF SELENIUM WORKFLOW - NO ASSUMPTIONS.
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
            # STEP 1: LOGIN
            if update_callback:
                update_callback(0, 100)
            login_to_readymode(page, dialer_url, readymode_user, readymode_pass, cancellation_callback)
            
            if update_callback:
                update_callback(10, 100)
            
            # STEP 2: CLICK CALL LOGS LINK
            print("SUCCESS Clicked Call Logs")
            call_logs_link = page.locator("a[href*='+CCS Reports/call_log']")
            call_logs_link.click()
            
            # STEP 3: WAIT FOR CALL LOGS PAGE TO FULLY LOAD
            print("WAIT Waiting for Call Logs page to load...")
            time.sleep(5)  # Give page time to load completely
            
            # Wait for date filter to confirm page loaded
            try:
                page.wait_for_selector("input[name='report[time_from_d]']", state="attached", timeout=30000)
                print("SUCCESS Call Logs page loaded - filters ready")
            except:
                print("WARNING Warning: Page may still be loading, continuing anyway...")
                time.sleep(3)
            
            # STEP 4: SET DATE FILTERS
            if start_date and end_date:
                start_str = start_date.strftime("%m/%d/%Y")
                end_str = end_date.strftime("%m/%d/%Y")
                
                print(f"DATE Setting dates: {start_str} to {end_str}")
                
                # Use JavaScript to set values on hidden Flatpickr inputs
                page.evaluate(f"""
                    var startInput = document.querySelector("input[name='report[time_from_d]']");
                    if (startInput) {{
                        startInput.value = '{start_str}';
                        startInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                """)
                time.sleep(1)
                
                page.evaluate(f"""
                    var endInput = document.querySelector("input[name='report[time_to_d]']");
                    if (endInput) {{
                        endInput.value = '{end_str}';
                        endInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                """)
                
                print("WAIT Waiting for results to load after date filter...")
                time.sleep(3)
                
                # Try to wait for MP3 links
                try:
                    page.wait_for_selector("a[href*='.mp3']", timeout=10000)
                    print("SUCCESS Results loaded")
                except:
                    print("WARNING No MP3 links yet (will check after agent filter)")
            
            if update_callback:
                update_callback(30, 100)
            
            # STEP 5: CAMPAIGN FILTER (if provided)
            if campaign_name:
                try:
                    page.wait_for_selector("#restrict_campaign", timeout=10000)
                    page.select_option("#restrict_campaign", label=campaign_name)
                    page.wait_for_selector("a[href*='.mp3']", timeout=10000)
                    print(f"SUCCESS Campaign: {campaign_name}")
                except Exception as e:
                    error_msg = f"[!] Campaign '{campaign_name}' not found"
                    print(error_msg)
                    raise RuntimeError(error_msg) from e
            
            # STEP 6: AGENT FILTER (if not "All users")
            if agent and agent.strip().lower() not in ["any", "all users"]:
                agent_selected = False
                try:
                    print(f"\\n{'='*60}")
                    print(f"SEARCH AGENT SELECTION DEBUG")
                    print(f"{'='*60}")
                    print(f"Looking for agent: '{agent}'")
                    
                    # Wait for dropdown
                    page.wait_for_selector("#restrict_uid", timeout=10000)
                    time.sleep(1)
                    
                    # Try to select agent
                    try:
                        page.select_option("#restrict_uid", label=agent.strip())
                        agent_selected = True
                        print(f"SUCCESS Agent filter applied: {agent}")
                    except:
                        print(f"WARNING Could not select agent '{agent}', continuing with all agents")
                    
                    # Wait for page to update
                    if agent_selected:
                        print("WAIT Waiting for page to refresh with filtered results...")
                        time.sleep(3)
                        try:
                            page.wait_for_selector("a[href*='.mp3']", timeout=10000)
                            print("SUCCESS Page updated with filtered results")
                        except:
                            print("WARNING No MP3 links found for this agent")
                        
                        print(f"\\n{'='*60}")
                        print(f"SUCCESS AGENT FILTER APPLIED")
                        print(f"   Selected: '{agent}'")
                        print(f"{'='*60}")
                
                except Exception as e:
                    print(f"WARNING Agent filter failed: {e}")
                    import traceback
                    traceback.print_exc()
                    print(f"WARNING Continuing with current filter state...\\n")
            
            if update_callback:
                update_callback(50, 100)
            
            # STEP 7: EXTRACT MP3 DOWNLOAD LINKS WITH PAGINATION
            # All modes paginate through pages to collect max_samples
            print(f"\\nSEARCH Extracting links with pagination (target: {max_samples} samples)...")
            
            downloaded = 0
            attempted = 0
            page_number = 1
            seen_links = set()
            max_attempts = max_samples * 3
            
            is_campaign_audit = bool(campaign_name)
            download_links = []
            
            while len(download_links) < max_samples and attempted < max_attempts:
                if cancellation_callback and cancellation_callback():
                    print("CANCELLED Download cancelled by user")
                    raise KeyboardInterrupt("Download cancelled by user")
                
                print(f"\\nPAGE Page {page_number} (Collected: {len(download_links)}/{max_samples})")
                
                # Wait for MP3 links to be present
                try:
                    page.wait_for_selector("a[href*='.mp3']", timeout=30000)
                except:
                    print("WARNING No MP3 links found on this page")
                    break
                
                # Get all MP3 links on current page
                all_links = page.locator("a[href*='.mp3']").all()
                
                new_links_this_page = 0
                for link in all_links:
                    if len(download_links) >= max_samples:
                        break
                    
                    href = link.get_attribute("href")
                    if href and ".mp3" in href:
                        # Make absolute URL
                        if not href.startswith("http"):
                            base = dialer_url.rstrip("/")
                            href = f"{base}/{href.lstrip('/')}"
                        
                        if href not in seen_links:
                            seen_links.add(href)
                            download_links.append(href)
                            new_links_this_page += 1
                            attempted += 1
                
                print(f"SEARCH Found {new_links_this_page} new links on page")
                
                # Check if we have enough
                if len(download_links) >= max_samples:
                    print(f"SUCCESS Collected {len(download_links)} links (target: {max_samples})")
                    break
                
                # Try to navigate to next page
                try:
                    pagination = page.locator("#ccs_cl_pagination")
                    
                    if not is_campaign_audit:
                        # Default behavior for BOTH specific agents and "All users":
                        # Click immediate next sibling page (sequential: 1→2→3→4...)
                        current = pagination.locator("li.page.selected")
                        next_page = current.locator("xpath=following-sibling::li[@class='page']").first
                        next_page.click()
                        page_number += 1
                        print(f"NEXT Next page ({page_number})")
                        time.sleep(2)
                    else:
                        # Campaign Audit: hop in 5-page steps (1 → 5 → 10 → 15 → ...)
                        current = pagination.locator("li.page.selected")
                        current_label = current.text_content().strip()
                        
                        try:
                            if current_label.isdigit():
                                page_number = int(current_label)
                        except:
                            pass
                        
                        # Compute next target page in 5-page increments
                        if page_number < 5:
                            target_page_number = 5
                        else:
                            target_page_number = ((page_number // 5) + 1) * 5
                        
                        # Try to find and click target page
                        try:
                            target_page = pagination.locator(f"li.page a:has-text('{target_page_number}')").first
                            target_page.click()
                            page_number = target_page_number
                            print(f"NEXT Jumped to page {target_page_number}")
                            time.sleep(2)
                        except:
                            print(f"WARNING No page {target_page_number} found, stopping pagination")
                            break
                
                except Exception as e:
                    print(f"PAGINATION End of pages reached or pagination failed: {e}")
                    break
            
            if not download_links:
                raise ReadyModeNoCallsError("No call recordings found for the specified criteria")
            
            print(f"\\nSEARCH Collected {len(download_links)} total links across {page_number} pages")
            
            if update_callback:
                update_callback(60, 100)
            
            # STEP 8: GET COOKIES FOR DOWNLOAD SESSION
            cookies_dict = {}
            for cookie in context.cookies():
                cookies_dict[cookie['name']] = cookie['value']
            
            # STEP 9: DOWNLOAD FILES CONCURRENTLY
            print(f"\\nDOWNLOAD Starting download of {len(download_links)} files...")
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
            
            print(f"DOWNLOAD_COMPLETE: {downloaded_count} files downloaded to {DOWNLOAD_DIR}")
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
