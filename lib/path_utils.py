"""
Shared path utilities for consistent directory resolution across the application.
"""
from pathlib import Path
import os
from typing import Optional


def get_recordings_root() -> Path:
    """
    Get the recordings root directory with fallback logic.
    
    Checks environment variables and common paths in order:
    1. RECORDINGS_ROOT environment variable
    2. ./Recordings (project root) - prioritized on non-Docker systems
    3. /app/Recordings (Docker container path) - only if in Docker
    4. /tmp/Recordings (temporary path)
    
    Returns:
        Path: The recordings root directory (created if needed)
    """
    env_root = os.getenv("RECORDINGS_ROOT")
    candidates = []
    
    if env_root:
        candidates.append(Path(env_root))
    
    # Check if we're in Docker (common indicators)
    is_docker = False
    try:
        if os.path.exists("/.dockerenv"):
            is_docker = True
        elif os.path.exists("/proc/self/cgroup"):
            try:
                with open("/proc/self/cgroup", "r") as f:
                    if "docker" in f.read():
                        is_docker = True
            except Exception:
                pass
        if os.getenv("DOCKER_CONTAINER") == "true":
            is_docker = True
    except Exception:
        # On Windows or other systems, assume not Docker
        is_docker = False
    
    # Prioritize project root on non-Docker systems
    if not is_docker:
        candidates.append(Path(__file__).parent.parent / "Recordings")
    
    # Docker paths (only checked if in Docker or if project root failed)
    candidates.extend([
        Path("/app/Recordings"),
        Path("/tmp/Recordings"),
    ])
    
    # If not in Docker and project root wasn't added yet, add it as fallback
    if is_docker:
        candidates.append(Path(__file__).parent.parent / "Recordings")
    
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            # Test write access
            test_file = candidate / ".write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            return candidate
        except Exception:
            continue
    
    # Final fallback to project root Recordings
    fallback = Path(__file__).parent.parent / "Recordings"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def get_upload_dir() -> Path:
    """
    Get the upload directory path.
    
    Checks UPLOAD_DIR or RECORDINGS_ROOT environment variables,
    falls back to Recordings directory.
    
    Returns:
        Path: The upload directory path
    """
    upload_dir = os.getenv("UPLOAD_DIR") or os.getenv("RECORDINGS_ROOT")
    if upload_dir:
        return Path(upload_dir)
    return get_recordings_root()
