"""
Audio processing API endpoints.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from typing import Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.schemas import (
    AudioUploadResponse,
    ProcessAudioRequest,
    ProcessingStatus,
    ProcessingResult
)
from backend.core.dependencies import get_current_user
from backend.services.audio_service import (
    upload_audio_file,
    process_audio,
    get_job_status,
    get_job_result
)
from backend.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload", response_model=AudioUploadResponse)
async def upload_audio(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload audio file for processing."""
    try:
        # Check file size
        file_content = await file.read()
        if len(file_content) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB"
            )
        
        # Upload file
        file_info = await upload_audio_file(
            file_content,
            file.filename,
            current_user["username"]
        )
        
        return AudioUploadResponse(
            file_id=file_info["file_id"],
            filename=file_info["filename"],
            message="File uploaded successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File upload failed"
        )


@router.post("/process")
async def process_audio_endpoint(
    request: ProcessAudioRequest,
    current_user: dict = Depends(get_current_user)
):
    """Start audio processing job."""
    try:
        # Get file path from file_id (simplified - in production, store file mapping)
        upload_dir = settings.UPLOAD_DIR / current_user["username"]
        files = list(upload_dir.glob(f"{request.file_id}_*"))
        if not files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        file_path = str(files[0])
        
        # Start processing
        job_id = await process_audio(
            request.file_id,
            file_path,
            request.audit_type,
            current_user["username"],
            request.options
        )
        
        return {"job_id": job_id, "message": "Processing started"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Process error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Processing failed to start"
        )


@router.get("/status/{job_id}", response_model=ProcessingStatus)
async def get_processing_status(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get processing job status."""
    job = get_job_status(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Verify job belongs to user
    if job.get("username") != current_user["username"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return ProcessingStatus(
        job_id=job_id,
        status=job.get("status", "unknown"),
        progress=job.get("progress", 0.0),
        message=job.get("error")
    )


@router.get("/results/{job_id}", response_model=ProcessingResult)
async def get_processing_results(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get processing job results."""
    job = get_job_status(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Verify job belongs to user
    if job.get("username") != current_user["username"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    result = get_job_result(job_id)
    
    return ProcessingResult(
        job_id=job_id,
        status=job.get("status", "unknown"),
        transcript=result.get("transcript") if result else None,
        agent_transcript=result.get("agent_transcript") if result else None,
        customer_transcript=result.get("customer_transcript") if result else None,
        rebuttals=result.get("rebuttals") if result else None,
        accent_corrections=result.get("accent_corrections") if result else None,
        metadata=result.get("metadata") if result else None,
        error=job.get("error")
    )

