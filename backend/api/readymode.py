"""
ReadyMode API endpoints — blocking download + SSE streaming variant.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
import sys, io, threading, queue, json, time

# ── Thread-local stdout router ────────────────────────────────────────────────
# Each worker thread registers its own QueueWriter here so concurrent audits
# never overwrite each other's sys.stdout.
_thread_local = threading.local()

class _ThreadLocalStdout(io.TextIOBase):
    """Proxy that routes writes to the current thread's registered writer,
    falling back to the real stdout for threads that haven't registered one."""
    def __init__(self, real_stdout):
        self._real = real_stdout

    def write(self, s: str):
        writer = getattr(_thread_local, "queue_writer", None)
        if writer is not None:
            return writer.write(s)
        return self._real.write(s)

    def flush(self):
        writer = getattr(_thread_local, "queue_writer", None)
        if writer is not None:
            writer.flush()
        else:
            self._real.flush()

# Install the router once at import time (safe — it's a stable proxy object)
if not isinstance(sys.stdout, _ThreadLocalStdout):
    sys.stdout = _ThreadLocalStdout(sys.stdout)
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from automation.download_readymode_calls import (
    download_all_call_recordings,
    ReadyModeLoginError,
    ReadyModeNoCallsError,
    extract_dialer_name_from_url,
)

from backend.models.schemas import ReadyModeDownloadRequest, ReadyModeStatus
from backend.core.dependencies import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Active-run tracking ────────────────────────────────────────────────────
# Each /stream call gets its OWN cancel Event (never shared/reused across calls —
# a previous bug reused one Event per username, so starting a second run cleared
# the first run's pending cancellation before it was ever seen).
#
# Separately, ReadyMode only allows one active login per (account, dialer) — login
# uses logout_other_sessions=on, so two concurrent runs hitting the same dialer with
# the same ReadyMode account kick each other's session repeatedly (404s / "session
# expired" mid-run). _dialer_locks rejects a second run on a dialer that's already busy.
_active_runs: dict[str, list[dict]] = {}   # vos username -> [{"event": Event}, ...]
_dialer_locks: dict[str, str] = {}          # f"{readymode_user}::{dialer_url}" -> vos username holding it
_registry_lock = threading.Lock()


def _dialer_key(readymode_user: str, dialer_url: str) -> str:
    return f"{readymode_user}::{(dialer_url or '').rstrip('/').lower()}"


def _acquire_dialer_locks(username: str, readymode_user: str, dialer_urls: list[str]) -> None:
    """Atomically claim every dialer this run needs, or 409 if any is already busy."""
    urls = [d for d in dialer_urls if d]
    keys = [_dialer_key(readymode_user, d) for d in urls]
    with _registry_lock:
        for key, durl in zip(keys, urls):
            holder = _dialer_locks.get(key)
            if holder and holder != username:
                raise HTTPException(
                    status_code=409,
                    detail=f"{durl} is already running an audit (started by {holder}). "
                           f"Wait for it to finish or cancel it before starting another on the same dialer.",
                )
        for key in keys:
            _dialer_locks[key] = username


def _release_dialer_locks(readymode_user: str, dialer_urls: list[str]) -> None:
    with _registry_lock:
        for d in dialer_urls:
            if d:
                _dialer_locks.pop(_dialer_key(readymode_user, d), None)


# ── Duration filter resolver (shared) ────────────────────────────────────────
def _resolve_duration(df: str, audit_type: str, custom_secs: Optional[int]):
    min_dur, max_dur = None, None
    if audit_type == "heavy" and df == "all":
        min_dur = 20
    elif df == "lt30":
        max_dur = 30
    elif df == "30to60":
        min_dur, max_dur = 30, 60
    elif df == "60to600":
        min_dur, max_dur = 60, 600
    elif df == "gt_custom":
        min_dur = custom_secs
    elif df == "lt_custom":
        max_dur = custom_secs
    return min_dur, max_dur


