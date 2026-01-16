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
    # INCREASED for free tier AssemblyAI which can be slow due to rate limits
    REBUTTAL_DETECTION_TIMEOUT_BASE = 300  # 5 minutes base timeout (was 180)
    REBUTTAL_DETECTION_TIMEOUT_PER_MINUTE = 60  # 60 seconds per minute of audio (was 30)
    REBUTTAL_DETECTION_TIMEOUT_MAX = 600  # 10 minutes maximum
    REBUTTAL_DETECTION_TIMEOUT_MIN = 120  # 2 minutes minimum (was 60)
    
    # Transcription timeouts
    # INCREASED for free tier AssemblyAI which can be slow due to rate limits
    TRANSCRIPTION_TIMEOUT_BASE = 300  # 5 minutes base timeout (was 180)
    TRANSCRIPTION_TIMEOUT_PER_MINUTE = 60  # 60 seconds per minute of audio (was 30)
    TRANSCRIPTION_TIMEOUT_MAX = 600  # 10 minutes maximum
    TRANSCRIPTION_TIMEOUT_MIN = 120  # 2 minutes minimum (was 60)


class SecurityConfig:
    """Security-related constants."""
    DEFAULT_SECRET_WARNING = "your-secret-key-change-in-production"
    DEFAULT_JWT_SECRET_WARNING = "your-jwt-secret-change-in-production"
