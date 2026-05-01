"""
System endpoints (gaps G7, G8, G10).

Lightweight endpoints the React UI needs that aren't covered by the
existing /health or /health/detailed routes.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.dependencies import get_current_user, get_current_admin_user, get_current_owner_user
from backend.models.schemas import GenericActionResponse
from backend.services import system_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/readonly-status")
async def readonly_status(_: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """Public-to-any-authenticated-user: is the app in migration/readonly mode?"""
    return system_service.get_readonly_status()


@router.get("/health")
async def system_health(_: dict = Depends(get_current_admin_user)) -> Dict[str, Any]:
    """Host CPU / memory / disk for the Settings UI."""
    return system_service.get_system_health()


@router.get("/sessions")
async def list_sessions(_: dict = Depends(get_current_owner_user)) -> List[Dict[str, Any]]:
    return system_service.list_active_sessions()


@router.get("/recordings/serve")
async def serve_recording(
    file_path: str = Query(None, description="Absolute path from File Path column"),
    filename:  str = Query(None, description="Filename for recursive search"),
    phone:     str = Query(None, description="Phone number for digits search"),
    current_user: dict = Depends(get_current_user),
):
    """Serve an .mp3 recording for the Call Review audio player.

    Applies the same 3-priority lookup used by the legacy call review UI:
      1. file_path (exact path)
      2. filename  (recursive search in RECORDINGS_ROOT)
      3. phone     (match digits in .mp3 filenames)

    Ownership check: the resolved path must be owned by the caller — either
    under their user-scoped recordings directory or referenced by one of their
    own audit rows.
    """
    resolved = system_service.resolve_recording_path(file_path, filename, phone)
    if resolved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording file not found",
        )

    if not system_service.caller_owns_recording(current_user["username"], resolved):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this recording is not permitted",
        )

    return FileResponse(path=str(resolved), media_type="audio/mpeg", filename=resolved.name)


@router.get("/recordings/words")
async def serve_word_timestamps(
    file_path: str = Query(None, description="Absolute path from File Path column"),
    filename:  str = Query(None, description="Filename for recursive search"),
    phone:     str = Query(None, description="Phone number for digits search"),
    current_user: dict = Depends(get_current_user),
):
    """Return word-level timestamps for a recording from the transcription cache.

    Returns [] when the file has no cached transcript or the transcript was
    stored without word-level data (e.g. older provider or mono-only run).
    Words are in seconds (AssemblyAI stores milliseconds — we convert here).
    """
    resolved = system_service.resolve_recording_path(file_path, filename, phone)
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not found")

    if not system_service.caller_owns_recording(current_user["username"], resolved):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access not permitted")

    words = system_service.get_word_timestamps(resolved)
    return {"words": words}


@router.post("/sessions/{username}/invalidate", response_model=GenericActionResponse)
async def invalidate_user_session(
    username: str,
    _: dict = Depends(get_current_owner_user),
):
    ok = system_service.invalidate_session(username)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active session for {username}",
        )
    return GenericActionResponse(success=True, message=f"Session for {username} invalidated")
