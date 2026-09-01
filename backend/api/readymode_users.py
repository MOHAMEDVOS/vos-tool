"""
Bulk ReadyMode user management — POST /api/readymode-users/{create,delete,duplicates}
Streams per-item results as SSE-style JSON lines.
"""

import sys
import json
import threading
from pathlib import Path
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.schemas import (
    BulkUserCreateRequest,
    BulkUserDeleteRequest,
    FindDuplicateUsersRequest,
)
from backend.core.dependencies import get_current_user, get_current_admin_user

# Reuse the thread-local stdout proxy already installed by readymode.py at import time.
# (importing readymode ensures the proxy is installed before we start worker threads)
import backend.api.readymode  # noqa: F401 — side-effect: installs _ThreadLocalStdout

import logging
logger = logging.getLogger(__name__)
router = APIRouter()


def _sse(event: str, data) -> str:
    return f"data: {json.dumps({'event': event, 'data': data})}\n\n"


def _resolve_readymode_credentials(current_user: dict) -> tuple[str, str]:
    """Shared creation-account credentials from env, falling back to the caller's own."""
    import os
    create_user = os.environ.get("READYMODE_CREATE_USER", "UserCreation")
    create_pass = os.environ.get("READYMODE_CREATE_PASSWORD", "RES370@370")

    if not create_pass:
        from config import get_user_readymode_credentials
        create_user, create_pass = get_user_readymode_credentials(current_user["username"])

    if not create_user or not create_pass:
        raise HTTPException(status_code=400, detail="ReadyMode creation credentials not configured")
    return create_user, create_pass


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

    create_user, create_pass = _resolve_readymode_credentials(current_user)

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

    def create_stream():
        while True:
            item = result_queue.get()
            if item is None:
                break
            yield item

    return StreamingResponse(create_stream(), media_type="text/event-stream")


@router.post("/delete")
async def bulk_delete_users(
    request: BulkUserDeleteRequest,
    current_user: dict = Depends(get_current_admin_user),
):
    """Delete users from one or more ReadyMode dialers in parallel, stream results.

    Admin-gated server-side (unlike /create, which only relies on the frontend hiding its
    tab from non-admins) — deleting is destructive against a production platform, so this
    one doesn't repeat that gap.

    Each row is either a `name` (resolved to a uid via that dialer's call-log userlist,
    same as always) or an exact `uid` (deletes that account directly, no resolution — used
    by the duplicates scan to target one specific account precisely). A uid is only
    meaningful on the dialer it came from, so a uid-carrying request is restricted to
    exactly one dialer — broadcasting a uid across multiple dialers would risk deleting an
    unrelated real person wherever that same numeric id happens to belong to someone else.
    """
    if not request.dialer_urls:
        raise HTTPException(status_code=400, detail="At least one dialer URL required")
    if not request.users:
        raise HTTPException(status_code=400, detail="No users provided")
    if any(u.uid for u in request.users) and len(request.dialer_urls) != 1:
        raise HTTPException(
            status_code=400,
            detail="Exact-uid deletes must target exactly one dialer per request "
                   "(a uid is only meaningful on the dialer it was scanned from).",
        )

    create_user, create_pass = _resolve_readymode_credentials(current_user)

    targets = [u.model_dump() for u in request.users]
    dialer_urls = request.dialer_urls

    result_queue: "queue.Queue[str | None]" = __import__("queue").Queue()

    def log_callback(msg: str):
        result_queue.put(_sse("log", msg.rstrip()))

    def worker():
        try:
            from automation.delete_readymode_users import delete_users_multi_dialer
            results = delete_users_multi_dialer(
                dialer_urls=dialer_urls,
                targets=targets,
                readymode_user=create_user,
                readymode_pass=create_pass,
                log_callback=log_callback,
            )
            result_queue.put(_sse("done", results))
        except Exception as e:
            logger.error(f"bulk_delete_users worker error: {e}", exc_info=True)
            result_queue.put(_sse("error", str(e)))
        finally:
            result_queue.put(None)  # sentinel

    threading.Thread(target=worker, daemon=True).start()

    def delete_stream():
        while True:
            item = result_queue.get()
            if item is None:
                break
            yield item

    return StreamingResponse(delete_stream(), media_type="text/event-stream")


@router.post("/duplicates")
async def find_duplicate_users(
    request: FindDuplicateUsersRequest,
    current_user: dict = Depends(get_current_admin_user),
):
    """Scan one or more ReadyMode dialers for accounts sharing a display name, stream
    one 'log' line per dialer plus a final 'done' event with the per-dialer group
    breakdown. Read-only — never deletes; use POST /delete with an explicit `uid` per
    row to remove a specific duplicate found here.

    Admin-gated, same as /delete: this exposes the full recently-active account roster
    per dialer and is the direct precursor to a destructive action.
    """
    if not request.dialer_urls:
        raise HTTPException(status_code=400, detail="At least one dialer URL required")

    create_user, create_pass = _resolve_readymode_credentials(current_user)

    dialer_urls = request.dialer_urls

    result_queue: "queue.Queue[str | None]" = __import__("queue").Queue()

    def log_callback(msg: str):
        result_queue.put(_sse("log", msg.rstrip()))

    def worker():
        try:
            from automation.find_duplicate_readymode_users import find_duplicate_users_multi_dialer
            results = find_duplicate_users_multi_dialer(
                dialer_urls=dialer_urls,
                readymode_user=create_user,
                readymode_pass=create_pass,
                log_callback=log_callback,
            )
            result_queue.put(_sse("done", results))
        except Exception as e:
            logger.error(f"find_duplicate_users worker error: {e}", exc_info=True)
            result_queue.put(_sse("error", str(e)))
        finally:
            result_queue.put(None)  # sentinel

    threading.Thread(target=worker, daemon=True).start()

    def duplicates_stream():
        while True:
            item = result_queue.get()
            if item is None:
                break
            yield item

    return StreamingResponse(duplicates_stream(), media_type="text/event-stream")
