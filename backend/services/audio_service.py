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

from backend.services import job_store


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

    # Initialize durable job record
    job_store.create_job(
        job_id,
        username=username,
        status="pending",
        progress=0.0,
        stage="queued",
        file_id=file_id,
        file_path=file_path,
        audit_type=audit_type,
        options=options,
    )
    
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
        job_store.update_job(job_id, status="processing", progress=0.1, stage="starting")
        
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
        from audio_pipeline.audio_processor import AudioProcessor
        from audio_pipeline.fast_audio_processor import FastAudioProcessor
        from audio_pipeline.semantic_audio_processor import SemanticAudioProcessor
        from lib.egyptian_accent_correction import EgyptianAccentCorrection
        
        # Process based on audit type - SINGLE FILE ONLY
        job_metadata = {"API Key Source": api_key_source, "Processing Mode": "single_file"}

        # Get timeout from config
        try:
            from backend.core.config import settings
            if audit_type == "lite":
                timeout = settings.PROCESSING_TIMEOUT_LITE_FILE
            else:
                timeout = settings.PROCESSING_TIMEOUT_SINGLE_FILE
        except ImportError:
            timeout = 600  # 10 minutes default for heavy, 60s for lite

        if audit_type == "lite":
            # Lite audit processing - FAST single file only
            job_store.update_job(job_id, progress=0.3, stage="processing_lite_fast")
            # Use FastAudioProcessor for much faster lite processing
            processor = FastAudioProcessor()
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    processor.process_single_file_fast,
                    Path(file_path),
                    additional_metadata=job_metadata,
                    username=username,
                    user_api_key=user_api_key,
                ),
                timeout=timeout
            )
            # Wrap single result in list to match expected batch format
            result = [result]
        else:
            # Heavy audit processing - SEMANTIC single file only (AssemblyAI + semantic analysis!)
            job_store.update_job(job_id, progress=0.3, stage="processing_heavy_semantic")
            # Use SemanticAudioProcessor for heavy processing with semantic rebuttal detection
            processor = SemanticAudioProcessor()
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    processor.process_single_file_semantic,
                    Path(file_path),
                    additional_metadata=job_metadata,
                    include_debug=False,
                    username=username,
                    user_api_key=user_api_key,
                ),
                timeout=timeout
            )
            # Wrap single result in list to match expected batch format
            result = [result]

        job_store.update_job(job_id, progress=0.9, stage="finalizing")

        # Store result durably
        try:
            if hasattr(result, "to_dict"):
                result_payload = result.to_dict(orient="records")
            else:
                result_payload = result
        except Exception:
            result_payload = result

        job_store.set_job_result(job_id, {"result": result_payload, "metadata": job_metadata})
        job_store.update_job(job_id, status="completed", progress=1.0, stage="completed")
        
        # Also save to dashboard for immediate visibility
        try:
            from lib.dashboard_manager import dashboard_manager
            
            # Convert result to DataFrame for dashboard storage
            import pandas as pd
            if isinstance(result_payload, list) and result_payload:
                df = pd.DataFrame(result_payload)
            else:
                df = pd.DataFrame([result_payload]) if result_payload else pd.DataFrame()
            
            # Save to appropriate dashboard based on audit type
            if audit_type == "heavy":
                dashboard_manager.save_agent_audit_results(df, username)
                logger.info(f"Saved {len(df)} heavy audit results to dashboard for user {username}")
            else:  # lite mode
                dashboard_manager.save_lite_audit_results(df, username)
                logger.info(f"Saved {len(df)} lite audit results to dashboard for user {username}")
            
        except Exception as e:
            logger.warning(f"Failed to save results to dashboard: {e}")
        
        # Release worker pool resources for this user
        try:
            from backend.services.worker_pool_manager import get_worker_pool_manager
            pool_manager = get_worker_pool_manager()
            pool_manager.release_user_workers(username)
            logger.info(f"Released worker pool resources for user {username}")
        except Exception as e:
            logger.warning(f"Could not release worker pool resources: {e}")
        
    except asyncio.TimeoutError:
        logger.error(f"Processing timeout for job {job_id} after {timeout}s")
        try:
            job_store.update_job(job_id, status="failed", error=f"Processing timeout after {timeout}s", stage="timeout")
        except Exception:
            pass
        
        # Release worker pool resources even on timeout
        try:
            from backend.services.worker_pool_manager import get_worker_pool_manager
            pool_manager = get_worker_pool_manager()
            pool_manager.release_user_workers(username)
            logger.info(f"Released worker pool resources for user {username} after timeout")
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Audio processing error: {e}", exc_info=True)
        try:
            job_store.update_job(job_id, status="failed", error=str(e), stage="failed")
        except Exception:
            pass
        
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
    return job_store.get_job(job_id)


def get_job_result(job_id: str) -> Optional[Dict[str, Any]]:
    """Get processing job result."""
    job = job_store.get_job(job_id)
    if not job:
        return None
    if job.get("status") != "completed":
        return None
    result_obj = job.get("result_json")
    if isinstance(result_obj, dict) and "result" in result_obj:
        return result_obj["result"]
    return result_obj

