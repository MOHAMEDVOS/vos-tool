"""
Configuration constants and utilities.
"""
import sys
import importlib.util
from pathlib import Path

# Import constants from config.constants
from config.constants import CacheConfig, FileConfig, ProcessingConfig, SecurityConfig

# Import everything from root-level config.py to maintain backward compatibility
# This allows "from config import app_settings" to work even though config is a package
_root_dir = Path(__file__).parent.parent
_config_file = _root_dir / "config.py"
if _config_file.exists():
    spec = importlib.util.spec_from_file_location("root_config_module", _config_file)
    root_config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(root_config_module)
    
    # Re-export commonly used items from root config.py
    READYMODE_URL = root_config_module.READYMODE_URL
    USERNAME = root_config_module.USERNAME
    RECORDINGS_ROOT = root_config_module.RECORDINGS_ROOT
    USER_CREDENTIALS = root_config_module.USER_CREDENTIALS
    app_settings = root_config_module.app_settings
    get_user_readymode_credentials = root_config_module.get_user_readymode_credentials
    get_user_daily_limit = root_config_module.get_user_daily_limit
    get_user_app_password = root_config_module.get_user_app_password
    
    # Add to __all__ for explicit exports
    __all__ = [
        'CacheConfig', 'FileConfig', 'ProcessingConfig', 'SecurityConfig',
        'READYMODE_URL', 'USERNAME', 'RECORDINGS_ROOT', 'USER_CREDENTIALS',
        'app_settings', 'get_user_readymode_credentials', 'get_user_daily_limit',
        'get_user_app_password'
    ]
else:
    # Fallback if config.py doesn't exist
    __all__ = ['CacheConfig', 'FileConfig', 'ProcessingConfig', 'SecurityConfig']
