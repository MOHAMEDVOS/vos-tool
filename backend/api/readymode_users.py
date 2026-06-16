"""
Bulk ReadyMode user creation — POST /api/readymode-users/create
Streams per-user results as JSON lines (no SSE needed — fast enough for sync).
"""

import sys
import json
import threading
from pathlib import Path
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.schemas import BulkUserCreateRequest
from backend.core.dependencies import get_current_user

# Reuse the thread-local stdout proxy already installed by readymode.py at import time.
# (importing readymode ensures the proxy is installed before we start worker threads)
import backend.api.readymode  # noqa: F401 — side-effect: installs _ThreadLocalStdout

import logging
logger = logging.getLogger(__name__)
router = APIRouter()


def _sse(event: str, data) -> str:
    return f"data: {json.dumps({'event': event, 'data': data})}\n\n"


@router.post("/create")
async def bulk_create_users(
    request: BulkUserCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create users on one or more ReadyMode dialers in parallel, stream results."""
    if not request.dialer_urls:
        raise HTTPException(status_code=400, detail="At least one dialer URL required")
    if not request.users:
        raise HTTPException(status_code=400, detail="No users provided")

    # Pull the shared creation-account credentials from env / config
    import os
    create_user = os.environ.get("READYMODE_CREATE_USER", "UserCreation")
    create_pass = os.environ.get("READYMODE_CREATE_PASSWORD", "RES370@370")

    if not create_pass:
        # Fallback: try the user's own ReadyMode credentials
        from config import get_user_readymode_credentials
        create_user, create_pass = get_user_readymode_credentials(current_user["username"])

    if not create_user or not create_pass:
        raise HTTPException(status_code=400, detail="ReadyMode creation credentials not configured")

    users_dicts = [u.model_dump() for u in request.users]
    dialer_urls = request.dialer_urls

    result_queue: "queue.Queue[str | None]" = __import__("queue").Queue()

    def log_callback(msg: str):
        result_queue.put(_sse("log", msg.rstrip()))

    def worker():
        try:
            from automation.create_readymode_users import create_users_multi_dialer
            results = create_users_multi_dialer(
                dialer_urls=dialer_urls,
                users=users_dicts,
                readymode_user=create_user,
                readymode_pass=create_pass,
                log_callback=log_callback,
            )
            result_queue.put(_sse("done", results))
        except Exception as e:
            logger.error(f"bulk_create_users worker error: {e}", exc_info=True)
            result_queue.put(_sse("error", str(e)))
        finally:
            result_queue.put(None)  # sentinel

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            item = result_queue.get()
            if item is None:
                break
            yield item

    return StreamingResponse(stream(), media_type="text/event-stream")