# ── Campaign disposition scan (fire-and-forget, called after lite+campaign audit) ─────
def _run_campaign_disposition_scan(
    dialer_url: str,
    campaign_name: str,
    start_date_str: str,
    end_date_str: str,
    username: str,
    rm_user: str,
    rm_pass: str,
) -> None:
    """Pull full-day disposition CSV, compute reachability, persist. Non-fatal on any error."""
    try:
        import csv as _csv, io as _io
        from datetime import date as _date, datetime as _dt
        from automation.readymode_http import ReadyModeHTTPClient
        from lib.campaign_audit_detector import summarize_reachability
        from lib.dashboard_manager import dashboard_manager

        def _fmt(d: str) -> str:
            if not d:
                return _date.today().strftime("%m/%d/%Y")
            return _date.fromisoformat(d).strftime("%m/%d/%Y")

        scan_date = _date.fromisoformat(start_date_str) if start_date_str else _date.today()

        client = ReadyModeHTTPClient(dialer_url.rstrip("/"))
        client.login(rm_user, rm_pass)

        csv_bytes = client.export_call_log_csv(
            time_from=_fmt(start_date_str),
            time_to=_fmt(end_date_str),
            fields=[
                ("Log Type",         "Disposition"),
                ("Current campaign", "Campaign"),
            ],
        )

        text   = csv_bytes.decode("utf-8", errors="replace")
        reader = _csv.DictReader(_io.StringIO(text))
        target = campaign_name.strip().lower()
        rows   = [
            {"Disposition": row["Disposition"]}
            for row in reader
            if (row.get("Campaign") or "").strip().lower() == target
        ]

        summary   = summarize_reachability(rows, campaign_name)
        timestamp = _dt.now().strftime("%Y%m%d_%H%M%S")
        dashboard_manager.save_campaign_disposition_scan(
            campaign_name=campaign_name,
            username=username,
            scan_date=scan_date,
            timestamp=timestamp,
            summary=summary,
        )
        logger.info(
            f"Disposition scan saved: {campaign_name} "
            f"low={summary['low_total']} good={summary['good_total']} verdict={summary['verdict']}"
        )
    except Exception as exc:
        logger.error(f"Campaign disposition scan failed (non-fatal): {exc}", exc_info=True)


