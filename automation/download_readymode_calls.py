"""ReadyMode Call Recording Downloader — pure HTTP (no Playwright/Chromium).

Replaces the former Playwright browser automation with direct HTTP requests against
ReadyMode's JSON report endpoint. See ``automation/readymode_http.py`` for the client
and ``scratch/readymode-recon/HTTP_SPEC.md`` for the reverse-engineered API contract.

The public contract is unchanged so the FastAPI layer (``backend/api/readymode.py``) and
the SSE stream keep working without edits:
  * ``download_all_call_recordings(...)`` — same signature
  * same output folders + filename format
  * same progress ``print()`` lines (consumed by the SSE stream)
  * same ``ReadyModeLoginError`` / ``ReadyModeNoCallsError`` exceptions (re-exported here)
"""

import os
import re
import logging
import threading
from pathlib import Path
from urllib.parse import quote
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

try:  # support both "automation.download_readymode_calls" and bare "download_readymode_calls" imports
    from automation.readymode_http import (
        ReadyModeHTTPClient,
        ReadyModeLoginError,
        ReadyModeNoCallsError,
        resolve_campaign_id,
        resolve_agent_id,
        disposition_type_ids,
    )
except ImportError:  # pragma: no cover
    from readymode_http import (
        ReadyModeHTTPClient,
        ReadyModeLoginError,
        ReadyModeNoCallsError,
        resolve_campaign_id,
        resolve_agent_id,
        disposition_type_ids,
    )

logger = logging.getLogger(__name__)

# System-level ReadyMode credentials (optional fallback)
USERNAME = os.getenv("READYMODE_USER")
PASSWORD = os.getenv("READYMODE_PASSWORD")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Concurrent download configuration. Default 30 — benchmarked sweet spot for the pure-HTTP
# downloader: 1000 files took ~125s @15, ~95s @30, ~91s @50 (server/bandwidth caps throughput
# at ~10-11 files/sec, so 30->50 gains almost nothing). Override via MAX_CONCURRENT_DOWNLOADS.
_max_downloads_env = os.getenv("MAX_CONCURRENT_DOWNLOADS", "30")
try:
    MAX_CONCURRENT_DOWNLOADS = int(_max_downloads_env)
except ValueError:
    MAX_CONCURRENT_DOWNLOADS = 30


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
    """Format agent name for use in filenames (remove spaces for filesystem compatibility)."""
    return agent_name.strip().replace(" ", "")


def extract_dialer_name_from_url(dialer_url: str) -> str:
    """Extract dialer name from ReadyMode URL (e.g. https://resva.readymode.com/ -> resva)."""
    try:
        if "://" in dialer_url:
            domain_part = dialer_url.split("://")[1]
            dialer = domain_part.split(".")[0]
            return dialer
        return "custom"
    except Exception:
        return "unknown"


def download_single_file(session, cookies, headers, href, filepath, min_duration, max_duration, lock):
    """Download a single file with optional duration filtering (unchanged from prior behavior)."""
    try:
        response = session.get(href, cookies=cookies, headers=headers, timeout=30)
        if response.status_code != 200:
            print(f"FAILED Download {href.split('/')[-1]} - Status {response.status_code}")
            try:
                snippet = response.text[:200].replace('\n', ' ')
                print(f"DEBUG Response Snippet: {snippet}")
            except Exception:
                pass
            return False, None, None

        # Verify we got an audio file, not an HTML error page
        content_type = response.headers.get('Content-Type', '').lower()
        if 'html' in content_type:
            print(f"FAILED Download {href.split('/')[-1]} - Received HTML instead of audio (session expired?)")
            try:
                snippet = response.text[:200].replace('\n', ' ')
                print(f"DEBUG HTML Snippet: {snippet}")
            except Exception:
                pass
            return False, None, None

        temp_filepath = filepath + ".tmp"
        with open(temp_filepath, "wb") as f:
            f.write(response.content)

        # Duration filter after download - STRICT MODE (authoritative; same as before)
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
        except Exception:
            pass
        return False, None, None


