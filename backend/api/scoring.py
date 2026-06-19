"""Scoring API — one-click multi-dialer call sampler.

Three endpoints:
  * POST /gather   (SSE)  — pull phone+agent CSV from all dialers for a date + load that date's
                            flagged calls, cache both maps in Redis under a run_id.
  * POST /generate        — given run_id + pasted agent names, return the per-agent scoring rows
                            (flagged numbers if the agent has flags, else 5 random).
  * POST /export-sheet    — push generated rows into a shared Google Sheet.

Reuses the proven ReadyMode HTTP client, the existing flagged-calls service, and the Google
Workspace helpers. See the plan and docs/READYMODE_HTTP_SPEC.md §7.
"""

import os
import sys
import json
import uuid
import queue
import asyncio
import logging
import threading
from pathlib import Path
from datetime import date as _date
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from automation.readymode_http import ReadyModeHTTPClient, ReadyModeLoginError
from lib.scoring_sampler import (
    parse_phone_agent_csv,
    build_agent_index,
    build_flagged_index,
    score_agents,
)
from backend.core.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

_REDIS_TTL_SECONDS = 3600  # gathered maps live ~1h

# Scoring only samples calls with these dispositions (per-dialer ids are resolved live from each
# dialer's own disposition map by export_call_log_csv).
SCORING_DISPOSITIONS = ["Wrong Number", "Decision Maker - NYI"]

# Company "Auditors-Scoring MOP" sheet + which auditor tab each VOS login owns. VOS only knows the
# login (no full name), so name-matching is unreliable — this explicit map is the source of truth.
COMPANY_SCORING_SHEET_ID = "1WQHD0ACs5K6iHXWxPnG8izcs-45KlFFyU3vufO7AxQE"
LOGIN_TO_TAB = {
    "mohamedabdo@res-va.com": "Abdo",
    "ayasamir@res-va.com": "Aya",
    "zeinab@res-va.com": "Zizi",
}


# ── request models ───────────────────────────────────────────────────────────
class GatherRequest(BaseModel):
    date: Optional[str] = None  # ISO YYYY-MM-DD; defaults to today


class GenerateRequest(BaseModel):
    run_id: str
    agent_names: List[str]


class AuditRequest(BaseModel):
    run_id: str
    agent_names: List[str]


class ExportSheetRequest(BaseModel):
    rows: List[dict]
    title: Optional[str] = None


# ── SSE + Redis helpers ──────────────────────────────────────────────────────
def _sse(event: str, data) -> str:
    return f"data: {json.dumps({'event': event, 'data': data})}\n\n"


_mem_store: dict = {}  # local-dev fallback when Redis is unavailable
_redis_client = None
_redis_tried = False


def _get_redis():
    """Return a connected redis client, or None to fall back to the in-process dict."""
    global _redis_client, _redis_tried
    if _redis_tried:
        return _redis_client
    _redis_tried = True
    url = os.getenv("REDIS_URL") or os.getenv("REDIS_PRIVATE_URL")
    if not url:
        return None
    try:
        import redis
        client = redis.from_url(url, decode_responses=True)
        client.ping()
        _redis_client = client
    except Exception as e:  # pragma: no cover
        logger.warning(f"Scoring: Redis unavailable ({e}); using in-process cache.")
        _redis_client = None
    return _redis_client


def _store_run(run_id: str, payload: dict) -> None:
    r = _get_redis()
    if r is not None:
        r.setex(f"scoring:{run_id}", _REDIS_TTL_SECONDS, json.dumps(payload))
    else:
        _mem_store[run_id] = payload


def _load_run(run_id: str) -> Optional[dict]:
    r = _get_redis()
    if r is not None:
        raw = r.get(f"scoring:{run_id}")
        return json.loads(raw) if raw else None
    return _mem_store.get(run_id)


def _dialer_list():
    """All real dialers from config (excludes the 'default' alias). -> [(name, url), ...]."""
    from config import READY_MODE_URLS
    return [(name, url) for name, url in READY_MODE_URLS.items() if name != "default"]


