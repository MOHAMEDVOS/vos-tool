"""
Audio processing service.
Handles audio upload, transcription, and analysis.
"""

import os
import uuid
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.config import settings
from lib.dashboard_manager import dashboard_manager

logger = logging.getLogger(__name__)

# In-memory job storage (in production, use Redis or database)
_jobs: Dict[str, Dict[str, Any]] = {}


async def upload_audio_file(file_content: bytes, filename: str, username: str) -> Dict[str, Any]:
    """Upload and save audio file."""
    try:
        # Create upload directory
        upload_dir = settings.UPLOAD_DIR / username
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        file_path = upload_dir / f"{file_id}_{filename}"
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        return {
            "file_id": file_id,
            "filename": filename,
            "file_path": str(file_path),
            "size": len(file_content)
        }
    except Exception as e:
        logger.error(f"File upload error: {e}", exc_info=True)
        raise


async def process_audio(
    file_id: str,
    file_path: str,
    audit_type: str,
    username: str,
    options: Optional[Dict[str, Any]] = None
) -> str:
    """Process audio file and return job ID."""
    job_id = str(uuid.uuid4())
    
    # Initialize job
    _jobs[job_id] = {
        "status": "pending",
        "file_id": file_id,
        "file_path": file_path,
        "audit_type": audit_type,
        "username": username,
        "created_at": datetime.now().isoformat(),
        "progress": 0.0
    }
    
    # Start processing in background
    asyncio.create_task(_process_audio_background(job_id, file_path, audit_type, username, options))
    
    return job_id


async def _process_audio_background(
    job_id: str,
    file_path: str,
    audit_type: str,
    username: str,
    options: Optional[Dict[str, Any]]
):
    """Background task for audio processing."""
    try:
        _jobs[job_id]["status"] = "processing"
        _jobs[job_id]["progress"] = 0.1
        
        # Get user's AssemblyAI API key if available
        user_api_key = None
        api_key_source = "global"
        try:
            from backend.services.user_service import get_user_settings
            user_settings = get_user_settings(username)
            # Use decrypted plaintext key exposed by get_user_settings; this is
            # what AssemblyAITranscriptionEngine expects.
            user_api_key = user_settings.get("assemblyai_api_key")
            if user_api_key:
                api_key_source = "user"
                logger.info(f"Using user-specific AssemblyAI API key for user {username}")
            else:
                logger.info(f"Using global AssemblyAI API key for user {username}")
        except Exception as e:
            logger.error(f"Error getting user settings for {username}: {e}")
        
        # Import processing functions
        from processing import batch_analyze_folder, batch_analyze_folder_lite
        from analyzer.rebuttal_detection import analyze_transcript_for_rebuttals
        from lib.egyptian_accent_correction import EgyptianAccentCorrection
        
        # Process based on audit type
        job_metadata = {"API Key Source": api_key_source}

        if audit_type == "lite":
            # Lite audit processing
            _jobs[job_id]["progress"] = 0.3
            result = await asyncio.to_thread(
                batch_analyze_folder_lite,
                str(Path(file_path).parent),
                None,
                job_metadata,
                username,
                user_api_key,  # Pass user API key
            )
        else:
            # Heavy audit processing
            _jobs[job_id]["progress"] = 0.3
            result = await asyncio.to_thread(
                batch_analyze_folder,
                str(Path(file_path).parent),
                username,
                user_api_key,
                job_metadata,
            )
        
        _jobs[job_id]["progress"] = 0.9
        
        # Store result
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["result"] = result
        _jobs[job_id]["progress"] = 1.0
        
        # Release worker pool resources for this user
        try:
            from backend.services.worker_pool_manager import get_worker_pool_manager
            pool_manager = get_worker_pool_manager()
            pool_manager.release_user_workers(username)
            logger.info(f"Released worker pool resources for user {username}")
        except Exception as e:
            logger.warning(f"Could not release worker pool resources: {e}")
        
    except Exception as e:
        logger.error(f"Audio processing error: {e}", exc_info=True)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)
        
        # Release worker pool resources even on error
        try:
            from backend.services.worker_pool_manager import get_worker_pool_manager
            pool_manager = get_worker_pool_manager()
            pool_manager.release_user_workers(username)
            logger.info(f"Released worker pool resources for user {username} after error")
        except Exception:
            pass


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Get processing job status."""
    return _jobs.get(job_id)


def get_job_result(job_id: str) -> Optional[Dict[str, Any]]:
    """Get processing job result."""
    job = _jobs.get(job_id)
    if job and job.get("status") == "completed":
        return job.get("result")
    return None

