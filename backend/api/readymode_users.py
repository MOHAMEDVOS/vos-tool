"""
Bulk ReadyMode user management — POST /api/readymode-users/{create,delete,duplicates}
Streams per-item results as SSE-style JSON lines.
"""

import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.schemas import (
    BulkUserCreateRequest,
    BulkUserDeleteRequest,
    FindDuplicateUsersRequest,
    FindInactiveUsersRequest,
)
from backend.core.dependencies import get_current_user, get_current_admin_user
from backend.core.sse import SSEEmitter, run_sse_stream

import logging
logger = logging.getLogger(__name__)
router = APIRouter()


def _resolve_readymode_credentials(current_user: dict) -> tuple[str, str]:
    """Use the caller's saved ReadyMode credentials, matching audits and Scoring."""
    from config import get_user_readymode_credentials

    readymode_user, readymode_pass = get_user_readymode_credentials(current_user["username"])
    if not readymode_user or not readymode_pass:
        raise HTTPException(status_code=400, detail="ReadyMode credentials not configured")
    return readymode_user, readymode_pass


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

    def worker(emitter: SSEEmitter):
        def log_callback(msg: str):
            emitter.send("log", msg.rstrip())

        try:
            from automation.create_readymode_users import create_users_multi_dialer
            results = create_users_multi_dialer(
                dialer_urls=dialer_urls,
                users=users_dicts,
                readymode_user=create_user,
                readymode_pass=create_pass,
                log_callback=log_callback,
            )
            emitter.send("done", results)
        except Exception as e:
            logger.error(f"bulk_create_users worker error: {e}", exc_info=True)
            emitter.send("error", str(e))

    return run_sse_stream(worker, keepalive=False)


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

    def worker(emitter: SSEEmitter):
        def log_callback(msg: str):
            emitter.send("log", msg.rstrip())

        try:
            from automation.delete_readymode_users import delete_users_multi_dialer
            results = delete_users_multi_dialer(
                dialer_urls=dialer_urls,
                targets=targets,
                readymode_user=create_user,
                readymode_pass=create_pass,
                log_callback=log_callback,
            )
            emitter.send("done", results)
        except Exception as e:
            logger.error(f"bulk_delete_users worker error: {e}", exc_info=True)
            emitter.send("error", str(e))

    return run_sse_stream(worker, keepalive=False)


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

    def worker(emitter: SSEEmitter):
        def log_callback(msg: str):
            emitter.send("log", msg.rstrip())

        try:
            from automation.find_duplicate_readymode_users import find_duplicate_users_multi_dialer
            results = find_duplicate_users_multi_dialer(
                dialer_urls=dialer_urls,
                readymode_user=create_user,
                readymode_pass=create_pass,
                log_callback=log_callback,
            )
            emitter.send("done", results)
        except Exception as e:
            logger.error(f"find_duplicate_users worker error: {e}", exc_info=True)
            emitter.send("error", str(e))

    return run_sse_stream(worker, keepalive=False)


@router.post("/inactive")
async def find_inactive_users(
    request: FindInactiveUsersRequest,
    current_user: dict = Depends(get_current_admin_user),
):
    """Scan one or more ReadyMode dialers for accounts with little-to-no recent shift
    activity (a login/shift signal, not a call-volume one), stream one 'log' line per
    dialer plus a final 'done' event with the per-dialer candidate list. Read-only —
    never deletes; use POST /delete with an explicit `uid` per row to remove a specific
    candidate found here.

    Admin-gated, same as /delete and /duplicates: this exposes the full account roster
    per dialer (via folder scans) and is the direct precursor to a destructive action.
    """
    if not request.dialer_urls:
        raise HTTPException(status_code=400, detail="At least one dialer URL required")
    if request.max_days_active < 0:
        raise HTTPException(status_code=400, detail="max_days_active must be 0 or greater")
    if request.lookback_days < 1:
        raise HTTPException(status_code=400, detail="lookback_days must be at least 1")

    create_user, create_pass = _resolve_readymode_credentials(current_user)

    dialer_urls = request.dialer_urls
    max_days_active = request.max_days_active
    lookback_days = request.lookback_days

    def worker(emitter: SSEEmitter):
        def log_callback(msg: str):
            emitter.send("log", msg.rstrip())

        try:
            from automation.find_inactive_readymode_users import find_inactive_users_multi_dialer
            results = find_inactive_users_multi_dialer(
                dialer_urls=dialer_urls,
                readymode_user=create_user,
                readymode_pass=create_pass,
                max_days_active=max_days_active,
                lookback_days=lookback_days,
                log_callback=log_callback,
            )
            emitter.send("done", results)
        except Exception as e:
            logger.error(f"find_inactive_users worker error: {e}", exc_info=True)
            emitter.send("error", str(e))

    return run_sse_stream(worker, keepalive=False)
