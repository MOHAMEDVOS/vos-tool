# ==================== config.py (CLEANED) ====================
from pathlib import Path
import os
from typing import Tuple, Union
from dotenv import load_dotenv
try:
    load_dotenv()
except ValueError as e:
    if "embedded null character" in str(e):
        # .env file is corrupted, skip it and continue
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("⚠️  .env file contains null characters, skipping environment file loading")
        # Continue without .env file
    else:
        raise
try:
    from lib.app_settings_manager import app_settings as _persistent_app_settings
except ImportError:
    _persistent_app_settings = None

# ────────────── Base directories ──────────────
from lib.path_utils import get_recordings_root

BASE_DIR = Path(__file__).parent
RECORDINGS_DIR = BASE_DIR / "Recordings"

# Ensure directories exist
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

# Use shared path utility
RECORDINGS_ROOT = get_recordings_root()

# ────────────── ReadyMode Dialer URLs ──────────────
READY_MODE_URLS = {
    "default": "https://resva.readymode.com/",
    "resva":    "https://resva.readymode.com/",
    "resva2":   "https://resva2.readymode.com/",
    "resva3":   "https://resva3.readymode.com/",
    "resva4":   "https://resva4.readymode.com/",
    "resva5":   "https://resva5.readymode.com/",
    "resva6":   "https://resva6.readymode.com/",
    "resva7":   "https://resva7.readymode.com/",
}

# ────────────── Download directory alias ──────────────
READYMODE_URL = READY_MODE_URLS["default"]

# ────────────── User Authentication ──────────────
# SECURITY: Credentials moved to dashboard system and environment variables
# No hardcoded passwords in source code for security
USER_CREDENTIALS = {
    # Default fallback users - passwords should be set via dashboard
    'Mohamed Abdo': {'daily_limit': 999999},
    'Aya': {'daily_limit': 999999},
    'Auditor1': {'daily_limit': 5000},
}

# ReadyMode credentials - OPTIONAL fallback for system-level operations
# Each user has their own ReadyMode credentials stored securely in the dashboard system.
# These environment variables are only used as a fallback when:
#   - A user doesn't have their own ReadyMode credentials configured
#   - The user_manager is not available
#   - System-level operations need default credentials
#
# If you don't set these, the system will still work - it will just use each user's
# individual credentials (which are set via the Settings dashboard).
USERNAME = os.getenv("READYMODE_USER")  # Optional: System fallback username
PASSWORD = os.getenv("READYMODE_PASSWORD")  # Optional: System fallback password

# Note: No warning if not set - this is intentional since each user has their own credentials


def _looks_like_encrypted_secret(value: str) -> bool:
    """Return true for the encrypted token format produced by security_utils."""
    if not value:
        return False
    stripped = value.strip()
    return len(stripped) > 80 and stripped.startswith(("Z0FB", "gAAAA"))

# ────────────── User Management Functions ──────────────
def _get_user_data(username: str, field: str, fallback=None):
    """
    Generic helper for user data retrieval from dashboard_manager.
    
    Args:
        username: The app username
        field: The field name to retrieve
        fallback: Default value if user or field doesn't exist
        
    Returns:
        The requested field value or fallback
    """
    try:
        from lib.dashboard_manager import user_manager
        user_data = user_manager.get_user(username)
        if user_data:
            return user_data.get(field, fallback)
    except ImportError:
        pass
    return fallback


def get_user_readymode_credentials(username: str) -> Union[Tuple[None, None], Tuple[str, str]]:
    """
    Get ReadyMode credentials for a specific user (with secure decryption).
    
    Args:
        username: The app username
        
    Returns:
        tuple: (readymode_username, readymode_password) or (None, None)
    """
    # Import user_manager dynamically to avoid circular imports
    try:
        from lib.dashboard_manager import user_manager
        # Use secure credential retrieval method
        readymode_user, readymode_pass = user_manager.get_user_readymode_credentials(username)
        if readymode_user and readymode_pass:
            return readymode_user, readymode_pass
    except ImportError:
        pass
    
    # Fallback to system default from environment variables (if set)
    # This is only used if the user doesn't have their own ReadyMode credentials
    if USERNAME and PASSWORD:
        # Also apply decryption to fallback credentials if needed
        if _looks_like_encrypted_secret(PASSWORD):
            try:
                from lib.security_utils import security_manager
                decrypted_pass = security_manager.decrypt_string(PASSWORD)
                if decrypted_pass and decrypted_pass != PASSWORD:
                    return USERNAME, decrypted_pass
            except Exception:
                pass
            return None, None
        return USERNAME, PASSWORD
    
    # If no fallback is set, return None (caller should handle this)
    return None, None


def get_user_app_password(username: str) -> Union[str, None]:
    """
    Get app password for a specific user.
    
    Args:
        username: The app username
        
    Returns:
        str: App password or None if user doesn't exist
    """
    return _get_user_data(username, 'app_pass', None)


def get_user_daily_limit(username: str) -> int:
    """
    Get daily download limit for a specific user.
    
    Args:
        username: The app username
        
    Returns:
        int: Daily download limit or 0 if user doesn't exist
    """
    return _get_user_data(username, 'daily_limit', 0)