def _collect_tasks_for_dialer(
    dialer_url, login_username, login_password,
    start_str, end_str, start_dateonly,
    agent, campaign_name, disposition,
    max_samples, download_dir,
    cancellation_callback=None,
    task_offset=0,
):
    """Login to one dialer and paginate up to max_samples tasks.

    Returns (tasks, cookies_dict) where tasks = [(href, filepath, filename), ...].
    task_offset is used to keep 'unknown_N' phone placeholders unique across dialers.
    Raises ReadyModeLoginError / ReadyModeNoCallsError on hard failures.
    """
    client = ReadyModeHTTPClient(dialer_url)
    client.login(login_username, login_password)
    print(f"SUCCESS Login successful (HTTP) on {client.dialer}")
    client.init_call_log()

    probe = client.fetch_report(time_from=start_str, time_to=end_str,
                                time_from_dateonly=start_dateonly)
    restrict_campaign = 0
    restrict_uid = 0

    if campaign_name:
        cid, cname = resolve_campaign_id(probe.get("campaignlist", {}), campaign_name)
        if not cid:
            raise ReadyModeNoCallsError(f"No campaign found with name '{campaign_name}' on {client.dialer}")
        restrict_campaign = cid
        print(f"SUCCESS Campaign filter resolved: {cname} (id={cid}) on {client.dialer}")

    if agent and agent.strip().lower() not in ["any", "all users", "all agents"]:
        uid, label = resolve_agent_id(probe.get("userlist", {}), agent)
        if not uid:
            raise ReadyModeNoCallsError(f"No agent found with name '{agent}' on {client.dialer}")
        restrict_uid = uid
        print(f"SUCCESS Agent filter resolved: {label} (uid={uid}) on {client.dialer}")

    types = disposition_type_ids(disposition) if disposition else None
    if disposition:
        print(f"INFO Disposition filter on {client.dialer}: {disposition} -> types {types}")

    tasks = []
    seen_links = set()
    page = 0
    total_pages = None
    collected = task_offset  # used only for unique placeholder filenames

    while len(tasks) < max_samples and page < 2000:
        if cancellation_callback and cancellation_callback():
            raise KeyboardInterrupt("Download cancelled by user")

        data = client.fetch_report(
            time_from=start_str, time_to=end_str, time_from_dateonly=start_dateonly,
            restrict_uid=restrict_uid, restrict_campaign=restrict_campaign,
            types=types, page=page,
        )

        if total_pages is None:
            try:
                total_pages = int(data.get("pages") or 0)
            except (TypeError, ValueError):
                total_pages = 0
            print(f"PAGE {client.dialer} total pages: {total_pages}")

        results = data.get("results") or {}
        if not results:
            break

        new_links = 0
        for row in results.values():
            if len(tasks) >= max_samples:
                break
            rec = row.get("RecId")
            if not rec:
                continue

            href = f"{client.dialer}{quote(rec, safe='/')}"
            href = href + ("&force_dl=1" if "?" in href else "?force_dl=1")
            if href in seen_links:
                continue

            agent_text = (row.get("User") or "").strip() or "Unknown_Agent"
            time_text  = (row.get("Time") or "").strip() or "Unknown_Time"
            type_text  = (row.get("Type") or "").strip() or "Unknown_Type"
            file_text  = row.get("File") or ""
            phone_match = re.search(r"\(\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}", file_text)
            phone_number = phone_match.group(0) if phone_match else f"unknown_{collected + 1}"

            filename = f"{agent_text} _ {time_text} _ {phone_number} _ {type_text}.mp3"
            filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
            filepath = os.path.join(download_dir, filename)

            seen_links.add(href)
            tasks.append((href, filepath, filename))
            new_links += 1
            collected += 1

        print(f"SEARCH {client.dialer} page {page + 1}: +{new_links} (collected {len(tasks)}/{max_samples})")
        page += 1
        if total_pages and page >= total_pages:
            break

    return tasks, client.cookies


