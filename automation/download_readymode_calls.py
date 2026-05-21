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
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    sync_playwright = None
    PlaywrightTimeout = Exception
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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


class ReadyModeNoCallsError(Exception):
    pass


def _visible_text(page, selector: str) -> str:
    try:
        locator = page.locator(selector).first
        if locator.count() and locator.is_visible():
            return locator.inner_text(timeout=1000).strip()
    except Exception:
        return ""
    return ""


# Concurrent download configuration
# Fix 5: Reduced default from 25→15 to prevent thread exhaustion when download pool
# and analysis thread pool overlap. 15 concurrent downloads is fast on Railway Pro
# and frees ~10 thread slots for ffmpeg subprocesses.
# Override via MAX_CONCURRENT_DOWNLOADS env var to tune per deployment.
_max_downloads_env = os.getenv("MAX_CONCURRENT_DOWNLOADS", "15")
try:
    MAX_CONCURRENT_DOWNLOADS = int(_max_downloads_env)
except ValueError:
    MAX_CONCURRENT_DOWNLOADS = 15


def _sanitize_path_component(value: str) -> str:
    """Sanitize strings for safe filesystem usage."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", value)


def get_next_run_counter(agent_name: str, username: str, subfolder: str) -> int:
    """Get the next sequential run counter for a given agent/date combination."""
    import glob
    
    # CRITICAL: Format agent name the same way as folder creation  
    # (remove spaces to match format_agent_name_for_filename behavior)
    formatted_agent_name = agent_name.strip().replace(" ", "")
    
    today = datetime.now().strftime('%Y-%m-%d')
    from config import RECORDINGS_ROOT
    base_dir = str(Path(RECORDINGS_ROOT) / subfolder / username)
    pattern = os.path.join(base_dir, f"{formatted_agent_name}-{today}_*")
    matching_dirs = glob.glob(pattern)
    
    counters = []
    for dir_path in matching_dirs:
        dir_name = os.path.basename(dir_path)
        try:
            after_date = dir_name.split(f"{formatted_agent_name}-{today}_")[1]
            counter_str = after_date.split()[0]
            counter = int(counter_str)
            counters.append(counter)
        except (IndexError, ValueError):
            continue
    
    return max(counters) + 1 if counters else 1


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
            print(f"FAILED Download {href.split('/')[-1]} - Status {response.status_code}")
            # Log first 200 characters of response if it's not success
            try:
                snippet = response.text[:200].replace('\n', ' ')
                print(f"DEBUG Response Snippet: {snippet}")
            except:
                pass
            return False, None, None
        
        # Verify we got an audio file, not an HTML error page
        content_type = response.headers.get('Content-Type', '').lower()
        if 'html' in content_type:
             print(f"FAILED Download {href.split('/')[-1]} - Received HTML instead of audio (session expired?)")
             try:
                 snippet = response.text[:200].replace('\n', ' ')
                 print(f"DEBUG HTML Snippet: {snippet}")
             except:
                 pass
             return False, None, None

        temp_filepath = filepath + ".tmp"
        with open(temp_filepath, "wb") as f:
            f.write(response.content)
        
        # Duration filter after download - STRICT MODE (Old logic)
        if min_duration is not None or max_duration is not None:
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_file(temp_filepath)
                dur = audio.duration_seconds
                
                if (min_duration is not None and dur < min_duration) or (max_duration is not None and dur > max_duration):
                    print(f"SKIPPED {os.path.basename(filepath)} - Duration {dur:.1f}s outside range")
                    os.remove(temp_filepath)
                    return False, None, dur
            except Exception as e:
                print(f"FAILED Duration check failed (strict mode): {e}")
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
                return False, None, None
        
        os.replace(temp_filepath, filepath)
        return True, filepath, None
    except Exception as e:
        print(f"CRITICAL Error downloading {href}: {e}")
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
    browser_headless = _env_flag("READYMODE_HEADLESS", True)
    keep_browser_open = keep_browser_open or _env_flag("READYMODE_KEEP_BROWSER_OPEN", False)
    slow_mo_ms = int(os.getenv("READYMODE_SLOW_MO_MS", "0") or "0")

    print(
        "DEBUG BROWSER: "
        f"headless={browser_headless}, "
        f"keep_browser_open={keep_browser_open}, "
        f"slow_mo_ms={slow_mo_ms}"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=browser_headless,
            slow_mo=slow_mo_ms,
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
            login_to_readymode(page, dialer_url, readymode_user, readymode_pass, cancellation_callback)
            
            
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
            
            
            # STEP 5: CAMPAIGN FILTER (if provided) - ROBUST IMPLEMENTATION
            if campaign_name:
                print(f"\n{'='*60}")
                print(f"Applying Campaign Filter: '{campaign_name}'")
                print(f"{'='*60}")

                # 1. Wait for dropdown (Allow hidden state since it may use custom UI)
                try:
                    page.wait_for_selector("#restrict_campaign", state="attached", timeout=10000)
                except:
                    print("WARNING: #restrict_campaign dropdown not found explicitly, searching all select elements...")

                # 2. Select Campaign via Direct JS (Works with hidden/custom UI)
                print(f"Selecting campaign '{campaign_name}' via Direct JS...")

                # Wait specifically for the campaign dropdown to be populated after date filter
                print("WAIT Waiting for campaign dropdown options to load...")
                try:
                    page.wait_for_function("""
                        () => {
                            const el = document.querySelector('#restrict_campaign');
                            return el && el.options.length > 1;
                        }
                    """, timeout=25000)
                    print("SUCCESS Campaign dropdown populated")
                except:
                    print("WARNING: Campaign dropdown didn't populate in 25s, attempting anyway...")

                campaign_selected = False
                for attempt in range(3):
                    try:
                        print(f"Campaign Filter Attempt {attempt + 1}/2")

                        # 0. HANDLE BLOCKING POPUPS
                        try:
                            popups = page.locator("button.close, .modal-close, button[aria-label='Close'], .ui-dialog-titlebar-close")
                            for i in range(popups.count()):
                                if popups.nth(i).is_visible():
                                    print("INFO Closing blocking popup/modal...")
                                    popups.nth(i).click()
                                    time.sleep(0.5)

                            if page.is_visible("text=On a scale of 0-10"):
                                print("INFO Detected NPS Survey. Attempting to close...")
                                page.mouse.click(10, 10)
                                time.sleep(0.5)
                        except:
                            pass

                        # Get all available options to check if target exists
                        available_info = page.evaluate("""
                            () => {
                                const selects = Array.from(document.querySelectorAll('select'));
                                return selects.map(s => ({
                                    id: s.id,
                                    name: s.name,
                                    options: Array.from(s.options).map(o => o.text.trim())
                                }));
                            }
                        """)
                        
                        all_options = []
                        for info in available_info:
                            all_options.extend([o.lower() for o in info['options']])
                        
                        target_lower = campaign_name.strip().lower()
                        if not any(target_lower in opt for opt in all_options):
                            print(f"ERROR: Campaign '{campaign_name}' not found in dropdown options (attempt {attempt + 1}/3).")
                            if attempt == 2: # Last attempt
                                break
                            time.sleep(3)
                            continue

                        # Select Campaign via Direct JS
                        selection_result = page.evaluate("""
                            (campaignName) => {
                                const selects = Array.from(document.querySelectorAll('select'));
                                const target = campaignName.trim().toLowerCase();
                                
                                const findAndSelect = (select) => {
                                    for(let i=0; i<select.options.length; i++) {
                                        if(select.options[i].text.trim().toLowerCase().includes(target)) {
                                            select.selectedIndex = i;
                                            select.dispatchEvent(new Event('change'));
                                            // Return a unique selector for this element
                                            if (select.id) return '#' + select.id;
                                            if (select.name) return `select[name="${select.name}"]`;
                                            return null;
                                        }
                                    }
                                    return false;
                                };

                                // Priority 1: #restrict_campaign
                                const primary = document.querySelector('#restrict_campaign');
                                if (primary) {
                                    const res = findAndSelect(primary);
                                    if (res) return { success: true, selector: res };
                                }

                                // Priority 2: Any other select
                                for (const select of selects) {
                                    const res = findAndSelect(select);
                                    if (res) return { success: true, selector: res };
                                }
                                return { success: false };
                            }
                        """, campaign_name.strip())

                        found_and_selected = selection_result.get("success", False)
                        used_selector = selection_result.get("selector", "#restrict_campaign")

                        if not found_and_selected:
                            print(f"WARNING: Selection failed via JS for '{campaign_name}'.")
                            time.sleep(2)
                            continue

                        time.sleep(1)

                        # 3. Verify selection
                        try:
                            selected_value = page.eval_on_selector(used_selector, "el => el.options[Math.max(0, el.selectedIndex)].text")
                        except:
                            selected_value = "unknown"

                        if campaign_name.strip().lower() not in selected_value.lower():
                            print(f"WARNING Verification failed. Got '{selected_value}', expected '{campaign_name}'")
                            time.sleep(2)
                            continue

                        campaign_selected = True
                        print(f"SUCCESS Campaign filter selected: {selected_value}")
                        
                        # Wait for page update
                        print("WAIT Waiting for results to refresh...")
                        time.sleep(4)
                        break

                    except Exception as e:
                        print(f"WARNING Campaign filter attempt {attempt + 1} failed: {e}")
                        time.sleep(2)

                if not campaign_selected:
                    error_msg = f"No campaign found with name '{campaign_name}'"
                    print(f"\n[!] CRITICAL: {error_msg}. STOPPING PROCESS.")
                    raise ReadyModeNoCallsError(error_msg)

                print(f"SUCCESS CAMPAIGN FILTER FINALIZED: '{campaign_name}'\n")
            
            # STEP 6: AGENT FILTER (if not "All users")
            # STEP 6: AGENT FILTER (if not "All users") - ROBUST IMPLEMENTATION
            if agent and agent.strip().lower() not in ["any", "all users", "all agents"]:
                print(f"\n{'='*60}")
                print(f"Applying Agent Filter: '{agent}'")
                print(f"{'='*60}")
                
                agent_selected = False
                for attempt in range(3):
                    try:
                        print(f"Agent Filter Attempt {attempt + 1}/3")

                        # 0. HANDLE BLOCKING POPUPS (Survey/NPS)
                        # Check for common modal overlays and close them
                        try:
                            # Look for close buttons on common dialogs
                            popups = page.locator("button.close, .modal-close, button[aria-label='Close'], .ui-dialog-titlebar-close")
                            for i in range(popups.count()):
                                if popups.nth(i).is_visible():
                                    print("INFO Closing blocking popup/modal...")
                                    popups.nth(i).click()
                                    time.sleep(0.5)
                            
                            # Specific check for survey (NPS) if detected textually
                            if page.is_visible("text=On a scale of 0-10"):
                                print("INFO Detected NPS Survey. Attempting to close...")
                                # Try clicking outside or finding a specific dismissal
                                page.mouse.click(10, 10) 
                                time.sleep(0.5)
                        except:
                            pass # Don't let popup closing crash the flow
                        
                        # 1. Wait for dropdown (Allow hidden state since logs say it's hidden)
                        # The native <select> is hidden, replaced by a custom UI. 
                        # We use state="attached" so we can manipulate it via JS even if hidden.
                        page.wait_for_selector("#restrict_uid", state="attached", timeout=10000)
                        
                        # 2. Select Agent (JS Injection Method - Preferred for Hidden/Custom UI)
                        # Since the element is hidden, page.select_option might fail or require force.
                        # JS injection is cleaner here as it bypasses the UI layer entirely.
                        print(f"Selecting agent '{agent}' via Direct JS...")
                        
                        found_and_selected = page.evaluate("""
                            (agentName) => {
                                const select = document.querySelector('#restrict_uid');
                                if (!select) return false;
                                
                                let found = false;
                                for(let i=0; i<select.options.length; i++) {
                                    if(select.options[i].text.includes(agentName)) {
                                        select.selectedIndex = i;
                                        select.dispatchEvent(new Event('change')); // Important: Trigger ReadyMode update
                                        found = true;
                                        break;
                                    }
                                }
                                return found;
                            }
                        """, agent.strip())
                        
                        if not found_and_selected:
                            print(f"WARNING: Agent '{agent}' not found in dropdown list via JS.")
                            # Fallback: Try Playwright's native select force (might work if our assumption about ID is wrong)
                            try:
                                page.select_option("#restrict_uid", label=agent.strip(), force=True)
                            except:
                                pass

                        time.sleep(1)
                        
                        # 3. Verify selection
                        # We check the property value, not visibility
                        selected_value = page.eval_on_selector("#restrict_uid", "el => el.options[Math.max(0, el.selectedIndex)].text")
                        
                        # Simple substring match usually enough
                        if agent.strip() not in selected_value:
                            print(f"WARNING Selection verification failed. Got '{selected_value}', expected '{agent}'")
                            # If we failed, wait and retry loop
                            time.sleep(2)
                            continue 
                        
                        agent_selected = True
                        print(f"SUCCESS Agent filter selected: {agent}")
                        
                        # Wait for page to update
                        print("WAIT Waiting for page to refresh with filtered results...")
                        time.sleep(3) # Initial wait for trigger
                        try:
                            # Wait for network requests to finish
                            page.wait_for_load_state("networkidle", timeout=15000)
                            print("SUCCESS Page updated with filtered results")
                            break # Success!
                        except:
                             print("WARNING: Timeout waiting for load after agent filter, but filter applied.")
                             break # Assume success if filter applied but no results

                    except Exception as e:
                        print(f"WARNING Agent filter attempt {attempt + 1} failed: {e}")
                        time.sleep(2)
                
                if not agent_selected:
                    error_msg = f"No agent found with name '{agent}'"
                    print(f"[!] CRITICAL: {error_msg}. Stopping to prevent invalid data download.")
                    raise ReadyModeNoCallsError(error_msg)

                print(f"SUCCESS AGENT FILTER FINALIZED: '{agent}'\n")
            
            
            # STEP 6.1: APPLY DISPOSITION FILTER (Robust Implementation with Retries)
            if disposition:
                print(f"\n{'='*60}")
                print(f"Applying Disposition Filter: {disposition}")
                print(f"{'='*60}")
                
                filter_success = False
                for attempt in range(3):
                    try:
                        print(f"Disposition Filter Attempt {attempt + 1}/3")
                        
                        # 0. HANDLE BLOCKING POPUPS (Same as Agent Filter)
                        try:
                            # Look for close buttons on common dialogs
                            popups = page.locator("button.close, .modal-close, button[aria-label='Close'], .ui-dialog-titlebar-close")
                            for i in range(popups.count()):
                                if popups.nth(i).is_visible():
                                    print("INFO Closing blocking popup/modal...")
                                    popups.nth(i).click()
                                    time.sleep(0.5)
                            
                            # Specific check for survey (NPS)
                            if page.is_visible("text=On a scale of 0-10"):
                                print("INFO Detected NPS Survey. Attempting to close...")
                                page.mouse.click(10, 10) 
                                time.sleep(0.5)
                        except:
                            pass
                        
                        # Small wait to ensure page is ready after popup handling
                        time.sleep(0.5)
                        
                        # 1. Open the dropdown
                        # Button may be hidden, so use "attached" state and JS click
                        dropdown_selector = "button.ui-multiselect"
                        page.wait_for_selector(dropdown_selector, state="attached", timeout=10000)
                        
                        # Use JS to click the button (works even if hidden)
                        dropdown_opened = page.evaluate("""
                            () => {
                                const btn = document.querySelector('button.ui-multiselect');
                                if (!btn) return false;
                                btn.click();
                                return true;
                            }
                        """)
                        
                        if not dropdown_opened:
                            raise Exception("Could not find disposition dropdown button")
                        
                        time.sleep(1)  # Wait for animation
                        
                        # Verify dropdown opened
                        if not page.is_visible("ul.ui-multiselect-checkboxes"):
                            print("Dropdown did not open, retrying click...")
                            # Retry with JS
                            page.evaluate("document.querySelector('button.ui-multiselect')?.click()")
                            time.sleep(1)
                        
                        if not page.is_visible("ul.ui-multiselect-checkboxes"):
                             raise Exception("Dropdown menu failed to open")

                        # 2. Click 'Uncheck all'
                        uncheck_all = page.locator("a.ui-multiselect-none")
                        uncheck_all.click()
                        time.sleep(0.5)

                        # 3. Check only the desired dispositions
                        for dispo in disposition:
                            # XPath matches the Selenium implementation precisely
                            xpath = f"//ul[contains(@class, 'ui-multiselect-checkboxes')]//label[span[text()='{dispo}']]//input"
                            checkbox = page.locator(xpath)
                            if not checkbox.is_visible():
                                checkbox.scroll_into_view_if_needed()
                            
                            if not checkbox.is_checked():
                                checkbox.click()
                                print(f"Checked disposition: {dispo}")
                            time.sleep(0.1)

                        # 4. Click outside to close the menu and trigger refresh
                        page.mouse.click(10, 10)
                        
                        # 5. Wait for results to reload
                        print("WAIT Waiting for results to reload after disposition change...")
                        time.sleep(2) # Initial waiting for trigger
                        try:
                            # Wait for the network requests to finish completely to ensure results are new
                            page.wait_for_load_state("networkidle", timeout=15000)
                            print("SUCCESS Results reloaded")
                        except:
                            print("WARNING: Timeout waiting for load after filter")
                        
                        filter_success = True
                        break # Success!

                    except Exception as e:
                        print(f"WARNING Disposition filter attempt {attempt + 1} failed: {e}")
                        time.sleep(2) # Wait before retry
                        # Try to recover state (click outside)
                        try: page.mouse.click(10, 10)
                        except: pass
                
                if not filter_success:
                    error_msg = "[!] CRITICAL: Failed to apply disposition filter after 3 attempts. Stopping to prevent invalid data download."
                    print(error_msg)
                    raise Exception(error_msg)
                
                print(f"SUCCESS Disposition filter applied: {disposition}")

            # STEP 6.1.5: DURATION FILTER (Old logic - Dropdown)
            if min_duration is not None or max_duration is not None:
                print(f"\n{'='*60}")
                print(f"Applying Duration Filter (Old Logic): {min_duration}s to {max_duration if max_duration else 'Any'}s")
                print(f"{'='*60}")
                
                duration_success = False
                for attempt in range(3):  # Increased to 3 attempts
                    handle_dialog = None
                    try:
                        print(f"Duration Filter Attempt {attempt + 1}/3")
                        
                        # Set up dialog handler for the "greater" prompt
                        duration_value_str = f"{int(min_duration or 20)} sec"
                        
                        def handle_dialog_func(dialog):
                            print(f"DEBUG DIALOG DETECTED: {dialog.message}")
                            # Be permissive with message matching
                            print(f"SUCCESS Handling duration prompt with: '{duration_value_str}'")
                            dialog.accept(duration_value_str)

                        handle_dialog = handle_dialog_func
                        page.on("dialog", handle_dialog)

                        # Determine bucket value
                        value_to_select = None
                        if min_duration is not None and max_duration is not None:
                            if min_duration == 30 and max_duration == 60:
                                value_to_select = "30-60"
                            elif min_duration == 60 and max_duration == 600:
                                value_to_select = "60-600"
                            else:
                                value_to_select = "30-60"  # Default bucket
                        elif max_duration is not None:
                            if max_duration == 30:
                                value_to_select = "0-30"
                            else:
                                value_to_select = "less"
                        elif min_duration is not None:
                            value_to_select = "greater"

                        if value_to_select:
                            print(f"Selecting duration bucket '{value_to_select}' via JS...")
                            found = page.evaluate("""
                                (val) => {
                                    const select = document.querySelector('#duration_filter');
                                    if (!select) return false;
                                    select.value = val;
                                    select.dispatchEvent(new Event('change', { bubbles: true }));
                                    return true;
                                }
                            """, value_to_select)
                            
                            if not found:
                                print("WARNING: #duration_filter dropdown not found on page")
                                time.sleep(2)
                                continue
                                
                            print(f"SUCCESS Duration bucket set: {value_to_select}")
                        
                        # Wait for trigger and results
                        time.sleep(3)
                        
                        try:
                            # Wait for MP3 links or results table to refresh
                            page.wait_for_selector("a[href*='.mp3']", timeout=12000)
                            print("SUCCESS Results refreshed after duration filter")
                        except:
                            print("INFO Filter applied, results refresh not explicitly confirmed (could be 0 results)")
                            
                        duration_success = True
                        break
                    except Exception as e:
                        print(f"WARNING Duration filter attempt {attempt + 1} failed: {e}")
                        time.sleep(2)
                    finally:
                        if handle_dialog:
                            try:
                                page.remove_listener("dialog", handle_dialog)
                            except:
                                pass

            # STEP 6.2: RE-APPLY AGENT FILTER (Robust JS Implementation)
            if agent and agent.strip().lower() not in ["any", "all users"]:
                print(f"\n{'='*60}")
                print(f"RE-APPLY AGENT FILTER (Post-other-filters)")
                print(f"{'='*60}")
                
                reapply_success = False
                for attempt in range(3):
                    try:
                        print(f"Re-Apply Agent Attempt {attempt + 1}/3")
                        
                        # Handle Popups (comprehensive - match main Agent Filter)
                        try:
                            # Look for close buttons on common dialogs
                            popups = page.locator("button.close, .modal-close, button[aria-label='Close'], .ui-dialog-titlebar-close")
                            for i in range(popups.count()):
                                if popups.nth(i).is_visible():
                                    print("INFO Closing blocking popup/modal...")
                                    popups.nth(i).click()
                                    time.sleep(0.5)
                            
                            # Specific check for survey (NPS)
                            if page.is_visible("text=On a scale of 0-10"):
                                print("INFO Detected NPS Survey. Attempting to close...")
                                page.mouse.click(10, 10) 
                                time.sleep(0.5)
                        except:
                            pass  # Don't let popup closing crash the flow

                        # 1. Wait for dropdown (attached/hidden ok)
                        page.wait_for_selector("#restrict_uid", state="attached", timeout=10000)
                        
                        # 2. Select via JS Injection (ONLY method - no fallback)
                        print(f"Re-selecting agent '{agent}' via Direct JS...")
                        found_and_selected = page.evaluate("""
                            (agentName) => {
                                const select = document.querySelector('#restrict_uid');
                                if (!select) return false;
                                for(let i=0; i<select.options.length; i++) {
                                    if(select.options[i].text.includes(agentName)) {
                                        select.selectedIndex = i;
                                        select.dispatchEvent(new Event('change'));
                                        return true;
                                    }
                                }
                                return false;
                            }
                        """, agent.strip())
                        
                        if not found_and_selected:
                            print(f"WARNING: Agent '{agent}' not found for re-application.")
                            # Don't use fallback - JS injection is the only reliable method
                            time.sleep(2)
                            continue  # Retry the loop instead of using broken fallback

                        time.sleep(1)
                        
                        # 3. Verify
                        selected_value = page.eval_on_selector("#restrict_uid", "el => el.options[Math.max(0, el.selectedIndex)].text")
                        if agent.strip() not in selected_value:
                            print(f"WARNING Re-apply verification failed. Got '{selected_value}'")
                            time.sleep(2)
                            continue
                            
                        print(f"SUCCESS Agent filter re-applied: {agent}")
                        
                        # 4. Wait for refresh
                        print("WAIT Waiting for page to refresh...")
                        time.sleep(3)
                        try:
                            page.wait_for_selector("a[href*='.mp3']", timeout=10000)
                            print("SUCCESS Page updated")
                        except:
                            print("WARNING No results after re-apply (normal if 0 results)")
                        
                        reapply_success = True
                        break
                        
                    except Exception as e:
                        print(f"WARNING Re-apply attempt {attempt+1} failed: {e}")
                        time.sleep(2)
                
                if not reapply_success:
                    print(f"[!] WARNING: Failed to re-apply agent filter. Proceeding, but results might be mixed.")
                    # We don't raise Exception here to avoid crashing the whole run at the end, 
                    # as the primary filter *did* work earlier.

            
            
            # STEP 7: EXTRACT MP3 DOWNLOAD LINKS WITH PAGINATION
            # All modes paginate through pages to collect max_samples
            print(f"\\nSEARCH Extracting links with pagination (target: {max_samples} samples)...")
            
            downloaded = 0
            attempted = 0
            page_number = 1
            seen_links = set()
            max_attempts = max_samples * 3
            
            is_campaign_audit = bool(campaign_name)
            download_tasks = []  # Changed from download_links to download_tasks (stores tuples)
            
            while len(download_tasks) < max_samples and attempted < max_attempts:
                if cancellation_callback and cancellation_callback():
                    print("CANCELLED Download cancelled by user")
                    raise KeyboardInterrupt("Download cancelled by user")
                
                print(f"\\nPAGE Page {page_number} (Collected: {len(download_tasks)}/{max_samples})")
                if update_callback:
                    update_callback(len(download_tasks), max_samples)
                
                # Wait for MP3 links to be present
                try:
                    page.wait_for_selector("a[href*='.mp3']", timeout=30000)
                except:
                    print("WARNING No MP3 links found on this page")
                    break
                
                # Find all DIV blocks containing MP3 links (to extract metadata)
                blocks = page.locator("div:has(a[href*='.mp3'])").all()
                
                new_links_this_page = 0
                for block in blocks:
                    if len(download_tasks) >= max_samples:
                        break
                    
                    try:
                        # Extract metadata from spans within the block
                        file_text = block.locator("span[repvar='File']").text_content()
                        agent_text = block.locator("span[repvar='User']").text_content().strip()
                        href = block.locator("a[href*='.mp3']").get_attribute("href")
                        
                        # Extract time with fallback
                        try:
                            time_text = block.locator("span[repvar='Time']").text_content()
                            if not time_text or not time_text.strip():
                                time_text = "Unknown_Time"
                        except:
                            time_text = "Unknown_Time"
                        
                        # Extract type/disposition with fallback
                        try:
                            type_text = block.locator("span[repvar='Type']").text_content()
                            if not type_text or not type_text.strip():
                                type_text = "Unknown_Type"
                        except:
                            type_text = "Unknown_Type"
                        
                        # Make absolute URL
                        if not href.startswith("http"):
                            base = dialer_url.rstrip("/")
                            href = f"{base}/{href.lstrip('/')}"
                        
                        # Skip if we've seen this link already
                        if href in seen_links:
                            continue
                        
                        # Extract phone number from file_text
                        phone_match = re.search(r"\(\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}", file_text)
                        phone_number = phone_match.group(0) if phone_match else f"unknown_{len(download_tasks)+1}"
                        
                        # Ensure all components are valid for filename
                        if not time_text or not time_text.strip():
                            time_text = "Unknown_Time"
                        if not type_text or not type_text.strip():
                            type_text = "Unknown_Type"
                        if not phone_number or not phone_number.strip():
                            phone_number = f"unknown_{len(download_tasks)+1}"
                        
                        # Create descriptive filename (matching Selenium format)
                        filename = f"{agent_text} _ {time_text} _ {phone_number} _ {type_text}.mp3"
                        
                        # Sanitize filename to remove problematic characters
                        filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
                        
                        filepath = os.path.join(DOWNLOAD_DIR, filename)
                        
                        # Add to download tasks
                        seen_links.add(href)
                        download_tasks.append((href, filepath, filename))
                        new_links_this_page += 1
                        attempted += 1
                        
                    except Exception as e:
                        # Skip blocks that fail to extract metadata
                        continue
                
                print(f"SEARCH Found {new_links_this_page} new links on page")
                
                # Check if we have enough
                if len(download_tasks) >= max_samples:
                    print(f"SUCCESS Collected {len(download_tasks)} links (target: {max_samples})")
                    break
                
                # Try to navigate to next page
                try:
                    pagination = page.locator("#ccs_cl_pagination")
                    
                    # FIXED: Use sequential pagination for BOTH Agent and Campaign audits
                    # to ensure all results are collected (was skipping 80% of results in Campaign mode)
                    # Sequential navigation: 1, 2, 3, 4... (instead of 1, 5, 10, 15...)
                    current = pagination.locator("li.page.selected")
                    next_page = current.locator("xpath=following-sibling::li[@class='page']").first
                    next_page.click()
                    page_number += 1
                    print(f"NEXT Next page ({page_number})")
                    time.sleep(2)
                
                except Exception as e:
                    print(f"PAGINATION End of pages reached or pagination failed: {e}")
                    break
            
            if not download_tasks:
                raise ReadyModeNoCallsError("No call recordings found for the specified criteria")
            
            print(f"\\nSEARCH Collected {len(download_tasks)} total links across {page_number} pages")
            
            # STEP 8: GET COOKIES FOR DOWNLOAD SESSION
            cookies_dict = {}
            for cookie in context.cookies():
                cookies_dict[cookie['name']] = cookie['value']
            
            # STEP 9: DOWNLOAD FILES CONCURRENTLY
            print(f"\\nDOWNLOAD Starting download of {len(download_tasks)} files...")
            print(f"\nDOWNLOAD Starting download of {len(download_tasks)} files...")
            session = requests.Session()
            # Fix connection pool exhaustion by increasing pool size to match concurrency
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=MAX_CONCURRENT_DOWNLOADS + 5, 
                pool_maxsize=MAX_CONCURRENT_DOWNLOADS + 5
            )
            session.mount('https://', adapter)
            session.mount('http://', adapter)

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            lock = threading.Lock()
            downloaded_count = 0
            skipped_count = 0
            total_count = len(download_tasks)
            
            with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS) as executor:
                futures = []
                
                for href, filepath, filename in download_tasks:
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
