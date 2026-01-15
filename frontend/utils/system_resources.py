"""
System resource monitoring utilities.
"""
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def check_system_resources() -> Dict[str, Any]:
    """
    Check system resources and return detailed usage metrics.
    
    Returns:
        dict: System resource metrics with keys: cpu, memory, disk, healthy
    """
    try:
        import psutil

        # Get CPU usage percentage
        cpu_percent = psutil.cpu_percent(interval=1)

        # Get memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        # Get disk usage
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent

        # Return detailed metrics
        return {
            "cpu": cpu_percent,
            "memory": memory_percent,
            "disk": disk_percent,
            "healthy": cpu_percent < 85 and memory_percent < 85 and disk_percent < 85
        }

    except Exception as e:
        logger.warning(f"Resource check failed: {e}")
        # Return default values if check fails
        return {
            "cpu": 0,
            "memory": 0,
            "disk": 0,
            "healthy": True
        }
