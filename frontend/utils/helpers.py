"""
General helper utilities for the frontend.
"""
from datetime import datetime


def generate_timestamped_folder_name(base_name: str = "All users") -> str:
    """
    Generate a unique folder name with timestamp to avoid duplicates.

    Args:
        base_name: Base name for the folder (default: "All users")

    Returns:
        Folder name with timestamp: "All users-2025-10-26_14-30-45"
    """
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    return f"{base_name}-{timestamp}"