# ── Agent long VM/Dead-call scan (fire-and-forget, called after agent lite audit) ─────
def _run_agent_call_length_scan(
    *,
    dialer_url: str,
    agent_name: str,
    start_date_str: str,
    end_date_str: str,
    rm_user: str,
    rm_pass: str,
    download_path,
    threshold: int = 15,
    max_flagged: int = 50,
):
    """Find the agent's long Voicemails / Dead Calls (> threshold s), download ONLY those
    recordings, and return a DataFrame of flagged rows to merge into the lite-audit results.

    Workflow (CSV-find -> report-match -> download-flagged):
      CSV gives exact 'Recording Length (Seconds)' (no download link); the JSON report gives
      the RecId (download link) but only a bucketed duration. So: flag from the CSV, then look
      the same calls up in the report (match on Call Log ID, fallback phone) to download them.

    Returns None on any failure or when nothing is flagged (non-fatal — never breaks the audit).
    """
    try:
        import csv as _csv, io as _io, os as _os, re as _re, threading as _threading
        import requests as _requests
        import pandas as pd
        from datetime import date as _date
        from urllib.parse import quote as _quote
        from automation.readymode_http import (
            ReadyModeHTTPClient, resolve_agent_id, all_type_ids, BASE_TYPE,
        )
        from automation.download_readymode_calls import download_single_file
        from lib.agent_call_length_detector import flag_long_calls

        def _fmt(d: str) -> str:
            if not d:
                return _date.today().strftime("%m/%d/%Y")
            return _date.fromisoformat(d).strftime("%m/%d/%Y")

        specific_agent = bool(
            agent_name and agent_name.strip().lower() not in ("", "any", "all users", "all agents")
        )

        client = ReadyModeHTTPClient(dialer_url.rstrip("/"))
        client.login(rm_user, rm_pass)

        # 1) CSV with exact duration + the keys we need to locate the recording later.
        csv_bytes = client.export_call_log_csv(
            time_from=_fmt(start_date_str),
            time_to=_fmt(end_date_str),
            fields=[
                ("u.u_name",                   "Agent name"),
                ("Log Type",                   "Disposition"),
                ("Recording Length (Seconds)", "Duration"),
                ("CCS_Profile.phone",          "Phone"),
                ("Call Log ID",                "Call Log ID"),
            ],
        )
        text = csv_bytes.decode("utf-8", errors="replace")
        rows = list(_csv.DictReader(_io.StringIO(text)))

        flagged = flag_long_calls(
            rows, threshold=threshold,
            agent_name=agent_name if specific_agent else None,
        )
        if not flagged:
            logger.info(f"Long VM/dead scan: no calls over {threshold}s for "
                        f"{agent_name or 'all agents'}")
            return None
        if len(flagged) > max_flagged:
            logger.info(f"Long VM/dead scan: capping {len(flagged)} flagged -> {max_flagged}")
            flagged = flagged[:max_flagged]

        # 2) Report pages (this agent, VM + Dead Call only) -> {Call Log ID: row} for the RecId.
        dmap = client.init_call_log()
        vm_id   = dmap.get("voicemail")
        dead_id = dmap.get("dead call")
        types = [BASE_TYPE] + [t for t in (vm_id, dead_id) if t]
        if len(types) == 1:  # nothing resolved -> fall back to the full default set so rows return
            types = all_type_ids(dmap) if dmap else None

        uid = 0
        if specific_agent:
            probe = client.fetch_report(
                time_from=_fmt(start_date_str), time_to=_fmt(end_date_str), types=types, page=0,
            )
            ruid, _label = resolve_agent_id(probe.get("userlist", {}), agent_name)
            uid = ruid or 0

        by_id: dict[str, dict] = {}
        by_phone: dict[str, dict] = {}
        page = 0
        total_pages = None
        while page < 2000:
            data = client.fetch_report(
                time_from=_fmt(start_date_str), time_to=_fmt(end_date_str),
                restrict_uid=uid, types=types, page=page,
            )
            if total_pages is None:
                try:
                    total_pages = int(data.get("pages") or 0)
                except (TypeError, ValueError):
                    total_pages = 0
            results = data.get("results") or {}
            if not results:
                break
            for row in results.values():
                rid = str(row.get("id") or "").strip()
                if rid:
                    by_id[rid] = row
                ph = _re.search(r"\(\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}", row.get("File") or "")
                if ph:
                    by_phone.setdefault(ph.group(0), row)
            page += 1
            if total_pages and page >= total_pages:
                break

        # 3) Download ONLY the flagged recordings into the same run folder.
        download_dir = str(download_path)
        _os.makedirs(download_dir, exist_ok=True)
        dl_session = _requests.Session()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        cookies = client.cookies
        lock = _threading.Lock()

        records = []
        for f in flagged:
            row = by_id.get(f["call_log_id"]) or (by_phone.get(f["phone"]) if f["phone"] else None)
            if row is None:
                logger.debug(f"Long VM/dead scan: no recording match for {f}")
                continue
            rec = row.get("RecId")
            if not rec:
                continue
            href = f"{client.dialer}{_quote(rec, safe='/')}"
            href = href + ("&force_dl=1" if "?" in href else "?force_dl=1")

            agent_text = (row.get("User") or "").strip() or (agent_name or "Unknown_Agent")
            time_text  = (row.get("Time") or "").strip() or "Unknown_Time"
            disp_text  = f["disposition"]
            phone_text = f["phone"] or "unknown"
            # Filename format the lite read-path parses: "Agent _ Time _ Phone _ Disposition.mp3"
            filename = f"{agent_text} _ {time_text} _ {phone_text} _ {disp_text}.mp3"
            filename = _re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
            filepath = _os.path.join(download_dir, filename)

            ok, fp, _dur = download_single_file(
                dl_session, cookies, headers, href, filepath, None, None, lock,
            )
            if not ok or not fp:
                continue

            records.append({
                "Agent Name":             agent_text,
                "File Name":              _os.path.basename(fp),
                "File Path":              fp,
                "Phone Number":           phone_text,
                "Disposition":            disp_text,
                "Timestamp":              time_text,
                "Dialer Name":            extract_dialer_name_from_url(dialer_url),
                "Call Duration":          f"{f['duration']}s",
                "Releasing Detection":    "No",
                "Late Hello Detection":   "No",
                "Rebuttal Detection":     "N/A",
                "Long VM/Dead Detection": f"{disp_text} {f['duration']}s",
            })

        if not records:
            return None
        logger.info(f"Long VM/dead scan: flagged {len(records)} calls for {agent_name or 'all agents'}")
        return pd.DataFrame(records)
    except Exception as exc:
        logger.error(f"Long VM/dead scan failed (non-fatal): {exc}", exc_info=True)
        return None


