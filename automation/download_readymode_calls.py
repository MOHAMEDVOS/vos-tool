"""ReadyMode Call Recording Downloader with Concurrent Downloads.

This module automates the download of call recordings from ReadyMode dialers.
It is designed to be safe for cloud deployments:

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
from pathlib import Path
from uuid import uuid4
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException, NoAlertPresentException
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import subprocess
import platform

# ✅ PERFORMANCE FIX: Import WebDriver manager for memory leak prevention
try:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from lib.webdriver_manager import managed_chrome_driver, get_chrome_manager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False
    print("WARNING: webdriver_manager not available - memory leaks possible")

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
    base_dir = os.path.join(os.getcwd(), "Recordings", subfolder, username)

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


def _force_kill_chrome_processes(profile_dir: str = None, pid: int = None):
    """
    Forcefully kill Chrome processes associated with a profile or PID.
    This is a fallback when driver.quit() doesn't work.
    """
    try:
        system = platform.system()
        
        if system == "Windows":
            # Windows: Use taskkill
            if pid:
                try:
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], 
                                 capture_output=True, timeout=5, check=False)
                except:
                    pass
            
            # Kill all Chrome processes using this profile directory
            if profile_dir:
                try:
                    # Find Chrome processes using this profile
                    result = subprocess.run(
                        ["wmic", "process", "where", f"CommandLine like '%{profile_dir}%'", "get", "ProcessId"],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        pids = [line.strip() for line in result.stdout.split('\n') if line.strip().isdigit()]
                        for chrome_pid in pids:
                            try:
                                subprocess.run(["taskkill", "/F", "/PID", chrome_pid], 
                                             capture_output=True, timeout=3, check=False)
                            except:
                                pass
                except:
                    pass
        else:
            # Linux/Mac: Use kill
            if pid:
                try:
                    subprocess.run(["kill", "-9", str(pid)], 
                                 capture_output=True, timeout=5, check=False)
                except:
                    pass
            
            # Kill Chrome processes by profile (Linux/Mac)
            if profile_dir:
                try:
                    result = subprocess.run(
                        ["pgrep", "-f", profile_dir],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        pids = result.stdout.strip().split('\n')
                        for chrome_pid in pids:
                            try:
                                subprocess.run(["kill", "-9", chrome_pid], 
                                             capture_output=True, timeout=3, check=False)
                            except:
                                pass
                except:
                    pass
    except Exception as e:
        print(f"WARNING Error in force kill: {e}")


def get_driver(profile_dir: str | None = None):
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--ignore-ssl-errors")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    # Configure download preferences for headless mode
    # Note: Downloads are handled via requests library, but Chrome preferences ensure compatibility
    prefs = {
        "download.default_directory": str(Path(os.getcwd()) / "Recordings" / "temp_downloads"),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "safebrowsing.disable_download_protection": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    # Add arguments to prevent port and resource conflicts for concurrency
    chrome_options.add_argument("--remote-debugging-port=0")  # Random port
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")

    if profile_dir is None:
        session_root = os.path.join(os.getcwd(), "chrome_profile_sessions")
        os.makedirs(session_root, exist_ok=True)
        profile_dir = tempfile.mkdtemp(prefix="session_", dir=session_root)
        cleanup_profile = True
    else:
        os.makedirs(profile_dir, exist_ok=True)
        cleanup_profile = False

    chrome_options.add_argument(f"--user-data-dir={profile_dir}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.implicitly_wait(10)
    driver._profile_dir = profile_dir  # type: ignore[attr-defined]
    driver._cleanup_profile = cleanup_profile  # type: ignore[attr-defined]
    
    # Store Chrome process ID for forceful termination if needed
    try:
        if hasattr(driver, 'service') and driver.service.process:
            driver._chrome_pid = driver.service.process.pid  # type: ignore[attr-defined]
        else:
            # Fallback: try to get PID from service
            driver._chrome_pid = None  # type: ignore[attr-defined]
    except:
        driver._chrome_pid = None  # type: ignore[attr-defined]
    
    return driver

def login_to_readymode(driver, wait, dialer_url, readymode_user=None, readymode_pass=None, cancellation_callback=None):
    driver.get(dialer_url)
    
    # Wait for login elements with cancellation checks
    timeout = 30  # seconds
    start_time = time.time()
    while time.time() - start_time < timeout:
        if cancellation_callback and cancellation_callback():
            print("CANCELLED Login cancelled by user during element wait")
            raise KeyboardInterrupt("Login cancelled by user")
        try:
            login_input = driver.find_element(By.NAME, "login_account")
            break
        except:
            time.sleep(0.5)
    else:
        raise TimeoutException("Login page did not load within timeout")

    username_input = driver.find_element(By.NAME, "login_account")
    password_input = driver.find_element(By.NAME, "login_password")
    admin_checkbox = driver.find_element(By.ID, "login_as_admin")
    sign_in_btn = driver.find_element(By.CSS_SELECTOR, "input[type='submit']")

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

    username_input.clear()
    username_input.send_keys(login_username)
    password_input.clear()
    password_input.send_keys(login_password)

    if not admin_checkbox.is_selected():
        driver.execute_script("arguments[0].click();", admin_checkbox)

    driver.execute_script("arguments[0].click();", sign_in_btn)

    try:
        continue_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "input.button.primary.primary-l.sign-in[value='Continue']")))
        continue_btn.click()
    except:
        pass

    # Wait for login completion with cancellation checks
    start_time = time.time()
    while time.time() - start_time < 60:  # 60 second timeout
        if cancellation_callback and cancellation_callback():
            print("CANCELLED Login cancelled by user during completion wait")
            raise KeyboardInterrupt("Login cancelled by user")
        if "login" not in driver.current_url:
            break
        time.sleep(0.5)
    else:
        raise ReadyModeLoginError("Login failed – check ReadyMode username/password.")

# Example function to save a downloaded file for a user

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
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
        except:
            pass
        return False, None, None


def handle_duration_prompt(driver, min_duration):
    try:
        alert = driver.switch_to.alert
    except NoAlertPresentException:
        for _ in range(10):
            time.sleep(0.5)
            try:
                alert = driver.switch_to.alert
                break
            except NoAlertPresentException:
                continue
        else:
            print("INFO No duration prompt found when trying to handle it")
            return

    if isinstance(min_duration, (int, float)):
        duration_value = f"{int(min_duration)} sec"
    else:
        duration_value = "20 sec"

    print(f"CONFIG Entering duration into ReadyMode prompt: '{duration_value}'")
    try:
        alert.send_keys(duration_value)
        alert.accept()
        print("SUCCESS Duration prompt handled successfully")
    except Exception as e:
        print(f"WARNING Failed to interact with duration prompt: {e}")

def download_all_call_recordings(dialer_url, agent, update_callback=None,
                                  start_date=None, end_date=None,
                                  max_samples=50, campaign_name=None,
                                  disposition=None,
                                  min_duration=None, max_duration=None,
                                  username=None, keep_browser_open=False,
                                  readymode_user=None, readymode_pass=None,
                                  cancellation_callback=None, driver_storage=None):
    subfolder = "Campaign" if campaign_name and start_date and end_date else "Agent"
    # Determine save path for Campaign or Agent
    
    # Use provided username or fall back to default
    download_username = username if username else USERNAME
    
    # Extract dialer name from URL for unique folder naming (already extracted in app.py, but keeping for safety)
    dialer_name = extract_dialer_name_from_url(dialer_url)
    
    # Get today's date for folder naming
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    if subfolder == "Campaign" and campaign_name:
        # Get next sequential counter for this campaign/date
        counter = get_next_run_counter(campaign_name, download_username, subfolder)
        counter_str = f"{counter:03d}"  # Zero-padded 3-digit number
        campaign_folder = f"{campaign_name}-{today_date}_{counter_str} {dialer_name}"
        DOWNLOAD_DIR = os.path.join(os.getcwd(), "Recordings", subfolder, download_username, campaign_folder)
    elif subfolder == "Agent" and agent:
        # Get next sequential counter for this agent/date
        counter = get_next_run_counter(agent, download_username, subfolder)
        counter_str = f"{counter:03d}"  # Zero-padded 3-digit number
        agent_folder = f"{agent}-{today_date}_{counter_str} {dialer_name}"
        DOWNLOAD_DIR = os.path.join(os.getcwd(), "Recordings", subfolder, download_username, agent_folder)
    else:
        # Fallback for unknown cases
        counter = get_next_run_counter("Unknown", download_username, subfolder)
        counter_str = f"{counter:03d}"
        DOWNLOAD_DIR = os.path.join(os.getcwd(), "Recordings", subfolder, download_username, f"Unknown-{today_date}_{counter_str}")
    
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    print(f"DEBUG DOWNLOAD_DIR: {DOWNLOAD_DIR}")
    print(f"DEBUG Current working directory: {os.getcwd()}")

    session_root = os.path.join(os.getcwd(), "chrome_profile_sessions")
    os.makedirs(session_root, exist_ok=True)
    session_id_parts = [download_username, dialer_name]
    session_id = "_".join(filter(None, session_id_parts)) or "session"
    session_id = _sanitize_path_component(session_id)
    unique_suffix = uuid4().hex[:8]
    profile_dir = tempfile.mkdtemp(prefix=f"{session_id}_{unique_suffix}_", dir=session_root)

    driver = get_driver(profile_dir=profile_dir)
    wait = WebDriverWait(driver, 60)
    
    # Store driver reference for cancellation if storage dict provided
    if driver_storage is not None:
        driver_storage['driver'] = driver
        driver_storage['profile_dir'] = profile_dir
        driver_storage['chrome_pid'] = getattr(driver, '_chrome_pid', None)

    # Immediate cancellation check before login
    if cancellation_callback and cancellation_callback():
        print("CANCELLED Download cancelled by user before login")
        raise KeyboardInterrupt("Download cancelled by user")

    try:
        login_to_readymode(driver, wait, dialer_url, readymode_user, readymode_pass, cancellation_callback)

        # Immediate cancellation check after login
        if cancellation_callback and cancellation_callback():
            print("CANCELLED Download cancelled by user after login")
            raise KeyboardInterrupt("Download cancelled by user")

        call_logs_link = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//a[contains(@href, '+CCS Reports/call_log')]")))
        driver.execute_script("arguments[0].click();", call_logs_link)
        print("SUCCESS Clicked Call Logs")
        
        # CRITICAL: Wait for Call Logs page to fully load
        print("WAIT Waiting for Call Logs page to load...")
        time.sleep(5)  # Give page time to load completely
        
        # Immediate cancellation check after page load
        if cancellation_callback and cancellation_callback():
            print("CANCELLED Download cancelled by user after page load")
            raise KeyboardInterrupt("Download cancelled by user")
        
        # Wait for date filter to be present (confirms page loaded)
        try:
            wait.until(EC.presence_of_element_located((By.NAME, "report[time_from_d]")))
            print("SUCCESS Call Logs page loaded - filters ready")
        except:
            print("WARNING Warning: Page may still be loading, continuing anyway...")
            time.sleep(3)  # Extra wait

        # Set Date Filters
        if start_date and end_date:
            start_str = start_date.strftime("%m/%d/%Y")
            end_str = end_date.strftime("%m/%d/%Y")

            print(f"DATE Setting dates: {start_str} to {end_str}")
            
            start_input = wait.until(EC.presence_of_element_located((By.NAME, "report[time_from_d]")))
            start_input.clear()
            start_input.send_keys(start_str)
            start_input.send_keys(Keys.RETURN)
            time.sleep(1)

            end_input = wait.until(EC.presence_of_element_located((By.NAME, "report[time_to_d]")))
            end_input.clear()
            end_input.send_keys(end_str)
            end_input.send_keys(Keys.RETURN)
            
            print("WAIT Waiting for results to load after date filter...")
            time.sleep(3)
            
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='.mp3']")))
                print("SUCCESS Results loaded")
            except:
                print("WARNING No MP3 links yet (will check after agent filter)")

        # Campaign Filter
        if campaign_name:
            try:
                camp_dropdown = wait.until(EC.presence_of_element_located((By.ID, "restrict_campaign")))
                Select(camp_dropdown).select_by_visible_text(campaign_name)
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='.mp3']")))
                print(f"SUCCESS Campaign: {campaign_name}")
            except Exception as e:
                error_msg = f"[!] Campaign '{campaign_name}' not found"
                print(error_msg)
                # Propagate a clear error so the caller can stop the process gracefully
                raise RuntimeError(error_msg) from e

        # Agent Filter - Enhanced with multiple selection strategies
        if agent and agent.strip().lower() not in ["any", "all users"]:
            agent_selected = False
            try:
                print(f"\n{'='*60}")
                print(f"SEARCH AGENT SELECTION DEBUG")
                print(f"{'='*60}")
                print(f"Looking for agent: '{agent}'")
                
                # Wait for dropdown to be present and interactable
                dropdown = wait.until(EC.presence_of_element_located((By.ID, "restrict_uid")))
                time.sleep(1)  # Give dropdown time to populate
                select = Select(dropdown)
                
                # Get all available options for debugging
                available_options = [opt.text.strip() for opt in select.options]
                print(f"\n📋 DROPDOWN CONTENTS ({len(available_options)} total options):")
                print("-" * 60)
                for i, opt in enumerate(available_options[:20], 1):  # Show first 20
                    print(f"  {i:2d}. '{opt}'")
                if len(available_options) > 20:
                    print(f"  ... and {len(available_options) - 20} more")
                print("-" * 60)
                
                # Strategy 1: Try exact match (original method)
                print(f"\nSEARCH STRATEGY 1: Exact Match")
                print(f"   Searching for: '{agent.strip()}'")
                try:
                    select.select_by_visible_text(agent.strip())
                    agent_selected = True
                    print(f"   SUCCESS SUCCESS - Exact match found!")
                except Exception as e1:
                    print(f"   FAILED Failed: {type(e1).__name__}")
                    
                    # Strategy 2: Try partial match (case-insensitive)
                    print(f"\nSEARCH STRATEGY 2: Partial Match (case-insensitive)")
                    agent_lower = agent.strip().lower()
                    print(f"   Searching for substring: '{agent_lower}'")
                    matched = False
                    
                    matches_found = []
                    for option in select.options:
                        option_text = option.text.strip()
                        if agent_lower in option_text.lower():
                            matches_found.append(option_text)
                    
                    if matches_found:
                        print(f"   MATCH Found {len(matches_found)} potential match(es):")
                        for match in matches_found:
                            print(f"      - '{match}'")
                        
                        # Try to select the first match
                        try:
                            print(f"   TARGET Attempting to select: '{matches_found[0]}'")
                            select.select_by_visible_text(matches_found[0])
                            agent_selected = True
                            matched = True
                            print(f"   SUCCESS SUCCESS - Selected: '{matches_found[0]}'")
                        except Exception as e2:
                            print(f"   FAILED Failed to select: {e2}")
                    else:
                        print(f"   FAILED No partial matches found")
                    
                    if not matched:
                        # Strategy 3: Try by value instead of text
                        print(f"\nSEARCH STRATEGY 3: Select by Value Attribute")
                        print(f"   Trying value: '{agent.strip()}'")
                        try:
                            select.select_by_value(agent.strip())
                            agent_selected = True
                            print(f"   SUCCESS SUCCESS - Selected by value!")
                        except Exception as e3:
                            print(f"   FAILED Failed: {type(e3).__name__}")
                            
                            # Strategy 4: Try removing spaces and matching
                            print(f"\nSEARCH STRATEGY 4: Match without spaces")
                            agent_no_space = agent.strip().replace(" ", "").lower()
                            print(f"   Searching for: '{agent_no_space}' (no spaces)")
                            
                            for option in select.options:
                                option_text = option.text.strip()
                                option_no_space = option_text.replace(" ", "").lower()
                                if agent_no_space == option_no_space or agent_no_space in option_no_space:
                                    try:
                                        print(f"   MATCH Found match: '{option_text}'")
                                        select.select_by_visible_text(option_text)
                                        agent_selected = True
                                        print(f"   SUCCESS SUCCESS - Selected: '{option_text}'")
                                        break
                                    except Exception as e4:
                                        print(f"   WARNING Failed to select '{option_text}': {e4}")
                                        continue
                            
                            if not agent_selected:
                                print(f"\nFAILED ALL STRATEGIES FAILED!")
                                print(f"\nTIP TROUBLESHOOTING:")
                                print(f"   1. Check if agent name matches dropdown exactly")
                                print(f"   2. Try copying name directly from dropdown list above")
                                print(f"   3. Available options: {', '.join(available_options[:10])}")
                                print(f"\nWARNING Will continue downloading ALL agents (no filter applied)")
                
                # Verify selection worked
                print(f"\n{'='*60}")
                if agent_selected:
                    selected_value = select.first_selected_option.text
                    print(f"SUCCESS AGENT FILTER APPLIED")
                    print(f"   Selected: '{selected_value}'")
                    print(f"{'='*60}")
                    
                    # Wait for page to update after selection
                    print("WAIT Waiting for page to refresh with filtered results...")
                    time.sleep(3)  # Increased wait time
                    
                    # Try to wait for MP3 links, but don't fail if none exist
                    try:
                        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='.mp3']")))
                        print("SUCCESS Page updated with filtered results\n")
                    except:
                        print("WARNING No MP3 links found for this agent - they may have no recordings\n")
                else:
                    print(f"WARNING NO AGENT FILTER APPLIED")
                    print(f"   Will download from ALL agents")
                    print(f"{'='*60}\n")
                
            except Exception as e:
                print(f"\n[!] Critical error in agent selection: {type(e).__name__}: {str(e)}")
                import traceback
                traceback.print_exc()
                print(f"WARNING Continuing without agent filter...\n")

        # Disposition Filter (HYBRID: UI interaction)
        if disposition:
            try:
                print(f"SUCCESS Disposition: {disposition}")
                # 1. Open the dropdown
                dropdown_btn = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.ui-multiselect"))
                )
                driver.execute_script("arguments[0].scrollIntoView(true);", dropdown_btn)
                driver.execute_script("arguments[0].click();", dropdown_btn)
                time.sleep(0.5)

                # 2. Click 'Uncheck all'
                uncheck_all = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.ui-multiselect-none"))
                )
                driver.execute_script("arguments[0].click();", uncheck_all)
                time.sleep(0.5)

                # 3. Check only the desired dispositions
                for dispo in disposition:
                    xpath = f"//ul[contains(@class, 'ui-multiselect-checkboxes')]//label[span[text()='{dispo}']]//input"
                    checkbox = driver.find_element(By.XPATH, xpath)
                    if not checkbox.is_selected():
                        driver.execute_script("arguments[0].click();", checkbox)
                    time.sleep(0.1)

                # 4. Click outside to close the menu (optional)
                from selenium.webdriver.common.action_chains import ActionChains
                ActionChains(driver).move_by_offset(10, 10).click().perform()
                time.sleep(0.2)
            except Exception as e:
                print(f"[!] Failed to apply disposition filter: {e}")

        # Duration Filter (NEW)
        if min_duration is not None or max_duration is not None:
            try:
                print(f"CONFIG Setting duration filter: {min_duration}-{max_duration}")
                duration_dropdown = wait.until(EC.presence_of_element_located((By.ID, "duration_filter")))

                # Map min/max to dropdown value with better logic
                if min_duration is not None and max_duration is not None:
                    if min_duration == 30 and max_duration == 60:
                        Select(duration_dropdown).select_by_value("30-60")
                        print("SUCCESS Set duration filter: 30-60 seconds")
                    elif min_duration == 60 and max_duration == 600:
                        Select(duration_dropdown).select_by_value("60-600")
                        print("SUCCESS Set duration filter: 60-600 seconds")
                    else:
                        # For custom ranges, try to find closest match or use "custom"
                        print(f"WARNING Custom duration range {min_duration}-{max_duration}, trying to set in UI")
                        # Try 30-60 first as default
                        try:
                            Select(duration_dropdown).select_by_value("30-60")
                            print("SUCCESS Used 30-60 as closest match for custom range")
                        except:
                            print("WARNING Could not set duration filter in UI, will filter after download")
                elif max_duration is not None:
                    if max_duration == 30:
                        Select(duration_dropdown).select_by_value("0-30")
                        print("SUCCESS Set duration filter: 0-30 seconds")
                    else:
                        Select(duration_dropdown).select_by_value("less")
                        print(f"SUCCESS Set duration filter: Less than {max_duration} seconds")
                elif min_duration is not None:
                    Select(duration_dropdown).select_by_value("greater")
                    print(f"SUCCESS Set duration filter: Greater than {min_duration} seconds")
                    handle_duration_prompt(driver, min_duration)

                time.sleep(2)
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='.mp3']")))
                print("SUCCESS Duration filter applied successfully")
            except UnexpectedAlertPresentException as e:
                print(f"INFO Duration prompt detected via unexpected alert: {e}")
                try:
                    handle_duration_prompt(driver, min_duration)
                    time.sleep(2)
                    try:
                        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='.mp3']")))
                        print("SUCCESS Duration filter applied successfully after handling alert")
                    except Exception as wait_err:
                        print(f"WARNING Could not confirm duration filter after handling alert: {wait_err}")
                except Exception as handle_err:
                    print(f"WARNING Failed to handle duration prompt after unexpected alert: {handle_err}")
                print("INFO Continuing with potential post-download duration filtering if needed")
            except Exception as e:
                print(f"[!] Failed to set duration filter in UI: {e}")
                print("WARNING Will rely on post-download duration filtering")

        # Re-apply Campaign Filter after other filters (with stale element handling)
        if campaign_name:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Wait for the page to be in a stable state
                    time.sleep(1)
                    
                    # Find the dropdown fresh each time with explicit wait
                    camp_dropdown = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.ID, "restrict_campaign"))
                    )
                    
                    # Create a new Select instance each time
                    select = Select(camp_dropdown)
                    
                    # Try to select the campaign
                    select.select_by_visible_text(campaign_name)
                    
                    # Wait for the page to update with a more robust condition
                    WebDriverWait(driver, 10).until(
                        lambda d: d.find_element(By.CSS_SELECTOR, "a[href*='.mp3']").is_displayed()
                    )
                    
                    print(f"SUCCESS Re-applied campaign filter: {campaign_name}")
                    time.sleep(1)  # Small delay to ensure stability
                    break
                    
                except Exception as e:
                    if attempt == max_retries - 1:  # Last attempt
                        print(f"WARNING Failed to re-apply campaign filter after {max_retries} attempts: {e}")
                        print("Continuing with current filter state...")
                    else:
                        print(f"Retrying campaign filter application (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(1)  # Small delay before retry

        # Re-apply Agent Filter after other filters (to handle page refresh issues)
        if agent and agent.strip().lower() not in ["any", "all users"]:
            agent_selected = False
            try:
                print(f"\n{'='*60}")
                print(f"RE-APPLY AGENT FILTER (Post-other-filters)")
                print(f"{'='*60}")
                print(f"Re-applying agent: '{agent}'")

                # Wait for dropdown to be present and interactable
                dropdown = wait.until(EC.presence_of_element_located((By.ID, "restrict_uid")))
                time.sleep(1)  # Give dropdown time to populate
                select = Select(dropdown)

                # Get all available options for debugging
                available_options = [opt.text.strip() for opt in select.options]
                print(f"\n📋 RE-APPLY DROPDOWN CONTENTS ({len(available_options)} total options):")
                print("-" * 60)
                for i, opt in enumerate(available_options[:20], 1):  # Show first 20
                    print(f"  {i:2d}. '{opt}'")
                if len(available_options) > 20:
                    print(f"  ... and {len(available_options) - 20} more")
                print("-" * 60)

                # Strategy 1: Try exact match (original method)
                print(f"\nRE-APPLY STRATEGY 1: Exact Match")
                print(f"   Searching for: '{agent.strip()}'")
                try:
                    select.select_by_visible_text(agent.strip())
                    agent_selected = True
                    print(f"   SUCCESS SUCCESS - Exact match found!")
                except Exception as e1:
                    print(f"   FAILED Failed: {type(e1).__name__}")

                    # Strategy 2: Try partial match (case-insensitive)
                    print(f"\nRE-APPLY STRATEGY 2: Partial Match (case-insensitive)")
                    agent_lower = agent.strip().lower()
                    print(f"   Searching for substring: '{agent_lower}'")
                    matched = False

                    matches_found = []
                    for option in select.options:
                        option_text = option.text.strip()
                        if agent_lower in option_text.lower():
                            matches_found.append(option_text)

                    if matches_found:
                        print(f"   MATCH Found {len(matches_found)} potential match(es):")
                        for match in matches_found:
                            print(f"      - '{match}'")

                        # Try to select the first match
                        try:
                            print(f"   TARGET Attempting to select: '{matches_found[0]}'")
                            select.select_by_visible_text(matches_found[0])
                            agent_selected = True
                            matched = True
                            print(f"   SUCCESS SUCCESS - Selected: '{matches_found[0]}'")
                        except Exception as e2:
                            print(f"   FAILED Failed to select: {e2}")
                    else:
                        print(f"   FAILED No partial matches found")

                    if not matched:
                        # Strategy 3: Try by value instead of text
                        print(f"\nRE-APPLY STRATEGY 3: Select by Value Attribute")
                        print(f"   Trying value: '{agent.strip()}'")
                        try:
                            select.select_by_value(agent.strip())
                            agent_selected = True
                            print(f"   SUCCESS SUCCESS - Selected by value!")
                        except Exception as e3:
                            print(f"   FAILED Failed: {type(e3).__name__}")

                            # Strategy 4: Try removing spaces and matching
                            print(f"\nRE-APPLY STRATEGY 4: Match without spaces")
                            agent_no_space = agent.strip().replace(" ", "").lower()
                            print(f"   Searching for: '{agent_no_space}' (no spaces)")

                            for option in select.options:
                                option_text = option.text.strip()
                                option_no_space = option_text.replace(" ", "").lower()
                                if agent_no_space == option_no_space or agent_no_space in option_text.lower():
                                    try:
                                        print(f"   MATCH Found match: '{option_text}'")
                                        select.select_by_visible_text(option_text)
                                        agent_selected = True
                                        print(f"   SUCCESS SUCCESS - Selected: '{option_text}'")
                                        break
                                    except Exception as e4:
                                        print(f"   WARNING Failed to select '{option_text}': {e4}")
                                        continue

                            if not agent_selected:
                                print(f"\nFAILED ALL RE-APPLY STRATEGIES FAILED!")
                                print(f"\nTIP TROUBLESHOOTING:")
                                print(f"   1. Check if agent name matches dropdown exactly")
                                print(f"   2. Try copying name directly from dropdown list above")
                                print(f"   3. Available options: {', '.join(available_options[:10])}")
                                print(f"\nWARNING Re-applying agent filter failed - continuing with current filter state")

                # Verify selection worked
                print(f"\n{'='*60}")
                if agent_selected:
                    selected_value = select.first_selected_option.text
                    print(f"SUCCESS AGENT FILTER RE-APPLIED")
                    print(f"   Selected: '{selected_value}'")
                    print(f"{'='*60}")

                    # Wait for page to update after re-selection
                    print("WAIT Waiting for page to refresh with re-applied agent filter...")
                    time.sleep(3)  # Increased wait time

                    # Try to wait for MP3 links, but don't fail if none exist
                    try:
                        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='.mp3']")))
                        print("SUCCESS Page updated with re-applied agent filter\n")
                    except:
                        print("WARNING No MP3 links found for this agent after re-application - they may have no recordings\n")
                else:
                    print(f"WARNING AGENT FILTER RE-APPLICATION FAILED")
                    print(f"   Continuing with current filter state")
                    print(f"{'='*60}\n")

            except Exception as e:
                print(f"\n[!] Critical error in agent filter re-application: {type(e).__name__}: {str(e)}")
                import traceback
                traceback.print_exc()
                print(f"WARNING Continuing with current filter state after re-application failure...\n")

        # Begin downloading
        session = requests.Session()
        # Increase connection pool size to handle concurrent downloads (up to 100 concurrent)
        adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        cookies = {c['name']: c['value'] for c in driver.get_cookies()}
        headers = {"User-Agent": "Mozilla/5.0"}

        if agent and agent.strip().lower() == "all users":
            downloaded = 0
            attempted = 0
            page_number = 1
            seen_links = set()
            max_attempts = max_samples * 3  # Allow up to 3x attempts to account for filtered files
            start_time = datetime.now()
            max_duration_minutes = 60  # Maximum 60 minutes for campaign download

            # Configure pagination behavior for Campaign Audit vs other flows
            is_campaign_audit = bool(campaign_name)
            
            while downloaded < max_samples and attempted < max_attempts:
                # Check for cancellation
                if cancellation_callback and cancellation_callback():
                    print("CANCELLED Download cancelled by user")
                    raise KeyboardInterrupt("Download cancelled by user")
                
                # Check timeout
                if datetime.now() - start_time > timedelta(minutes=max_duration_minutes):
                    print(f"TIMEOUT Timeout reached after {max_duration_minutes} minutes")
                    break

                print(f"\nPAGE Page {page_number} (Downloaded: {downloaded}/{max_samples}, Attempted: {attempted})")
                
                # Check for cancellation before waiting
                if cancellation_callback and cancellation_callback():
                    print("CANCELLED Download cancelled by user")
                    raise KeyboardInterrupt("Download cancelled by user")
                
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='.mp3']")))

                blocks = driver.find_elements(By.XPATH, "//div[.//a[contains(@href, '.mp3')]]")
                calls = []
                for block in blocks:
                    try:
                        file_text = block.find_element(By.CSS_SELECTOR, "span[repvar='File']").text
                        # Keep original agent name with spaces (don't remove spaces here)
                        agent_text = block.find_element(By.CSS_SELECTOR, "span[repvar='User']").text.strip()
                        href = block.find_element(By.CSS_SELECTOR, "a[href*='.mp3']").get_attribute("href")
                        
                        # Extract time with fallback
                        try:
                            time_text = block.find_element(By.CSS_SELECTOR, "span[repvar='Time']").text
                            if not time_text or time_text.strip() == "":
                                time_text = "Unknown_Time"
                        except:
                            time_text = "Unknown_Time"
                        
                        # Extract type/disposition with fallback
                        try:
                            type_text = block.find_element(By.CSS_SELECTOR, "span[repvar='Type']").text
                            if not type_text or type_text.strip() == "":
                                type_text = "Unknown_Type"
                        except:
                            type_text = "Unknown_Type"
                        
                        if not href.startswith("http"):
                            href = dialer_url.rstrip("/") + "/" + href.lstrip("/")
                        calls.append((agent_text, file_text, href, time_text, type_text))
                    except:
                        continue

                print(f"SEARCH Found {len(calls)} calls on page")

                # Collect files to download for this page (limited by remaining slots)
                download_tasks = []
                remaining_slots = max_samples - downloaded
                if remaining_slots <= 0:
                    break

                for agent_name, file_text, href, time_text, type_text in calls:
                    if href in seen_links:
                        continue
                    seen_links.add(href)

                    # Stop collecting if we've filled all remaining slots
                    if remaining_slots <= 0:
                        break

                    phone_match = re.search(r"\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}", file_text)
                    phone_number = phone_match.group(0) if phone_match else f"unknown_{len(download_tasks)+attempted+1}"

                    # Ensure all components are valid for filename
                    if not time_text or time_text.strip() == "":
                        time_text = "Unknown_Time"
                    if not type_text or type_text.strip() == "":
                        type_text = "Unknown_Type"
                    if not phone_number or phone_number.strip() == "":
                        phone_number = f"unknown_{len(download_tasks)+attempted+1}"

                    filename = f"{agent_name.strip()} _ {time_text} _ {phone_number} _ {type_text}.mp3"

                    # Sanitize filename to remove any problematic characters
                    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)

                    filepath = os.path.join(DOWNLOAD_DIR, filename)
                    download_tasks.append((href, filepath, filename))

                    # Decrement remaining slots as we add files to batch
                    remaining_slots -= 1

                # Download files concurrently - download ALL calls found on this page at once
                if download_tasks:
                    # Use the number of calls on this page as the batch size (all calls download concurrently)
                    page_batch_size = len(download_tasks)
                    # Cap at reasonable maximum to avoid overwhelming system (100 concurrent downloads max)
                    max_workers = min(page_batch_size, 100)
                    print(f"DOWNLOAD Starting concurrent download of {page_batch_size} files from this page (all {page_batch_size} downloading at once)")
                    
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        # Submit all download tasks
                        future_to_task = {}
                        for href, filepath, filename in download_tasks:
                            future = executor.submit(
                                download_single_file, 
                                session, cookies, headers, href, filepath, 
                                min_duration, max_duration, threading.Lock()
                            )
                            future_to_task[future] = (filename, filepath)
                        
                        # Process completed downloads
                        for future in as_completed(future_to_task):
                            filename, filepath = future_to_task[future]
                            attempted += 1
                            
                            try:
                                success, actual_filepath, duration = future.result()
                                if success:
                                    downloaded += 1
                                    print(f"SUCCESS Downloaded ({downloaded}/{max_samples}): {filename}")
                                    if update_callback:
                                        update_callback(downloaded, max_samples)
                                else:
                                    if duration is not None:
                                        print(f"SKIP Skipped {filename} (duration {duration:.1f}s not in range {min_duration}-{max_duration})")
                                    else:
                                        print(f"FAILED Failed to download: {filename}")
                            except Exception as e:
                                print(f"[!] Error in concurrent download of {filename}: {e}")

                if downloaded >= max_samples:
                    print(f"SUCCESS Reached target of {max_samples} files")
                    break

                try:
                    pagination = driver.find_element(By.ID, "ccs_cl_pagination")
                    pages = pagination.find_elements(By.CSS_SELECTOR, "li.page")

                    # Default behavior for non-Campaign flows: click immediate next sibling page
                    if not is_campaign_audit:
                        current = pagination.find_element(By.CSS_SELECTOR, "li.page.selected")
                        next_page = current.find_element(By.XPATH, "following-sibling::li[@class='page']")
                        driver.execute_script("arguments[0].click();", next_page)
                        page_number += 1
                        print(f"NEXT Next page ({page_number})")
                        time.sleep(2)
                    else:
                        # Campaign Audit behavior: hop in fixed 5-page steps (1 -> 5 -> 10 -> 15 -> ...)
                        # Determine current page from the selected paginator element
                        current = pagination.find_element(By.CSS_SELECTOR, "li.page.selected")
                        try:
                            current_label = current.text.strip()
                            if current_label.isdigit():
                                page_number = int(current_label)
                        except:
                            pass

                        # Compute next target page in 5-page increments: 1 -> 5, 5 -> 10, 10 -> 15, etc.
                        if page_number < 5:
                            target_page_number = 5
                        else:
                            target_page_number = ((page_number // 5) + 1) * 5

                        # Try to find a page li whose text matches the target page number
                        target_li = None
                        for li in pages:
                            try:
                                label = li.text.strip()
                                if label.isdigit() and int(label) == target_page_number:
                                    target_li = li
                                    break
                            except:
                                continue

                        # If exact target not found, fall back to the smallest numeric page > current
                        if not target_li:
                            numeric_pages = []
                            for li in pages:
                                try:
                                    label = li.text.strip()
                                    if label.isdigit():
                                        numeric_pages.append((int(label), li))
                                except:
                                    continue

                            numeric_pages.sort(key=lambda x: x[0])
                            for num, li in numeric_pages:
                                if num > page_number:
                                    target_li = li
                                    target_page_number = num
                                    break

                        if target_li:
                            driver.execute_script("arguments[0].click();", target_li)
                            page_number = target_page_number
                            print(f"NEXT Jump to page {page_number}")
                            time.sleep(2)
                        else:
                            print("FAILED No suitable next page found for jump.")
                            break
                except:
                    print("FAILED No more pages or pagination not found.")
                    break

        else:
            # Single agent download logic
            downloaded = 0
            attempted = 0
            max_attempts = max_samples * 2  # Allow up to 2x attempts for single agent
            start_time = datetime.now()
            max_duration_minutes = 15  # Maximum 15 minutes for single agent
            seen_links = set()  # Track downloaded links to avoid duplicates

            while downloaded < max_samples and attempted < max_attempts:
                # Check for cancellation
                if cancellation_callback and cancellation_callback():
                    print("CANCELLED Download cancelled by user")
                    raise KeyboardInterrupt("Download cancelled by user")
                
                # Check timeout
                if datetime.now() - start_time > timedelta(minutes=max_duration_minutes):
                    print(f"TIMEOUT Timeout reached after {max_duration_minutes} minutes")
                    break

                print(f"\nSEARCH Looking for calls... (Downloaded: {downloaded}/{max_samples})")
                
                # Check for cancellation before waiting
                if cancellation_callback and cancellation_callback():
                    print("CANCELLED Download cancelled by user")
                    raise KeyboardInterrupt("Download cancelled by user")
                
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='.mp3']")))

                blocks = driver.find_elements(By.XPATH, "//div[.//a[contains(@href, '.mp3')]]")
                calls = []
                for block in blocks:
                    try:
                        file_text = block.find_element(By.CSS_SELECTOR, "span[repvar='File']").text
                        # Keep original agent name with spaces (don't remove spaces here)
                        agent_text = block.find_element(By.CSS_SELECTOR, "span[repvar='User']").text.strip()
                        href = block.find_element(By.CSS_SELECTOR, "a[href*='.mp3']").get_attribute("href")
                        
                        # Extract time with fallback
                        try:
                            time_text = block.find_element(By.CSS_SELECTOR, "span[repvar='Time']").text
                            if not time_text or time_text.strip() == "":
                                time_text = "Unknown_Time"
                        except:
                            time_text = "Unknown_Time"
                        
                        # Extract type/disposition with fallback
                        try:
                            type_text = block.find_element(By.CSS_SELECTOR, "span[repvar='Type']").text
                            if not type_text or type_text.strip() == "":
                                type_text = "Unknown_Type"
                        except:
                            type_text = "Unknown_Type"
                        
                        if not href.startswith("http"):
                            href = dialer_url.rstrip("/") + "/" + href.lstrip("/")
                        calls.append((agent_text, file_text, href, time_text, type_text))
                    except:
                        continue

                print(f"SEARCH Found {len(calls)} calls")

                # Collect files to download for this batch (limited by remaining slots)
                download_tasks = []
                remaining_slots = max_samples - downloaded
                if remaining_slots <= 0:
                    break

                for agent_name, file_text, href, time_text, type_text in calls:
                    # Skip duplicates (same link already seen)
                    if href in seen_links:
                        continue
                    seen_links.add(href)
                    
                    if remaining_slots <= 0:
                        break

                    attempted += 1
                    phone_match = re.search(r"\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}", file_text)
                    phone_number = phone_match.group(0) if phone_match else f"unknown_{attempted}"

                    # Ensure all components are valid for filename
                    if not time_text or time_text.strip() == "":
                        time_text = "Unknown_Time"
                    if not type_text or type_text.strip() == "":
                        type_text = "Unknown_Type"
                    if not phone_number or phone_number.strip() == "":
                        phone_number = f"unknown_{attempted}"

                    filename = f"{agent_name.strip()} _ {time_text} _ {phone_number} _ {type_text}.mp3"

                    # Sanitize filename to remove any problematic characters
                    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)

                    filepath = os.path.join(DOWNLOAD_DIR, filename)
                    download_tasks.append((href, filepath, filename))

                    # Decrement remaining slots as we add files to batch
                    remaining_slots -= 1

                # Download files concurrently - download ALL calls found on this page at once
                if download_tasks:
                    # Use the number of calls on this page as the batch size (all calls download concurrently)
                    page_batch_size = len(download_tasks)
                    # Cap at reasonable maximum to avoid overwhelming system (100 concurrent downloads max)
                    max_workers = min(page_batch_size, 100)
                    print(f"DOWNLOAD Starting concurrent download of {page_batch_size} files from this page (all {page_batch_size} downloading at once)")
                    
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        # Submit all download tasks
                        future_to_task = {}
                        for href, filepath, filename in download_tasks:
                            future = executor.submit(
                                download_single_file, 
                                session, cookies, headers, href, filepath, 
                                min_duration, max_duration, threading.Lock()
                            )
                            future_to_task[future] = (filename, filepath)
                        
                        # Process completed downloads
                        failed_downloads = []  # Track failed downloads for potential retry
                        for future in as_completed(future_to_task):
                            filename, filepath = future_to_task[future]
                            
                            try:
                                success, actual_filepath, duration = future.result()
                                if success:
                                    downloaded += 1
                                    print(f"SUCCESS Downloaded ({downloaded}/{max_samples}): {filename}")
                                    if update_callback:
                                        update_callback(downloaded, max_samples)
                                else:
                                    if duration is not None:
                                        print(f"SKIP Skipped {filename} (duration {duration:.1f}s not in range)")
                                    else:
                                        print(f"FAILED Failed to download: {filename}")
                                        # Store failed download info for potential retry
                                        for href, fp, fn in download_tasks:
                                            if fn == filename:
                                                failed_downloads.append((href, fp, fn))
                                                break
                            except Exception as e:
                                print(f"[!] Error in concurrent download of {filename}: {e}")
                                # Store failed download for potential retry
                                for href, fp, fn in download_tasks:
                                    if fn == filename:
                                        failed_downloads.append((href, fp, fn))
                                        break
                        
                        # Retry failed downloads once (in case of transient network issues)
                        if failed_downloads and len(failed_downloads) <= 5:  # Only retry if few failures
                            print(f"RETRY Retrying {len(failed_downloads)} failed downloads...")
                            for href, filepath, filename in failed_downloads:
                                try:
                                    success, actual_filepath, duration = download_single_file(
                                        session, cookies, headers, href, filepath, 
                                        min_duration, max_duration, threading.Lock()
                                    )
                                    if success:
                                        downloaded += 1
                                        print(f"SUCCESS Retry successful ({downloaded}/{max_samples}): {filename}")
                                        if update_callback:
                                            update_callback(downloaded, max_samples)
                                    else:
                                        print(f"FAILED Retry also failed: {filename}")
                                except Exception as e:
                                    print(f"[!] Error in retry download of {filename}: {e}")

                if downloaded >= max_samples:
                    break

                # Try to load more results - multiple strategies for single agent
                more_results = False
                try:
                    # Strategy 1: Look for specific pagination
                    pagination = driver.find_element(By.ID, "ccs_cl_pagination")
                    current = pagination.find_element(By.CSS_SELECTOR, "li.page.selected")
                    next_page = current.find_element(By.XPATH, "following-sibling::li[@class='page']")
                    if next_page:
                        driver.execute_script("arguments[0].click();", next_page)
                        print(f"NEXT Next page")
                        more_results = True
                        time.sleep(2)
                except:
                    try:
                        # Strategy 2: Look for "Load More" or "Show More" buttons
                        buttons = driver.find_elements(By.CSS_SELECTOR, "button, a, span")
                        for btn in buttons:
                            if ("load more" in btn.text.lower() or
                                "show more" in btn.text.lower() or
                                "next" in btn.text.lower()):
                                driver.execute_script("arguments[0].click();", btn)
                                print("LOAD Loading more results...")
                                more_results = True
                                time.sleep(3)
                                break
                    except:
                        pass

                if not more_results:
                    if downloaded < max_samples:
                        print(f"INFO No more results available. Downloaded {downloaded}/{max_samples} files.")
                        print(f"INFO This is normal if there are fewer calls than requested in the date range.")
                    else:
                        print(f"SUCCESS Reached target of {max_samples} files")
                    break

            print(f"STATS Single agent download complete: {downloaded}/{max_samples} files downloaded, {attempted} total attempts")
            print(f"INFO Proceeding to analysis phase with {downloaded} downloaded files...")

        if downloaded == 0:
            raise ReadyModeNoCallsError("No calls found for this date range. Please adjust the ReadyMode filters or date range and try again.")

    finally:
        # Clear driver storage if provided
        if driver_storage is not None:
            driver_storage.pop('driver', None)
            driver_storage.pop('profile_dir', None)
            driver_storage.pop('chrome_pid', None)
        
        # Try graceful shutdown first
        try:
            driver.quit()
            print("SUCCESS Done. Browser closed.")
        except Exception as e:
            print(f"WARNING Error closing browser gracefully: {e}")
            # Force kill Chrome processes as fallback
            try:
                chrome_pid = getattr(driver, '_chrome_pid', None)
                _force_kill_chrome_processes(profile_dir=profile_dir, pid=chrome_pid)
                print("SUCCESS Force-killed Chrome processes.")
            except Exception as kill_error:
                print(f"WARNING Failed to force-kill Chrome: {kill_error}")
        
        try:
            shutil.rmtree(profile_dir, ignore_errors=True)
            print(f"SUCCESS Cleaned up Chrome profile: {profile_dir}")
        except Exception as cleanup_error:
            print(f"WARNING Failed to clean Chrome profile {profile_dir}: {cleanup_error}")