# ────────────── Application Settings ──────────────
class AppSettings:
    """
    Centralized settings management for active analysis parameters.
    This singleton ensures all backend functions use the same settings.
    """
    def __init__(self):
        # Late hello detection time (in seconds)
        self.late_hello_time = 5  # Extended to 5 seconds for network delay tolerance
        
        # Voice Activity Detection (VAD) sensitivity settings
        # Lower values = more sensitive (detects fainter speech)
        # Higher values = less sensitive (rejects more noise)
        self.vad_energy_threshold = 600  # RMS energy threshold (optimized)
        self.vad_min_speech_duration = 120  # Minimum speech duration in ms (optimized)
        
        # Sensitivity presets for easy adjustment
        # 'high' = detects faint/unclear speech (more false positives)
        # 'medium' = balanced detection (recommended)
        # 'low' = only clear speech (more false negatives)
        self.vad_sensitivity = 'medium'  # Use balanced detection
        if _persistent_app_settings is not None:
            try:
                self.vad_energy_threshold = _persistent_app_settings.get_vad_threshold()
                self.vad_min_speech_duration = _persistent_app_settings.get_vad_min_duration()
            except Exception:
                pass
        
    def update_from_ui(self, ui_settings):
        """
        Update settings from UI values.
        
        Args:
            ui_settings: Dict of setting_name -> value pairs
        """
        for key, value in ui_settings.items():
            if hasattr(self, key):
                setattr(self, key, value)
                print(f"Updated setting: {key} = {value}")
    
    def apply_vad_sensitivity_preset(self, preset='medium'):
        """
        Apply VAD sensitivity preset.
        
        Args:
            preset: 'high', 'medium', or 'low'
        """
        presets = {
            'high': {
                'vad_energy_threshold': 400,  # Very sensitive - catches faint speech
                'vad_min_speech_duration': 100,  # Shorter minimum duration
                'description': 'High sensitivity - detects faint/unclear speech (may have more false positives)'
            },
            'medium': {
                'vad_energy_threshold': 600,  # Balanced sensitivity
                'vad_min_speech_duration': 120,  # Standard minimum duration (optimized)
                'description': 'Medium sensitivity - balanced detection with noise rejection (recommended)'
            },
            'low': {
                'vad_energy_threshold': 3000,  # Extremely high threshold to reject all but loudest speech
                'vad_min_speech_duration': 300,  # Require very long continuous speech
                'description': 'Very low sensitivity - only clear, loud speech (rejects most noise)'
            }
        }
        
        if preset not in presets:
            print(f"WARNING Invalid preset '{preset}'. Using 'medium'.")
            preset = 'medium'
        
        config = presets[preset]
        self.vad_energy_threshold = config['vad_energy_threshold']
        self.vad_min_speech_duration = config['vad_min_speech_duration']
        self.vad_sensitivity = preset
        
        print(f"SUCCESS VAD Sensitivity: {preset.upper()}")
        print(f"   Energy Threshold: {self.vad_energy_threshold}")
        print(f"   Min Speech Duration: {self.vad_min_speech_duration}ms")
        print(f"   {config['description']}")
    
    def get_vad_parameters(self):
        """Get current VAD parameters as tuple."""
        return self.vad_energy_threshold, self.vad_min_speech_duration

# Global settings instance
app_settings = AppSettings()


# ────────────── Configuration Constants (Merged from config/constants.py) ──────────────

class CacheConfig:
    """Cache configuration constants."""
    CSV_TTL = 3600  # 1 hour in seconds


class FileConfig:
    """File handling configuration constants."""
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
    FFMPEG_BIN_PATH = Path(__file__).parent / "ffmpeg" / "bin" / "ffmpeg.exe"
    RECORDINGS_DIR_NAME = "Recordings"


class ProcessingConfig:
    """Processing timeout configuration constants."""
    TIMEOUT_SINGLE_FILE = int(os.getenv("TIMEOUT_SINGLE_FILE", "600"))
    TIMEOUT_LITE_FILE = int(os.getenv("TIMEOUT_LITE_FILE", "60"))
    
    # Rebuttal detection timeouts (progressive based on file duration)
    # OPTIMIZED: Reduced from 300-600s to 60-90s for faster batch processing
    # Files that timeout are marked as 'No' rebuttal and don't block other files
    REBUTTAL_DETECTION_TIMEOUT_BASE = int(os.getenv("REBUTTAL_DETECTION_TIMEOUT_BASE", "60"))
    REBUTTAL_DETECTION_TIMEOUT_PER_MINUTE = int(os.getenv("REBUTTAL_DETECTION_TIMEOUT_PER_MINUTE", "30"))
    REBUTTAL_DETECTION_TIMEOUT_MAX = int(os.getenv("REBUTTAL_DETECTION_TIMEOUT_MAX", "90"))
    REBUTTAL_DETECTION_TIMEOUT_MIN = int(os.getenv("REBUTTAL_DETECTION_TIMEOUT_MIN", "30"))
    
    # Transcription timeouts
    # INCREASED for free tier AssemblyAI which can be slow due to rate limits
    TRANSCRIPTION_TIMEOUT_BASE = int(os.getenv("TRANSCRIPTION_TIMEOUT_BASE", "300"))
    TRANSCRIPTION_TIMEOUT_PER_MINUTE = int(os.getenv("TRANSCRIPTION_TIMEOUT_PER_MINUTE", "60"))
    TRANSCRIPTION_TIMEOUT_MAX = int(os.getenv("TRANSCRIPTION_TIMEOUT_MAX", "600"))
    TRANSCRIPTION_TIMEOUT_MIN = int(os.getenv("TRANSCRIPTION_TIMEOUT_MIN", "120"))


class SecurityConfig:
    """Security-related constants."""
    DEFAULT_SECRET_WARNING = "your-secret-key-change-in-production"
    DEFAULT_JWT_SECRET_WARNING = "your-jwt-secret-change-in-production"
