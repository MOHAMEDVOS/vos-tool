"""
Audio processing API endpoints.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from typing import Optional, Dict
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
        message=job.get("error"),
        stage=job.get("stage")
    )


def _extract_transcription_status(result_dict: Optional[Dict], stored_metadata: Optional[Dict]) -> Optional[str]:
    """Extract transcription status from result or metadata."""
    if not result_dict and not stored_metadata:
        return None
    
    # Check result dict first
    if result_dict:
        # Direct transcription status
        if "transcription_status" in result_dict:
            return result_dict["transcription_status"]
        
        # Check nested result structure (batch format)
        if "result" in result_dict and isinstance(result_dict["result"], list) and result_dict["result"]:
            first_item = result_dict["result"][0]
            if isinstance(first_item, dict) and "transcription_status" in first_item:
                return first_item["transcription_status"]
    
    # Check metadata
    if stored_metadata:
        if "transcription_status" in stored_metadata:
            return stored_metadata["transcription_status"]
    
    # Check for error patterns
    if result_dict:
        # Check if transcript is empty but processing completed
        transcript = result_dict.get("transcript", "")
        if not transcript and result_dict.get("classification_success") is False:
            return "failed"
        
        # Check for timeout indicators
        error = result_dict.get("error", "")
        if "timeout" in error.lower():
            return "timeout"
    
    return None


def _extract_transcription_error(result_dict: Optional[Dict], stored_metadata: Optional[Dict]) -> Optional[str]:
    """Extract transcription error from result or metadata."""
    if not result_dict and not stored_metadata:
        return None
    
    # Check result dict first
    if result_dict:
        # Direct transcription error
        if "transcription_error" in result_dict:
            return result_dict["transcription_error"]
        
        # Check nested result structure (batch format)
        if "result" in result_dict and isinstance(result_dict["result"], list) and result_dict["result"]:
            first_item = result_dict["result"][0]
            if isinstance(first_item, dict) and "transcription_error" in first_item:
                return first_item["transcription_error"]
        
        # Check general error field for transcription-related errors
        error = result_dict.get("error", "")
        if error and any(keyword in error.lower() for keyword in ["transcription", "assemblyai", "api", "timeout"]):
            return error
    
    # Check metadata
    if stored_metadata:
        if "transcription_error" in stored_metadata:
            return stored_metadata["transcription_error"]
    
    return None


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

    # The stored result is a DataFrame-like payload (list[dict]) plus optional metadata.
    # For now, expose it in `metadata` to keep the schema stable until we add richer fields.
    stored_metadata = None
    try:
        stored_metadata = job.get("result_json", {}).get("metadata") if isinstance(job.get("result_json"), dict) else None
    except Exception:
        stored_metadata = None

    result_dict = result if isinstance(result, dict) else None
    result_payload = result if not isinstance(result, dict) else None

    merged_metadata = None
    if result_dict and result_dict.get("metadata") is not None:
        merged_metadata = result_dict.get("metadata")
    elif result_payload is not None:
        merged_metadata = {
            "result": result_payload,
            "metadata": stored_metadata,
        }
    else:
        merged_metadata = stored_metadata

    return ProcessingResult(
        job_id=job_id,
        status=job.get("status", "unknown"),
        transcript=result_dict.get("transcript") if result_dict else None,
        agent_transcript=result_dict.get("agent_transcript") if result_dict else None,
        customer_transcript=result_dict.get("customer_transcript") if result_dict else None,
        rebuttals=result_dict.get("rebuttals") if result_dict else None,
        accent_corrections=result_dict.get("accent_corrections") if result_dict else None,
        metadata=merged_metadata,
        error=job.get("error"),
        # New transcription-specific fields
        transcription_status=_extract_transcription_status(result_dict, stored_metadata),
        transcription_error=_extract_transcription_error(result_dict, stored_metadata),
        processing_stage=job.get("stage")
    )
