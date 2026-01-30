from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional
import os
import uuid
from datetime import datetime
import logging

from backend.core.dependencies import get_current_user
from backend.services.job_store import create_job, get_job, update_job
from backend.job_tasks.processing_tasks import process_audio_batch_task
from backend.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

from pydantic import BaseModel

class BatchJobRequest(BaseModel):
    folder_path: str
    metadata: Optional[dict] = None

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    stage: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    result: Optional[dict] = None
    error: Optional[str] = None

@router.post("/submit", response_model=dict)
async def submit_batch_job(
    request: BatchJobRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Submit a batch audio processing job.
    """
    # Generate Job ID
    job_id = str(uuid.uuid4())
    username = current_user['username']
    
    # Check concurrent job limit (optional, simple check)
    # count = get_active_jobs_count(username)
    # if count >= MAX_JOBS: raise HTTPException(429, "Too many active jobs")
    
    # Create job in database
    try:
        create_job(
            job_id=job_id,
            username=username,
            status="pending",
            file_path=request.folder_path,
            audit_type="batch_full",
            options=request.metadata
        )
    except Exception as e:
        logger.error(f"Failed to create job record: {e}")
        raise HTTPException(status_code=500, detail="Failed to create job record")

    # Enqueue Celery task
    try:
        # We pass the token separately if needed, or let the task fetch it
        process_audio_batch_task.delay(
            job_id=job_id,
            folder_path=request.folder_path,
            username=username,
            metadata=request.metadata
        )
    except Exception as e:
        logger.error(f"Failed to enqueue task: {e}")
        # Mark job as failed immediately if enqueue fails
        update_job(job_id, status="failed", error="Failed to enqueue background task")
        raise HTTPException(status_code=500, detail="Failed to start processing task")

    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Job submitted successfully"
    }

@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status_endpoint(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get the status of a specific job.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Security check: only allow owner to see job
    if job['username'] != current_user['username']:
        # Admin override could be added here
        raise HTTPException(status_code=403, detail="Access denied")
        
    return {
        "job_id": job['job_id'],
        "status": job['status'],
        "progress": job.get('progress', 0.0),
        "stage": job.get('stage'),
        "created_at": job.get('created_at'),
        "updated_at": job.get('updated_at'),
        "result": job.get('result_json'),
        "error": job.get('error')
    }

@router.get("/user/list", response_model=List[JobStatusResponse])
async def list_user_jobs(
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """
    List recent jobs for the current user.
    """
    db = get_db()
    
    # This should ideally be in job_store.py as get_user_jobs
    # For now, quick implementation here or I should add it to job_store.
    # Let's add inline query for now to save a context switch.
    
    query = """
    SELECT * FROM processing_jobs 
    WHERE username = %s 
    ORDER BY created_at DESC 
    LIMIT %s
    """
    
    # Handle SQLite/pg param style
    if getattr(db, "db_type", "postgresql") == "sqlite":
         query = query.replace("%s", "?")
    
    rows = db.execute_query(query, params=(current_user['username'], limit), fetch=True)
    
    results = []
    for row in rows:
        # Re-use normalization logic from get_job if needed, or simple dict match
        results.append({
            "job_id": row['job_id'],
            "status": row['status'],
            "progress": row.get('progress', 0.0),
            "stage": row.get('stage'),
            "created_at": row.get('created_at'),
            "updated_at": row.get('updated_at'),
            "result": row.get('result_json'), # Might need JSON parsing if returned as str
            "error": row.get('error')
        })
        
    return results
