"""
Celery application configuration for VOS Backend.
This handles async job processing.
"""

from celery import Celery
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Get Redis URL from environment (default to localhost)
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery app
celery_app = Celery(
    'vos_backend',
    broker=redis_url,          # Where to send jobs
    backend=redis_url          # Where to store results
)

# Configure Celery
celery_app.conf.update(
    # Serialization (how data is stored)
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Timezone
    timezone='UTC',
    enable_utc=True,
    
    # Task settings
    task_track_started=True,           # Track when task starts
    task_time_limit=3600,              # Max 1 hour per task
    task_soft_time_limit=3300,         # Warning at 55 minutes
    
    # Worker settings
    worker_prefetch_multiplier=1,      # Fair distribution (one task at a time)
    worker_max_tasks_per_child=50,     # Restart worker every 50 tasks (prevent memory leaks)
    worker_disable_rate_limits=True,   # No rate limits (we handle this in API)
    
    # Result backend settings
    result_expires=86400,               # Keep results for 24 hours
    result_extended=True,               # Store full task info
)

# Auto-discover tasks in backend/tasks/ folder
celery_app.autodiscover_tasks(['backend.job_tasks'])

print("✅ Celery app configured successfully")
