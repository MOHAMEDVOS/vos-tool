"""
ReadyMode API endpoints — blocking download + SSE streaming variant.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
import sys, io, threading, queue, json, time
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

# ── Per-user cancellation flags ──────────────────────────────────────────────
_cancel_flags: dict[str, threading.Event] = {}


def _get_cancel_event(username: str) -> threading.Event:
    if username not in _cancel_flags:
        _cancel_flags[username] = threading.Event()
    return _cancel_flags[username]


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
                agent=request.agent_name or "All users",
                campaign_name=request.campaign_name or None,
                start_date=start_date,
                end_date=end_date,
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
    cancel_event = _get_cancel_event(username)
    cancel_event.clear()

    log_q: queue.Queue[Optional[str]] = queue.Queue()
    result_box: dict = {}

    def worker():
        """Run download + analysis in thread, redirect stdout to queue."""
        class QueueWriter(io.TextIOBase):
            def write(self, s: str):
                for line in s.splitlines():
                    line = line.strip()
                    if line:
                        log_q.put(("log", line))
                return len(s)
            def flush(self): pass

        old_stdout = sys.stdout
        sys.stdout = QueueWriter()
        try:
            def check_cancel():
                return cancel_event.is_set()

            def on_progress(downloaded: int, total: int):
                log_q.put(("progress", json.dumps({"downloaded": downloaded, "total": total})))

            download_result = download_all_call_recordings(
                dialer_url=dialer_url,
                agent=request.agent_name or "All users",
                campaign_name=request.campaign_name or None,
                start_date=start_date,
                end_date=end_date,
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
            sys.stdout = old_stdout
            log_q.put(None)  # sentinel — None (not a tuple) signals end

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
# POST /cancel  — set cancel flag for current user
# ═════════════════════════════════════════════════════════════════════════════
@router.post("/cancel")
async def cancel_audit(current_user: dict = Depends(get_current_user)):
    """Signal the running audit for this user to stop."""
    _get_cancel_event(current_user["username"]).set()
    return {"status": "cancellation_requested"}


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
            audio_exts = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
            downloaded_count = sum(
                1 for item in download_path.iterdir()
                if item.is_file() and item.suffix.lower() in audio_exts
            )

    if download_path and download_path.exists() and downloaded_count > 0:
        try:
            from backend.services.user_service import get_user_settings
            from lib.dashboard_manager import dashboard_manager
            from processing import batch_analyze_folder_fast, batch_analyze_folder_lite

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
                        dashboard_manager.save_campaign_audit_results(
                            df, request.campaign_name.strip(), current_user["username"]
                        )
                    else:
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