# ── SSE helper ────────────────────────────────────────────────────────────────
def _sse(event: str, data: str) -> str:
    payload = json.dumps({"event": event, "data": data})
    return f"data: {payload}\n\n"


# ═════════════════════════════════════════════════════════════════════════════
# POST /download  (original blocking endpoint — kept for compatibility)
# ═════════════════════════════════════════════════════════════════════════════
@router.post("/download", response_model=ReadyModeStatus)
async def download_readymode_calls(
    request: ReadyModeDownloadRequest,
    current_user: dict = Depends(get_current_user),
):
    caller_role = current_user["role"]
    audit_type = (request.audit_type or "heavy").lower()
    is_campaign = bool(request.campaign_name and request.campaign_name.strip())
    if is_campaign and caller_role == "Auditor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Auditors can only run Agent audits")
    try:
        from config import get_user_readymode_credentials, get_user_daily_limit
        readymode_user, readymode_pass = get_user_readymode_credentials(current_user["username"])
        if not readymode_user or not readymode_pass:
            raise HTTPException(status_code=400, detail="ReadyMode credentials not configured")

        daily_limit = get_user_daily_limit(current_user["username"])
        min_duration, max_duration = _resolve_duration(
            request.duration_filter or "all", audit_type, request.custom_duration_seconds
        )
        dialer_url = request.dialer_url or "https://resva.readymode.com/"
        max_calls = request.max_calls or daily_limit

        from datetime import date as _date
        start_date = _date.fromisoformat(request.start_date) if request.start_date else _date.today()
        end_date   = _date.fromisoformat(request.end_date)   if request.end_date   else _date.today()

        import asyncio, functools
        loop = asyncio.get_event_loop()
        download_result = await loop.run_in_executor(
            None,
            functools.partial(
                download_all_call_recordings,
                dialer_url=dialer_url,
                dialer_url_2=request.dialer_url_2 or None,
                agent=request.agent_name or "All users",
                campaign_name=request.campaign_name or None,
                start_date=start_date,
                end_date=end_date,
                start_time=request.start_time or None,
                max_samples=max_calls,
                min_duration=min_duration,
                max_duration=max_duration,
                disposition=request.dispositions or None,
                username=current_user["username"],
                readymode_user=readymode_user,
                readymode_pass=readymode_pass,
            ),
        )

        downloaded_count, analyzed_count, download_path = _count_and_analyze(
            download_result, request, current_user, audit_type
        )

        return ReadyModeStatus(
            status="completed",
            downloaded_count=downloaded_count,
            analyzed_count=analyzed_count,
            message=f"Downloaded {downloaded_count} calls and analyzed {analyzed_count} rows",
        )

    except ReadyModeLoginError as e:
        raise HTTPException(status_code=401, detail=f"ReadyMode login failed: {e}")
    except ReadyModeNoCallsError as e:
        return ReadyModeStatus(status="completed", downloaded_count=0, message=str(e))
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"ReadyMode download error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# POST /stream  — SSE streaming audit with live log lines
# ═════════════════════════════════════════════════════════════════════════════
@router.post("/stream")
async def stream_readymode_audit(
    request: ReadyModeDownloadRequest,
    current_user: dict = Depends(get_current_user),
):
    """Run audit in background thread, stream every print() line as SSE."""
    caller_role = current_user["role"]
    audit_type  = (request.audit_type or "heavy").lower()
    is_campaign = bool(request.campaign_name and request.campaign_name.strip())
    if is_campaign and caller_role == "Auditor":
        raise HTTPException(status_code=403, detail="Auditors can only run Agent audits")

    from config import get_user_readymode_credentials, get_user_daily_limit
    readymode_user, readymode_pass = get_user_readymode_credentials(current_user["username"])
    if not readymode_user or not readymode_pass:
        raise HTTPException(status_code=400, detail="ReadyMode credentials not configured")

    daily_limit = get_user_daily_limit(current_user["username"])
    min_duration, max_duration = _resolve_duration(
        request.duration_filter or "all", audit_type, request.custom_duration_seconds
    )
    dialer_url = request.dialer_url or "https://resva.readymode.com/"
    max_calls  = request.max_calls or daily_limit

    from datetime import date as _date
    start_date = _date.fromisoformat(request.start_date) if request.start_date else _date.today()
    end_date   = _date.fromisoformat(request.end_date)   if request.end_date   else _date.today()

    username = current_user["username"]
    dialer_urls = [dialer_url] + ([request.dialer_url_2] if request.dialer_url_2 else [])
    _acquire_dialer_locks(username, readymode_user, dialer_urls)

    cancel_event = threading.Event()  # fresh per run — never shared with any other call
    run_entry = {"event": cancel_event}
    with _registry_lock:
        _active_runs.setdefault(username, []).append(run_entry)

    log_q: queue.Queue[Optional[str]] = queue.Queue()
    result_box: dict = {}

    def worker():
        """Run download + analysis in thread, stream stdout to this user's queue only."""
        class QueueWriter(io.TextIOBase):
            def write(self, s: str):
                for line in s.splitlines():
                    line = line.strip()
                    if line:
                        log_q.put(("log", line))
                return len(s)
            def flush(self): pass

        # Register on thread-local storage — does NOT touch global sys.stdout,
        # so concurrent users each write only to their own queue.
        _thread_local.queue_writer = QueueWriter()
        try:
            def check_cancel():
                return cancel_event.is_set()

            def on_progress(downloaded: int, total: int):
                log_q.put(("progress", json.dumps({"downloaded": downloaded, "total": total})))

            download_result = download_all_call_recordings(
                dialer_url=dialer_url,
                dialer_url_2=request.dialer_url_2 or None,
                agent=request.agent_name or "All users",
                campaign_name=request.campaign_name or None,
                start_date=start_date,
                end_date=end_date,
                start_time=request.start_time or None,
                max_samples=max_calls,
                min_duration=min_duration,
                max_duration=max_duration,
                disposition=request.dispositions or None,
                username=username,
                readymode_user=readymode_user,
                readymode_pass=readymode_pass,
                cancellation_callback=check_cancel,
                update_callback=on_progress,
            )

            if cancel_event.is_set():
                result_box["cancelled"] = True
                return

            downloaded_count, analyzed_count, _ = _count_and_analyze(
                download_result, request, current_user, audit_type
            )
            result_box["downloaded"] = downloaded_count
            result_box["analyzed"]   = analyzed_count

        except KeyboardInterrupt:
            result_box["cancelled"] = True
        except ReadyModeLoginError as e:
            result_box["error"] = f"Login failed: {e}"
        except ReadyModeNoCallsError as e:
            result_box["no_calls"] = str(e)
        except Exception as e:
            result_box["error"] = str(e)
        finally:
            _release_dialer_locks(readymode_user, dialer_urls)
            with _registry_lock:
                runs = _active_runs.get(username)
                if runs and run_entry in runs:
                    runs.remove(run_entry)
                if runs is not None and not runs:
                    _active_runs.pop(username, None)
            # Unregister this thread's writer so the thread is clean if reused
            _thread_local.queue_writer = None
            log_q.put(None)  # sentinel — signals event_stream to stop

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    async def event_stream():
        import asyncio
        try:
            yield _sse("start", "Audit started")
            while True:
                try:
                    item = log_q.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.2)
                    yield ": ping\n\n"   # keep-alive
                    continue

                if item is None:          # sentinel — worker done
                    break

                event_type, data = item
                yield _sse(event_type, data)

            # Final result event
            if result_box.get("cancelled"):
                yield _sse("cancelled", "Audit cancelled by user")
            elif "error" in result_box:
                yield _sse("error", result_box["error"])
            elif "no_calls" in result_box:
                yield _sse("done", json.dumps({"downloaded": 0, "analyzed": 0,
                                               "message": result_box["no_calls"]}))
            else:
                dl = result_box.get("downloaded", 0)
                an = result_box.get("analyzed", 0)
                yield _sse("done", json.dumps({
                    "downloaded": dl,
                    "analyzed": an,
                    "message": f"Downloaded {dl} calls, analyzed {an} rows",
                }))
        except asyncio.CancelledError:
            cancel_event.set()
            logger.info(f"SSE client disconnected (cancelled) for user {username}, cancelling worker")
            raise
        except (GeneratorExit, Exception):
            # Client disconnected — signal the worker to stop
            cancel_event.set()
            logger.info(f"SSE client disconnected for user {username}, cancelling worker")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",    # disable nginx buffering
        },
    )


