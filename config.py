# ==================== config.py (CLEANED) ====================
from pathlib import Path
import os
from dotenv import load_dotenv
load_dotenv()
try:
    from lib.app_settings_manager import app_settings as _persistent_app_settings
except ImportError:
    _persistent_app_settings = None

# ────────────── Base directories ──────────────
BASE_DIR        = Path(__file__).parent
RECORDINGS_DIR  = BASE_DIR / "Recordings"

# Ensure directories exist
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

# ────────────── ReadyMode Dialer URLs ──────────────
READY_MODE_URLS = {
    "default": "https://resva.readymode.com/",
    "resva":    "https://resva.readymode.com/",
    "resva2":   "https://resva2.readymode.com/",
    "resva4":   "https://resva4.readymode.com/",
    "resva5":   "https://resva5.readymode.com/",
    "resva6":   "https://resva6.readymode.com/",
    "resva7":   "https://resva7.readymode.com/",
    "gfcl":     "https://gfcl.readymode.com/",
}

# ────────────── Download directory alias ──────────────
READYMODE_URL = READY_MODE_URLS["default"]

# ────────────── User Authentication ──────────────
# SECURITY: Credentials moved to dashboard system and environment variables
# No hardcoded passwords in source code for security
USER_CREDENTIALS = {
    # Default fallback users - passwords should be set via dashboard
    'auditor1': {'daily_limit': 5000},
    'auditor2': {'daily_limit': 5000},
    'auditor3': {'daily_limit': 5000},
    'auditor4': {'daily_limit': 3000},
    'auditor5': {'daily_limit': 5000},
    'auditor6': {'daily_limit': 5000},
    'auditor7': {'daily_limit': 5000},
    'wosmova': {'daily_limit': 2000},
    'Mohamed Abdo': {'daily_limit': 999999},
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

# ────────────── User Management Functions ──────────────
def get_user_readymode_credentials(username: str):
    """
    Get ReadyMode credentials for a specific user (with secure decryption).
    
    Args:
        username: The app username
        
    Returns:
        tuple: (readymode_username, readymode_password)
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
        return USERNAME, PASSWORD
    
    # If no fallback is set, return None (caller should handle this)
    return None, None

def get_user_app_password(username: str):
    """
    Get app password for a specific user.
    
    Args:
        username: The app username
        
    Returns:
        str: App password or None if user doesn't exist
    """
    # Import user_manager dynamically to avoid circular imports
    try:
        from lib.dashboard_manager import user_manager
        user_data = user_manager.get_user(username)
        if user_data:
            return user_data.get('app_pass')
    except ImportError:
        pass
    
    # Fallback to None if user_manager not available
    return None

def get_user_daily_limit(username: str):
    """
    Get daily download limit for a specific user.
    
    Args:
        username: The app username
        
    Returns:
        int: Daily download limit or 0 if user doesn't exist
    """
    # Import user_manager dynamically to avoid circular imports
    try:
        from lib.dashboard_manager import user_manager
        user_data = user_manager.get_user(username)
        if user_data:
            return user_data.get('daily_limit', 0)
    except ImportError:
        pass
    
    # Fallback to 0 if user_manager not available
    return 0

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