def download_all_call_recordings(dialer_url, agent, update_callback=None,
                                 start_date=None, end_date=None,
                                 start_time=None,
                                 max_samples=50, campaign_name=None,
                                 call_type=None, min_duration=None,
                                 max_duration=None,
                                 username=None, keep_browser_open=False,
                                 readymode_user=None, readymode_pass=None,
                                 cancellation_callback=None, driver_storage=None,
                                 disposition=None, dialer_url_2=None):
    """Download call recordings from ReadyMode via pure HTTP (no browser).

    Signature, output folders, filename format, progress prints, duration filtering and
    cancellation semantics are preserved from the previous Playwright implementation.
    ``keep_browser_open`` / ``driver_storage`` / ``call_type`` are accepted for backward
    compatibility but are no longer used.

    ``dialer_url_2`` is optional. When provided, both dialers are queried in parallel and
    each independently collects up to ``max_samples`` recordings (total = 2 × max_samples).
    If dialer 2 fails (login error, no calls), a warning is printed and the run continues
    with dialer 1 only.
    """
    # ── Validate ──────────────────────────────────────────────────────────────
    if not agent or not agent.strip():
        raise ValueError("Agent name cannot be empty")

    # ── Determine download directory (unchanged) ──────────────────────────────
    from config import RECORDINGS_ROOT
    try:
        test_file = Path(RECORDINGS_ROOT) / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
    except Exception as e:
        print(f"WARNING: RECORDINGS_ROOT ({RECORDINGS_ROOT}) is not writable: {e}")
        RECORDINGS_ROOT = "/tmp/Recordings"
        os.makedirs(RECORDINGS_ROOT, exist_ok=True)

    if campaign_name:
        subfolder = "Campaign"
        display_name = campaign_name
    else:
        subfolder = "Agent"
        display_name = agent

    counter = get_next_run_counter(display_name, username or "default", subfolder)
    dialer_name = extract_dialer_name_from_url(dialer_url)
    if dialer_url_2:
        dialer_name = f"{dialer_name}+{extract_dialer_name_from_url(dialer_url_2)}"
    today = datetime.now().strftime('%Y-%m-%d')
    safe_display_name = format_agent_name_for_filename(display_name)
    folder_name = f"{safe_display_name}-{today}_{counter:03d} {dialer_name}"

    DOWNLOAD_DIR = str(Path(RECORDINGS_ROOT) / subfolder / (username or "default") / folder_name)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    print(f"DEBUG DOWNLOAD_DIR: {DOWNLOAD_DIR}")

    try:
        login_username = readymode_user or USERNAME
        login_password = readymode_pass or PASSWORD
        print(f"DEBUG LOGIN: Using username='{login_username}' "
              f"(length={len(login_username) if login_username else 0})")

        # ── Date / time range ─────────────────────────────────────────────────
        start_str = start_date.strftime("%m/%d/%Y")
        end_str = end_date.strftime("%m/%d/%Y")
        start_dateonly = "1"
        if start_time:
            start_str = f"{start_str} {start_time}".strip()
            start_dateonly = "0"
        print(f"DATE Range {start_str} -> {end_str}")

        # ── Collect tasks (one or two dialers in parallel) ────────────────────
        print(f"SEARCH Collecting up to {max_samples} recordings"
              f"{' per dialer (2 dialers)' if dialer_url_2 else ''}...")

        shared_args = dict(
            login_username=login_username, login_password=login_password,
            start_str=start_str, end_str=end_str, start_dateonly=start_dateonly,
            agent=agent, campaign_name=campaign_name, disposition=disposition,
            max_samples=max_samples, download_dir=DOWNLOAD_DIR,
            cancellation_callback=cancellation_callback,
        )

        # tagged tasks = [(href, filepath, filename, cookies_dict), ...]
        tagged_tasks = []

        if dialer_url_2:
            from concurrent.futures import ThreadPoolExecutor as _TPE, as_completed as _ac
            futures_map = {}
            with _TPE(max_workers=2) as col_exec:
                f1 = col_exec.submit(_collect_tasks_for_dialer, dialer_url,  **shared_args, task_offset=0)
                f2 = col_exec.submit(_collect_tasks_for_dialer, dialer_url_2, **shared_args, task_offset=0)
                futures_map[f1] = dialer_url
                futures_map[f2] = dialer_url_2

            for fut in (f1, f2):
                durl = futures_map[fut]
                try:
                    tasks, cookies = fut.result()
                    for href, filepath, filename in tasks:
                        tagged_tasks.append((href, filepath, filename, cookies))
                    print(f"INFO {durl}: {len(tasks)} tasks collected")
                except (ReadyModeLoginError, ReadyModeNoCallsError) as e:
                    if durl == dialer_url:
                        raise  # primary dialer failure is fatal
                    print(f"WARNING Dialer 2 ({durl}) skipped: {e}")
                except KeyboardInterrupt:
                    raise
        else:
            tasks, cookies = _collect_tasks_for_dialer(dialer_url, **shared_args, task_offset=0)
            for href, filepath, filename in tasks:
                tagged_tasks.append((href, filepath, filename, cookies))

        if not tagged_tasks:
            raise ReadyModeNoCallsError("No call recordings found for the specified criteria")

        print(f"SEARCH Collected {len(tagged_tasks)} total links")
        if update_callback:
            update_callback(len(tagged_tasks), len(tagged_tasks))

        # ── Download files concurrently ────────────────────────────────────────
        print(f"DOWNLOAD Starting download of {len(tagged_tasks)} files...")
        dl_session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=MAX_CONCURRENT_DOWNLOADS + 5,
            pool_maxsize=MAX_CONCURRENT_DOWNLOADS + 5,
        )
        dl_session.mount('https://', adapter)
        dl_session.mount('http://', adapter)
        headers = {"User-Agent": UA}

        lock = threading.Lock()
        downloaded_count = 0
        skipped_count = 0
        total_count = len(tagged_tasks)

        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS) as executor:
            futures = [
                executor.submit(
                    download_single_file,
                    dl_session, task_cookies, headers, href, filepath,
                    min_duration, max_duration, lock,
                )
                for href, filepath, filename, task_cookies in tagged_tasks
            ]

            for future in as_completed(futures):
                if cancellation_callback and cancellation_callback():
                    print("CANCELLED Download cancelled by user")
                    raise KeyboardInterrupt("Download cancelled by user")

                success, fp, duration = future.result()
                if success:
                    downloaded_count += 1
                else:
                    skipped_count += 1

                if update_callback:
                    update_callback(downloaded_count, total_count)

        if update_callback:
            update_callback(total_count, total_count)

        print(f"DOWNLOAD_COMPLETE: {downloaded_count} files downloaded to {DOWNLOAD_DIR}")
        return DOWNLOAD_DIR

    except KeyboardInterrupt:
        print("Download cancelled by user")
        raise
    except (ReadyModeLoginError, ReadyModeNoCallsError):
        raise
    except Exception as e:
        print(f"Download failed: {e}")
        import traceback
        traceback.print_exc()
        raise