# ═════════════════════════════════════════════════════════════════════════════
# POST /cancel  — stop every audit currently running for this user
# ═════════════════════════════════════════════════════════════════════════════
@router.post("/cancel")
async def cancel_audit(current_user: dict = Depends(get_current_user)):
    """Signal every currently-running audit for this user to stop."""
    username = current_user["username"]
    with _registry_lock:
        runs = list(_active_runs.get(username, []))
    for run in runs:
        run["event"].set()
    return {"status": "cancellation_requested", "runs_signalled": len(runs)}


# ═════════════════════════════════════════════════════════════════════════════
# GET /status
# ═════════════════════════════════════════════════════════════════════════════
@router.get("/status", response_model=ReadyModeStatus)
async def get_readymode_status(current_user: dict = Depends(get_current_user)):
    from config import get_user_readymode_credentials
    readymode_user, readymode_pass = get_user_readymode_credentials(current_user["username"])
    return ReadyModeStatus(
        status="available" if (readymode_user and readymode_pass) else "not_configured",
        message="ReadyMode configured" if (readymode_user and readymode_pass) else "ReadyMode credentials not set",
    )


# ── Shared helper: count downloads + run analysis ────────────────────────────
def _count_and_analyze(download_result, request, current_user, audit_type):
    downloaded_count = 0
    analyzed_count   = 0
    download_path    = None

    if isinstance(download_result, int):
        downloaded_count = download_result
    elif isinstance(download_result, (str, Path)):
        download_path = Path(download_result)
        if download_path.exists():
            # rglob, not iterdir: dual-dialer runs return a parent folder containing one
            # subfolder per dialer (see download_all_call_recordings), not flat files.
            audio_exts = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
            downloaded_count = sum(
                1 for item in download_path.rglob("*")
                if item.is_file() and item.suffix.lower() in audio_exts
            )

    if download_path and download_path.exists() and downloaded_count > 0:
        try:
            from backend.services.user_service import get_user_settings
            from lib.dashboard_manager import dashboard_manager
            from processing import batch_analyze_folder_fast, batch_analyze_folder_lite
            import pandas as pd

            user_settings = get_user_settings(current_user["username"])
            user_api_key  = user_settings.get("assemblyai_api_key")
            metadata = {
                "Processing Mode": "readymode_folder",
                "ReadyMode Folder": str(download_path),
                "API Key Source": "user" if user_api_key else "global",
                "Dialer Name": extract_dialer_name_from_url(request.dialer_url or "https://resva.readymode.com/"),
            }
            if request.campaign_name:
                metadata["Campaign Name"] = request.campaign_name

            is_campaign = bool(request.campaign_name and request.campaign_name.strip())

            if audit_type == "lite":
                df = batch_analyze_folder_lite(
                    str(download_path),
                    additional_metadata=metadata,
                    username=current_user["username"],
                    user_api_key=user_api_key,
                )
                if not df.empty:
                    df["Audit Type"] = "Lite Audit"
                if is_campaign:
                    if not df.empty:
                        dashboard_manager.save_campaign_audit_results(
                            df, request.campaign_name.strip(), current_user["username"]
                        )
                        try:
                            from config import get_user_readymode_credentials as _get_creds
                            _rm_user, _rm_pass = _get_creds(current_user["username"])
                            if _rm_user and _rm_pass:
                                _run_campaign_disposition_scan(
                                    dialer_url=request.dialer_url or "https://resva.readymode.com/",
                                    campaign_name=request.campaign_name.strip(),
                                    start_date_str=request.start_date or "",
                                    end_date_str=request.end_date or "",
                                    username=current_user["username"],
                                    rm_user=_rm_user,
                                    rm_pass=_rm_pass,
                                )
                        except Exception as _scan_err:
                            logger.error(f"Disposition scan failed (non-fatal): {_scan_err}", exc_info=True)
                else:
                    # Agent (non-campaign) lite: add long Voicemail/Dead-call detection rows.
                    # Isolated — a scan failure must never break the normal lite audit save.
                    try:
                        from config import get_user_readymode_credentials as _get_creds
                        _rm_user, _rm_pass = _get_creds(current_user["username"])
                        if _rm_user and _rm_pass:
                            extra_df = _run_agent_call_length_scan(
                                dialer_url=request.dialer_url or "https://resva.readymode.com/",
                                agent_name=request.agent_name or "",
                                start_date_str=request.start_date or "",
                                end_date_str=request.end_date or "",
                                rm_user=_rm_user,
                                rm_pass=_rm_pass,
                                download_path=download_path,
                            )
                            if extra_df is not None and not extra_df.empty:
                                extra_df["Audit Type"] = "Lite Audit"
                                df = extra_df if df.empty else pd.concat([df, extra_df], ignore_index=True)
                    except Exception as _scan_err:
                        logger.error(f"Long VM/dead scan failed (non-fatal): {_scan_err}", exc_info=True)
                    if not df.empty:
                        dashboard_manager.save_lite_audit_results(df, current_user["username"])
            else:
                df = batch_analyze_folder_fast(
                    str(download_path),
                    additional_metadata=metadata,
                    show_all_results=True,
                    use_async=True,
                    username=current_user["username"],
                    user_api_key=user_api_key,
                )
                if not df.empty:
                    df["Audit Type"] = "Heavy Audit"
                    if is_campaign:
                        dashboard_manager.save_campaign_audit_results(
                            df, request.campaign_name.strip(), current_user["username"]
                        )
                    else:
                        dashboard_manager.save_agent_audit_results(df, current_user["username"])

            analyzed_count = int(len(df)) if df is not None else 0
            if downloaded_count > 0:
                dashboard_manager.increment_daily_download_count(current_user["username"], downloaded_count)
        except Exception as process_error:
            logger.error(f"Post-download analysis failed: {process_error}", exc_info=True)
            raise

    return downloaded_count, analyzed_count, download_path
