"""
Configuration constants for the application.
"""
from pathlib import Path


class CacheConfig:
    """Cache configuration constants."""
    CSV_TTL = 3600  # 1 hour in seconds


class FileConfig:
    """File handling configuration constants."""
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
    FFMPEG_BIN_PATH = Path(__file__).parent.parent / "ffmpeg" / "bin" / "ffmpeg.exe"
    RECORDINGS_DIR_NAME = "Recordings"


class ProcessingConfig:
    """Processing timeout configuration constants."""
    TIMEOUT_SINGLE_FILE = 600  # 10 minutes in seconds
    TIMEOUT_LITE_FILE = 60  # 1 minute in seconds
    
    # Rebuttal detection timeouts (progressive based on file duration)
    REBUTTAL_DETECTION_TIMEOUT_BASE = 180  # 3 minutes base timeout
    REBUTTAL_DETECTION_TIMEOUT_PER_MINUTE = 30  # 30 seconds per minute of audio
    REBUTTAL_DETECTION_TIMEOUT_MAX = 600  # 10 minutes maximum
    REBUTTAL_DETECTION_TIMEOUT_MIN = 60  # 1 minute minimum
    
    # Transcription timeouts
    TRANSCRIPTION_TIMEOUT_BASE = 180  # 3 minutes base timeout
    TRANSCRIPTION_TIMEOUT_PER_MINUTE = 30  # 30 seconds per minute of audio
    TRANSCRIPTION_TIMEOUT_MAX = 600  # 10 minutes maximum
    TRANSCRIPTION_TIMEOUT_MIN = 60  # 1 minute minimum


class SecurityConfig:
    """Security-related constants."""
    DEFAULT_SECRET_WARNING = "your-secret-key-change-in-production"
    DEFAULT_JWT_SECRET_WARNING = "your-jwt-secret-change-in-production"
