#!/usr/bin/env python3
"""
App Settings Manager for VOS Tool
Handles persistent application configuration settings
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class AppSettingsManager:
    """Manages application-wide configuration settings."""
    
    def __init__(self):
        self.settings_dir = Path("dashboard_data/settings")
        self.settings_file = self.settings_dir / "app_settings.json"
        self.settings_dir.mkdir(parents=True, exist_ok=True)
        
        # Default settings
        self.default_settings = {
            "audio": {
                "vad_energy_threshold": 600,
                "vad_min_speech_duration": 120,
                "audio_quality": "medium",
                "processing_timeout": 300
            },
            "detection": {
                "rebuttal_sensitivity": 0.68,
                "intro_detection_mode": "balanced",
                "accent_correction_enabled": True,
                "agent_only_detection": True,
                "semantic_threshold": 0.68
            },
            "user_defaults": {
                "daily_limit": 5000,
                "readymode_access": True,
                "auto_enable": True,
                "default_account_type": "app_readymode"
            },
            "storage": {
                "auto_cleanup_days": 30,
                "max_storage_gb": 10,
                "backup_enabled": True,
                "temp_file_cleanup": True
            },
            "system": {
                "session_timeout_hours": 24,
                "max_concurrent_audits": 3,
                "debug_mode": False,
                "maintenance_mode": False
            }
        }
        
        # Load existing settings or create defaults
        self._load_settings()
    
    def _load_settings(self):
        """Load settings from file or create defaults."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                
                # Merge with defaults to ensure all keys exist
                self.settings = self._merge_settings(self.default_settings, loaded_settings)
                logger.info("Loaded app settings from file")
            else:
                self.settings = self.default_settings.copy()
                self._save_settings()
                logger.info("Created default app settings")
                
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Error parsing settings file: {e}")
            logger.info("Using default settings due to corrupted file")
            self.settings = self.default_settings.copy()
            # Try to backup corrupted file
            try:
                backup_path = self.settings_file.with_suffix('.json.backup')
                self.settings_file.rename(backup_path)
                logger.info(f"Backed up corrupted settings to {backup_path}")
            except Exception:
                pass
        except (OSError, IOError) as e:
            logger.error(f"Error accessing settings file: {e}")
            self.settings = self.default_settings.copy()
        except Exception as e:
            logger.error(f"Unexpected error loading settings: {e}")
            self.settings = self.default_settings.copy()
    
    def _merge_settings(self, defaults: Dict, loaded: Dict) -> Dict:
        """Recursively merge loaded settings with defaults."""
        result = defaults.copy()
        
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_settings(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _save_settings(self):
        """Save current settings to file."""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2)
            logger.info("Saved app settings to file")
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
    
    def get_setting(self, category: str, key: str, default=None):
        """Get a specific setting value."""
        try:
            return self.settings.get(category, {}).get(key, default)
        except (KeyError, TypeError, AttributeError):
            logger.debug(f"Error getting setting {category}.{key}, using default")
            return default
    
    def set_setting(self, category: str, key: str, value: Any):
        """Set a specific setting value."""
        try:
            # Basic validation
            if not isinstance(category, str) or not isinstance(key, str):
                logger.error(f"Category and key must be strings: {category}, {key}")
                return False
            
            # Validate JSON serializable
            try:
                json.dumps(value)
            except (TypeError, ValueError) as e:
                logger.error(f"Value not JSON serializable for {category}.{key}: {e}")
                return False
            
            if category not in self.settings:
                self.settings[category] = {}
            
            self.settings[category][key] = value
            self._save_settings()
            logger.info(f"Updated setting: {category}.{key} = {value}")
            return True
        except Exception as e:
            logger.error(f"Error setting {category}.{key}: {e}")
            return False
    
    def get_category(self, category: str) -> Dict[str, Any]:
        """Get all settings for a category."""
        return self.settings.get(category, {}).copy()
    
    def update_category(self, category: str, updates: Dict[str, Any]):
        """Update multiple settings in a category."""
        try:
            if category not in self.settings:
                self.settings[category] = {}
            
            self.settings[category].update(updates)
            self._save_settings()
            logger.info(f"Updated {category} settings: {list(updates.keys())}")
            return True
        except Exception as e:
            logger.error(f"Error updating {category}: {e}")
            return False
    
    def reset_to_defaults(self, category: Optional[str] = None):
        """Reset settings to defaults."""
        try:
            if category:
                if category in self.default_settings:
                    self.settings[category] = self.default_settings[category].copy()
                    logger.info(f"Reset {category} to defaults")
            else:
                self.settings = self.default_settings.copy()
                logger.info("Reset all settings to defaults")
            
            self._save_settings()
            return True
        except Exception as e:
            logger.error(f"Error resetting settings: {e}")
            return False
    
    def export_settings(self) -> str:
        """Export settings as JSON string."""
        try:
            return json.dumps(self.settings, indent=2)
        except Exception as e:
            logger.error(f"Error exporting settings: {e}")
            return "{}"
    
    def import_settings(self, settings_json: str) -> bool:
        """Import settings from JSON string."""
        try:
            imported = json.loads(settings_json)
            self.settings = self._merge_settings(self.default_settings, imported)
            self._save_settings()
            logger.info("Imported settings successfully")
            return True
        except Exception as e:
            logger.error(f"Error importing settings: {e}")
            return False
    
    # Convenience methods for common settings
    def get_vad_threshold(self) -> int:
        """Get VAD energy threshold."""
        return self.get_setting("audio", "vad_energy_threshold", 600)
    
    def get_vad_min_duration(self) -> int:
        """Get VAD minimum speech duration."""
        return self.get_setting("audio", "vad_min_speech_duration", 120)
    
    def get_rebuttal_sensitivity(self) -> float:
        """Get rebuttal detection sensitivity."""
        return self.get_setting("detection", "rebuttal_sensitivity", 0.68)
    
    def get_semantic_threshold(self) -> float:
        """Get semantic similarity threshold for rebuttal detection."""
        return self.get_setting("detection", "semantic_threshold", 0.68)
    
    def get_default_daily_limit(self) -> int:
        """Get default daily limit for new users."""
        return self.get_setting("user_defaults", "daily_limit", 5000)
    
    def is_accent_correction_enabled(self) -> bool:
        """Check if accent correction is enabled."""
        return self.get_setting("detection", "accent_correction_enabled", True)
    
    def is_maintenance_mode(self) -> bool:
        """Check if maintenance mode is enabled."""
        return self.get_setting("system", "maintenance_mode", False)

# Global settings manager instance
app_settings = AppSettingsManager()

def get_app_settings() -> AppSettingsManager:
    """Get the global app settings manager."""
    return app_settings
