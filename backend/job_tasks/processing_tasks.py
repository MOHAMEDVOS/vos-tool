import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

from backend.celery_app import celery_app
from backend.services.job_store import update_job, set_job_result, get_job
from processing.batch_engine import batch_analyze_folder_fast

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name='process_audio_batch')
def process_audio_batch_task(
    self, 
    job_id: str, 
    folder_path: str, 
    username: str, 
    user_api_key: Optional[str] = None, 
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Celery task for batch audio processing.
    """
    logger.info(f"Starting batch job {job_id} for folder {folder_path} (User: {username})")
    
    try:
        # Update status to processing
        update_job(job_id, status="processing", progress=0.0, stage="initializing")
        
        # Progress callback to update DB and Celery state
        def progress_callback(current: int, total: int):
            if total > 0:
                progress = (current / total) * 100
            else:
                progress = 0.0
                
            # Update DB with progress
            # Only update DB on significant steps to reduce load
            update_job(job_id, progress=progress, stage=f"processed_{current}_of_{total}")
            
            # Update Celery state
            self.update_state(state='PROGRESS', meta={'current': current, 'total': total, 'progress': progress})

        # Run batch processing using the optimized fast engine
        # This will use async processing internally for AssemblyAI optimization
        df_results = batch_analyze_folder_fast(
            folder_path=folder_path,
            progress_callback=progress_callback,
            additional_metadata=metadata,
            show_all_results=True,  # we want to store everything
            use_async=True,         # Enable the Phase 2 optimization
            username=username,
            user_api_key=user_api_key
        )
        
        # Convert DataFrame to list of dicts for JSON storage
        results = df_results.to_dict(orient='records')
        
        # Store results
        result_payload = {
            'results': results,
            'total_files': len(results),
            'processed_at': datetime.utcnow().isoformat() + "Z"
        }
        
        set_job_result(job_id, result_payload)
        update_job(job_id, status="completed", progress=100.0, stage="completed")
        
        logger.info(f"Job {job_id} completed successfully")
        return {'status': 'success', 'job_id': job_id}
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        update_job(job_id, status="failed", error=str(e))
        raise

