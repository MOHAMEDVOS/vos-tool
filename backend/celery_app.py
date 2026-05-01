"""
Celery application configuration for VOS Backend.
This handles async job processing.
"""

import os
import sys
from pathlib import Path

from celery import Celery

# Add parent directory to path.
sys.path.insert(0, str(Path(__file__).parent.parent))

# Get Redis URL from environment.
# Priority: REDIS_URL (public), then REDIS_PRIVATE_URL (internal/recommended),
# then REDIS_PUBLIC_URL for Railway compatibility.
redis_url = (
    os.getenv("REDIS_URL")
    or os.getenv("REDIS_PRIVATE_URL")
    or os.getenv("REDIS_PUBLIC_URL")
    or "redis://localhost:6379/0"
)

if not os.getenv("REDIS_URL") and not os.getenv("REDIS_PRIVATE_URL"):
    print("WARNING: REDIS_URL/REDIS_PRIVATE_URL not found in environment.")
    print("   Worker will attempt to connect to localhost:6379 (likely to fail on Railway).")
else:
    try:
        from urllib.parse import urlparse

        parsed = urlparse(redis_url)
        print(f"Celery using broker at: {parsed.hostname}")
    except Exception:
        print("Celery broker configured from environment variables")

# Create Celery app.
celery_app = Celery(
    "vos_backend",
    broker=redis_url,
    backend=redis_url,
)

# Configure Celery.
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3300,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    worker_disable_rate_limits=True,
    result_expires=86400,
    result_extended=True,
)

# Auto-discover tasks in backend/job_tasks.py.
celery_app.autodiscover_tasks(["backend.job_tasks"])

print("Celery app configured successfully")
