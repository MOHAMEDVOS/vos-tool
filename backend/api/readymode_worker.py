"""Owner controls and authenticated job routes for the local ReadyMode worker."""

import json
import base64
import os
import re
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from backend.core.dependencies import get_current_owner_user
from backend.services import readymode_worker_service as worker_service

router = APIRouter()
MAX_WORKER_RECORDING_BYTES = 100 * 1024 * 1024


class WorkerJobResult(BaseModel):
    claim_token: str
    result: dict


class WorkerJobProgress(BaseModel):
    claim_token: str
    message: str = Field(max_length=255)


class WorkerJobFailure(BaseModel):
    claim_token: str
    error_code: str = Field(max_length=60)


class WorkerRecordingClaim(BaseModel):
    claim_token: str
    dialer_host: str
    recording_ids: list[str]
    force_reaudit: bool = False


class WorkerRecordingRelease(BaseModel):
    claim_token: str
    recordings: list[dict[str, str]]


def _require_worker(authorization: str | None = Header(default=None)) -> None:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not worker_service.authenticate_worker(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid worker token")


@router.get("/settings")
async def get_worker_settings(_: dict = Depends(get_current_owner_user)):
    return {
        "execution_mode": worker_service.get_execution_mode(),
        **worker_service.worker_status(),
    }


@router.post("/token")
async def rotate_worker_token(_: dict = Depends(get_current_owner_user)):
    response = Response(
        content=json.dumps({"token": worker_service.issue_worker_token()}),
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )
    return response


@router.post("/jobs/claim")
async def claim_worker_job(
    _: None = Depends(_require_worker),
):
    job = worker_service.claim_job()
    if job is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return job


@router.post("/jobs/{job_id}/progress")
async def update_worker_job_progress(
    job_id: str,
    request: WorkerJobProgress,
    _: None = Depends(_require_worker),
):
    if not worker_service.update_progress(job_id, request.claim_token, request.message):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Worker job lease expired")
    return {"success": True}


@router.post("/jobs/{job_id}/complete")
async def complete_worker_job(
    job_id: str,
    request: WorkerJobResult,
    _: None = Depends(_require_worker),
):
    if not worker_service.complete_job(job_id, request.claim_token, request.result):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Worker job lease expired")
    return {"success": True}


@router.post("/jobs/{job_id}/fail")
async def fail_worker_job(
    job_id: str,
    request: WorkerJobFailure,
    _: None = Depends(_require_worker),
):
    if not worker_service.fail_job(job_id, request.claim_token, request.error_code):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Worker job lease expired")
    return {"success": True}


@router.post("/jobs/{job_id}/recordings/claim")
async def claim_worker_recordings(
    job_id: str,
    request: WorkerRecordingClaim,
    _: None = Depends(_require_worker),
):
    context = worker_service.get_claimed_job_context(job_id, request.claim_token)
    if not context or context["job_type"] != "readymode_recordings":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Worker job lease expired")
    from backend.services.readymode_recording_registry import claim_recordings

    claimed = claim_recordings(
        context["username"],
        request.dialer_host,
        request.recording_ids,
        job_id,
        request.force_reaudit,
    )
    return {"claimed_ids": sorted(claimed)}


@router.post("/jobs/{job_id}/recordings/release")
async def release_worker_recordings(
    job_id: str,
    request: WorkerRecordingRelease,
    _: None = Depends(_require_worker),
):
    context = worker_service.get_claimed_job_context(job_id, request.claim_token)
    if not context or context["job_type"] != "readymode_recordings":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Worker job lease expired")
    from backend.services.readymode_recording_registry import release_recordings

    count = release_recordings(context["username"], request.recordings, job_id)
    return {"released_count": count}


@router.put("/jobs/{job_id}/recordings/upload")
async def upload_worker_recording(
    job_id: str,
    request: Request,
    claim_token: str = Header(alias="X-Worker-Claim-Token"),
    metadata_header: str = Header(alias="X-Worker-Recording-Metadata"),
    _: None = Depends(_require_worker),
):
    context = worker_service.get_claimed_job_context(job_id, claim_token)
    if not context or context["job_type"] != "readymode_recordings":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Worker job lease expired")
    if len(metadata_header) > 8192:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recording metadata")
    try:
        metadata = json.loads(base64.urlsafe_b64decode(metadata_header.encode("ascii")))
        filename = str(metadata["filename"])
        dialer_name = str(metadata["dialer_name"])
        dialer_host = str(metadata.get("dialer_host", ""))
        recording_id = str(metadata.get("recording_id", ""))
    except (ValueError, KeyError, TypeError, UnicodeEncodeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recording metadata")
    if not filename or len(filename) > 255 or not dialer_name or len(dialer_name) > 60:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recording metadata")
    if len(dialer_host) > 255 or len(recording_id) > 255:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recording metadata")
    track_recordings = bool(context["payload"].get("track_recordings", True))
    if track_recordings and recording_id and not worker_service.recording_is_claimed(
        context["username"], dialer_host, recording_id, job_id
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Recording was not claimed for this job")

    from config import RECORDINGS_ROOT

    root = Path(RECORDINGS_ROOT).resolve()
    directory = Path((context["payload"].get("download_dirs") or {}).get(dialer_name, "")).resolve()
    if directory == root or not directory.is_relative_to(root):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recording directory")
    directory.mkdir(parents=True, exist_ok=True)

    safe_name = os.path.basename(filename.replace("\\", "/"))
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", safe_name).strip(" .")[:220]
    if not safe_name or not safe_name.lower().endswith((".mp3", ".wav", ".m4a", ".ogg", ".flac")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid audio filename")
    destination = directory / safe_name
    if destination.exists():
        suffix = re.sub(r"[^A-Za-z0-9_-]", "", recording_id)[:16] or os.urandom(4).hex()
        destination = destination.with_name(f"{destination.stem}_{suffix}{destination.suffix}")
    temporary = destination.with_name(f".{destination.name}.{job_id}.tmp")

    try:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_WORKER_RECORDING_BYTES:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Recording is too large")
        total_bytes = 0
        last_heartbeat = time.monotonic()
        with temporary.open("wb") as stream:
            async for chunk in request.stream():
                total_bytes += len(chunk)
                if total_bytes > MAX_WORKER_RECORDING_BYTES:
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Recording is too large")
                stream.write(chunk)
                if time.monotonic() - last_heartbeat >= 30:
                    if not worker_service.update_progress(job_id, claim_token, "Uploading recording"):
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Worker job lease expired")
                    last_heartbeat = time.monotonic()
        if total_bytes == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty recording upload")
        if not worker_service.get_claimed_job_context(job_id, claim_token):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Worker job lease expired")

        from automation.download_readymode_calls import _probe_duration_seconds

        try:
            duration = _probe_duration_seconds(str(temporary))
        except Exception:
            temporary.unlink(missing_ok=True)
            return {"accepted": False, "reason": "duration_check_failed"}
        min_duration = context["payload"].get("min_duration")
        max_duration = context["payload"].get("max_duration")
        if (min_duration is not None and duration < min_duration) or (
            max_duration is not None and duration > max_duration
        ):
            temporary.unlink(missing_ok=True)
            return {"accepted": False, "reason": "duration_filter"}

        os.replace(temporary, destination)
        return {"accepted": True, "file_path": str(destination)}
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