# ── POST /gather (SSE) ─────────────────────────────────────────────────────────
@router.post("/gather")
async def gather(request: GatherRequest, current_user: dict = Depends(get_current_user)):
    """Pull phone+agent CSV from every dialer + this date's flagged calls; cache under a run_id."""
    username = current_user["username"]

    from config import get_user_readymode_credentials
    rm_user, rm_pass = get_user_readymode_credentials(username)
    if not rm_user or not rm_pass:
        raise HTTPException(status_code=400, detail="ReadyMode credentials not configured")

    day = _date.fromisoformat(request.date) if request.date else _date.today()
    rm_date = day.strftime("%m/%d/%Y")
    dialers = _dialer_list()

    log_q: "queue.Queue[Optional[tuple]]" = queue.Queue()
    result_box: dict = {}

    def _pull_dialer(name: str, url: str):
        client = ReadyModeHTTPClient(url)
        client.login(rm_user, rm_pass)
        csv_bytes = client.export_call_log_csv(
            time_from=rm_date, time_to=rm_date, dispositions=SCORING_DISPOSITIONS,
        )
        return name, parse_phone_agent_csv(csv_bytes)

    def worker():
        records_by_dialer: dict = {}
        dialers_ok, dialers_failed = [], []
        try:
            with ThreadPoolExecutor(max_workers=len(dialers)) as ex:
                futures = {ex.submit(_pull_dialer, n, u): n for n, u in dialers}
                done = 0
                for fut in as_completed(futures):
                    name = futures[fut]
                    try:
                        dname, records = fut.result()
                        records_by_dialer[dname] = records
                        dialers_ok.append(dname)
                        log_q.put(("log", f"{dname}: {len(records)} calls"))
                    except ReadyModeLoginError as e:
                        dialers_failed.append(name)
                        log_q.put(("log", f"{name}: skipped ({e})"))
                    except Exception as e:
                        dialers_failed.append(name)
                        log_q.put(("log", f"{name}: error ({e})"))
                    done += 1
                    log_q.put(("progress", json.dumps({"done": done, "total": len(dialers)})))

            rand_index = build_agent_index(records_by_dialer)

            # flagged calls from VOS's own audit data for the same day
            from backend.services.dashboard_service import get_flagged_calls
            flagged = get_flagged_calls(username, day, day)
            flagged_index = build_flagged_index(flagged)

            run_id = uuid.uuid4().hex
            _store_run(run_id, {
                "date": day.isoformat(),
                "rand_index": rand_index,
                "flagged_index": flagged_index,
            })
            total_rows = sum(len(v) for v in records_by_dialer.values())
            result_box["done"] = {
                "run_id": run_id,
                "dialers_ok": dialers_ok,
                "dialers_failed": dialers_failed,
                "agent_count": len(rand_index),
                "flagged_agent_count": len(flagged_index),
                "total_rows": total_rows,
            }
        except Exception as e:
            logger.error(f"Scoring gather failed: {e}", exc_info=True)
            result_box["error"] = str(e)
        finally:
            log_q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    async def event_stream():
        try:
            yield _sse("start", f"Gathering {len(dialers)} dialers for {rm_date}")
            while True:
                try:
                    item = log_q.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.2)
                    yield ": ping\n\n"
                    continue
                if item is None:
                    break
                yield _sse(item[0], item[1])
            if "error" in result_box:
                yield _sse("error", result_box["error"])
            else:
                yield _sse("done", json.dumps(result_box["done"]))
        except (asyncio.CancelledError, GeneratorExit):
            logger.info(f"Scoring gather SSE disconnected for {username}")
            raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── POST /generate ─────────────────────────────────────────────────────────────
