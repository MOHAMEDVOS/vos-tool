"""Owner controls and authenticated job routes for the local ReadyMode worker."""

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field

from backend.core.dependencies import get_current_owner_user
from backend.services import readymode_worker_service as worker_service

router = APIRouter()


class WorkerJobResult(BaseModel):
    claim_token: str
    result: dict


class WorkerJobProgress(BaseModel):
    claim_token: str
    message: str = Field(max_length=255)


class WorkerJobFailure(BaseModel):
    claim_token: str
    error_code: str = Field(max_length=60)


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