@router.post("/generate")
async def generate(request: GenerateRequest, current_user: dict = Depends(get_current_user)):
    """Turn pasted agent names into the per-agent scoring rows for a prior gather run."""
    run = _load_run(request.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Gather run not found or expired — gather again.")
    result = score_agents(run.get("rand_index", {}), run.get("flagged_index", {}), request.agent_names)
    result["date"] = run.get("date")
    return result


# ── POST /audit (SSE) ────────────────────────────────────────────────────────────
@router.post("/audit")
async def audit(request: AuditRequest, current_user: dict = Depends(get_current_user)):
    """Heavy-audit each pasted agent (5 samples, 20s+) and majority-vote the 5 scoring points.

    Reuses a prior /gather run for the agent->busiest-dialer index and the Actions-page
    flagged_index. Per agent: download 5 samples (>=20s, same as Heavy Audit) from the busiest
    dialer, transcribe + detect, then fold into one scoring row via lib.scoring_audit.aggregate_agent
    (Actions-page calls add late-hello/releasing votes). Streams per-agent progress.

    Results are NOT persisted to any dashboard/DB — they're streamed back for the table and
    /export-sheet, exactly like a normal heavy audit that the auditor scores by hand.
    """
    username = current_user["username"]

    run = _load_run(request.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Gather run not found or expired — gather again.")

    from config import get_user_readymode_credentials
    rm_user, rm_pass = get_user_readymode_credentials(username)
    if not rm_user or not rm_pass:
        raise HTTPException(status_code=400, detail="ReadyMode credentials not configured")

    rand_index = run.get("rand_index", {})
    flagged_index = run.get("flagged_index", {})
    run_date = run.get("date")
    day = _date.fromisoformat(run_date) if run_date else _date.today()

    dialer_urls = {name: url for name, url in _dialer_list()}
    rand_keys = set(rand_index.keys())
    flagged_keys = set(flagged_index.keys())

    names = [str(n).strip() for n in (request.agent_names or []) if str(n).strip()]
    total = len(names)

    cancel_event = threading.Event()
    log_q: "queue.Queue[Optional[tuple]]" = queue.Queue()
    result_box: dict = {}

    _AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}

    def _prog(i: int, name: str, phase: str, **extra):
        log_q.put(("progress", json.dumps({"agent_idx": i, "total": total, "agent": name,
                                           "phase": phase, **extra})))

    def worker():
        from lib.scoring_sampler import _match_key
        from lib.scoring_audit import aggregate_agent
        from automation.download_readymode_calls import download_all_call_recordings
        from processing import batch_analyze_folder_fast
        from backend.services.user_service import get_user_settings

        user_api_key = (get_user_settings(username) or {}).get("assemblyai_api_key")

        rows, skipped = [], []
        try:
            for i, name in enumerate(names, start=1):
                if cancel_event.is_set():
                    break

                rk = _match_key(rand_keys, name)
                dmap = rand_index.get(rk, {}) if rk else {}
                action_calls = flagged_index.get(_match_key(flagged_keys, name) or "", [])

                # No dialer presence AND no flagged history → nothing to score.
                if not dmap and not action_calls:
                    skipped.append(name)
                    _prog(i, name, "skipped")
                    continue

                fresh_rows = []
                dialer_name = max(dmap, key=lambda d: len(dmap[d])) if dmap else ""
                dialer_url = dialer_urls.get(dialer_name) if dialer_name else None

                if dialer_url:
                    try:
                        _prog(i, name, "download")
                        folder = download_all_call_recordings(
                            dialer_url=dialer_url,
                            agent=name,
                            start_date=day,
                            end_date=day,
                            max_samples=5,
                            min_duration=20,
                            disposition=SCORING_DISPOSITIONS,  # keep the 2-disposition rule (matches Gather)
                            username=username,
                            readymode_user=rm_user,
                            readymode_pass=rm_pass,
                            cancellation_callback=cancel_event.is_set,
                            update_callback=lambda dl, tot, _i=i, _n=name: _prog(
                                _i, _n, "download", downloaded=dl, dl_total=tot),
                        )
                        if cancel_event.is_set():
                            break
                        folder_path = Path(folder) if isinstance(folder, (str, Path)) else None
                        has_audio = bool(folder_path and folder_path.exists() and any(
                            p.is_file() and p.suffix.lower() in _AUDIO_EXTS
                            for p in folder_path.rglob("*")))
                        if has_audio:
                            _prog(i, name, "analyze")
                            df = batch_analyze_folder_fast(
                                str(folder_path),
                                additional_metadata={"Dialer Name": dialer_name.upper()},
                                show_all_results=True,
                                use_async=True,
                                username=username,
                                user_api_key=user_api_key,
                            )
                            if df is not None and not df.empty:
                                fresh_rows = df.to_dict("records")
                    except Exception as e:
                        # One agent's download/analysis failure shouldn't kill the whole run.
                        logger.warning(f"Scoring audit: {name} download/analyze failed: {e}")
                        log_q.put(("log", f"{name}: {e}"))

                if not fresh_rows and not action_calls:
                    skipped.append(name)
                    _prog(i, name, "skipped")
                    continue

                # pad the phone cell up to 5 with random unused numbers from this agent's CSV
                # calls on the busiest dialer (fillers only — not scored).
                rows.append(aggregate_agent(name, fresh_rows, action_calls,
                                            dialer=dialer_name.upper(),
                                            pad_pool=dmap.get(dialer_name, [])))
                _prog(i, name, "done")

            # Always keep whatever completed so a cancel still returns partial rows.
            result_box["done"] = {"rows": rows, "skipped": skipped, "date": run_date}
            if cancel_event.is_set():
                result_box["cancelled"] = True
        except Exception as e:
            logger.error(f"Scoring audit failed: {e}", exc_info=True)
            result_box["error"] = str(e)
        finally:
            log_q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    async def event_stream():
        try:
            yield _sse("start", f"Auditing {total} agent(s)")
            while True:
                try:
                    item = log_q.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.2)
                    yield ": ping\n\n"
                    continue
                if item is None:
                    break
                yield _sse(item[0], item[1])
            if result_box.get("cancelled"):
                yield _sse("cancelled", json.dumps(result_box.get("done") or {"rows": [], "skipped": []}))
            elif "error" in result_box:
                yield _sse("error", result_box["error"])
            else:
                yield _sse("done", json.dumps(result_box.get("done", {"rows": [], "skipped": []})))
        except (asyncio.CancelledError, GeneratorExit):
            cancel_event.set()
            logger.info(f"Scoring audit SSE disconnected for {username}")
            raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── POST /export-sheet ──────────────────────────────────────────────────────────
@router.post("/export-sheet")
async def export_sheet(request: ExportSheetRequest, current_user: dict = Depends(get_current_user)):
    """Append the generated scoring rows to the logged-in auditor's tab of the company sheet.

    One row per agent. We write only Agent Name, Phone Number, Dialer, and the scoring defaults
    (with the 2 VOS-driven columns); RES-ID / TL Name / Auditor / Date / Performance Index are
    sheet array-formulas that auto-fill off Agent Name — see lib.google_workspace.append_scoring_rows.
    """
    if not request.rows:
        raise HTTPException(status_code=400, detail="No rows to export")

    username = current_user["username"]
    tab = LOGIN_TO_TAB.get(username.strip().lower())
    if not tab:
        raise HTTPException(
            status_code=400,
            detail=(f"No scoring tab is mapped for '{username}'. Ask an admin to add you to "
                    f"the scoring tab map before exporting."),
        )

    def _append():
        from lib.google_workspace import get_service_account_credentials, build_sheets, append_scoring_rows
        creds = get_service_account_credentials()
        sheets_svc = build_sheets(creds)
        return append_scoring_rows(sheets_svc, COMPANY_SCORING_SHEET_ID, tab, request.rows)

    try:
        result = await asyncio.to_thread(_append)
    except Exception as e:
        logger.error(f"Scoring export-sheet (append) failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    return result
