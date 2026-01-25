"""
Backend configuration settings.
"""

import os
from typing import List, Optional
from pathlib import Path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import Field, field_validator
    PYDANTIC_V2 = True
except ImportError:
    # Fallback for older pydantic versions
    from pydantic_settings import BaseSettings
    from pydantic import Field, validator
    PYDANTIC_V2 = False

from lib.path_utils import get_upload_dir
from config import FileConfig, ProcessingConfig, SecurityConfig


def _get_cors_origins() -> List[str]:
    """Helper function to get CORS origins from environment or defaults."""
    _frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8501")
    _cors_origins_env = os.getenv("CORS_ORIGINS", "").strip()
    
    if _cors_origins_env:
        # Support comma-separated list from environment
        return [origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()]
    else:
        return [
            "http://localhost:8501",
            "http://127.0.0.1:8501",
            _frontend_url
        ]


# Common settings fields (shared between Pydantic versions)
_COMMON_SETTINGS = {
    # Server settings
    "HOST": os.getenv("BACKEND_HOST", "0.0.0.0"),
    "PORT": int(os.getenv("BACKEND_PORT", "8000")),
    "DEBUG": os.getenv("DEBUG", "false").lower() == "true",
    
    # CORS settings - will be set via validator to avoid Pydantic parsing issues
    
    # Security
    "SECRET_KEY": os.getenv("SECRET_KEY", SecurityConfig.DEFAULT_SECRET_WARNING),
    "JWT_SECRET": os.getenv("JWT_SECRET", SecurityConfig.DEFAULT_JWT_SECRET_WARNING),
    "JWT_ALGORITHM": "HS256",
    "JWT_EXPIRATION_HOURS": 24,
    
    # Database
    "DB_TYPE": os.getenv("DB_TYPE", "postgresql"),
    "POSTGRES_HOST": os.getenv("POSTGRES_HOST", "localhost"),
    "POSTGRES_PORT": os.getenv("POSTGRES_PORT", "5432"),
    "POSTGRES_DB": os.getenv("POSTGRES_DB", "vos_tool"),
    "POSTGRES_USER": os.getenv("POSTGRES_USER", "vos_user"),
    "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
    
    # File storage
    "UPLOAD_DIR": get_upload_dir(),
    "MAX_UPLOAD_SIZE": FileConfig.MAX_UPLOAD_SIZE,
    
    # ReadyMode
    "READYMODE_AVAILABLE": os.getenv("FORCE_READYMODE", "false").lower() == "true",
    
    # AssemblyAI Configuration
    "ASSEMBLYAI_API_KEY": os.getenv("ASSEMBLYAI_API_KEY", ""),
    "ASSEMBLYAI_POLLING_INTERVAL": int(os.getenv("ASSEMBLYAI_POLLING_INTERVAL", "5")),
    "ASSEMBLYAI_RETRY_ATTEMPTS": int(os.getenv("ASSEMBLYAI_RETRY_ATTEMPTS", "3")),
    "ASSEMBLYAI_ENABLE_SPEAKER_DIARIZATION": os.getenv("ASSEMBLYAI_ENABLE_SPEAKER_DIARIZATION", "true").lower() == "true",
    "ASSEMBLYAI_TRANSCRIPTION_TIMEOUT": int(os.getenv("ASSEMBLYAI_TRANSCRIPTION_TIMEOUT", "300")),
    
    # GroqCloud LLM Configuration (for fallback rebuttal evaluation)
    "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
    "GROQ_MODEL": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
    "GROQ_TEMPERATURE": float(os.getenv("GROQ_TEMPERATURE", "0.2")),
    "GROQ_MAX_TOKENS": int(os.getenv("GROQ_MAX_TOKENS", "300")),
    "GROQ_TIMEOUT": int(os.getenv("GROQ_TIMEOUT", "10")),
    
    # LLM Fallback Configuration
    "LLM_FALLBACK_ENABLED": os.getenv("LLM_FALLBACK_ENABLED", "true").lower() == "true",
    "LLM_CONFIDENCE_THRESHOLD": float(os.getenv("LLM_CONFIDENCE_THRESHOLD", "0.70")),
    
        # Processing timeouts
        "PROCESSING_TIMEOUT_SINGLE_FILE": ProcessingConfig.TIMEOUT_SINGLE_FILE,
        "PROCESSING_TIMEOUT_LITE_FILE": ProcessingConfig.TIMEOUT_LITE_FILE,
        
        # Rebuttal detection timeout (can be overridden via env var)
        "ASSEMBLYAI_REBUTTAL_TIMEOUT_SECONDS": int(os.getenv("ASSEMBLYAI_REBUTTAL_TIMEOUT_SECONDS", str(ProcessingConfig.REBUTTAL_DETECTION_TIMEOUT_BASE))),
    
    # Optional: Allow extra environment variables (for compatibility with existing .env)
    "READYMODE_USER": os.getenv("READYMODE_USER"),
    "READYMODE_PASSWORD": os.getenv("READYMODE_PASSWORD"),
    "ENCRYPTION_KEY": os.getenv("ENCRYPTION_KEY"),
    "SESSION_SECRET": os.getenv("SESSION_SECRET"),
}


if PYDANTIC_V2:
    class Settings(BaseSettings):
        """Application settings (Pydantic V2)."""
        
        HOST: str = _COMMON_SETTINGS["HOST"]
        PORT: int = _COMMON_SETTINGS["PORT"]
        DEBUG: bool = _COMMON_SETTINGS["DEBUG"]
        CORS_ORIGINS: List[str] = Field(default_factory=_get_cors_origins)
        SECRET_KEY: str = _COMMON_SETTINGS["SECRET_KEY"]
        JWT_SECRET: str = _COMMON_SETTINGS["JWT_SECRET"]
        JWT_ALGORITHM: str = _COMMON_SETTINGS["JWT_ALGORITHM"]
        JWT_EXPIRATION_HOURS: int = _COMMON_SETTINGS["JWT_EXPIRATION_HOURS"]
        DB_TYPE: str = _COMMON_SETTINGS["DB_TYPE"]
        POSTGRES_HOST: str = _COMMON_SETTINGS["POSTGRES_HOST"]
        POSTGRES_PORT: str = _COMMON_SETTINGS["POSTGRES_PORT"]
        POSTGRES_DB: str = _COMMON_SETTINGS["POSTGRES_DB"]
        POSTGRES_USER: str = _COMMON_SETTINGS["POSTGRES_USER"]
        POSTGRES_PASSWORD: str = _COMMON_SETTINGS["POSTGRES_PASSWORD"]
        UPLOAD_DIR: Path = _COMMON_SETTINGS["UPLOAD_DIR"]
        MAX_UPLOAD_SIZE: int = _COMMON_SETTINGS["MAX_UPLOAD_SIZE"]
        READYMODE_AVAILABLE: bool = _COMMON_SETTINGS["READYMODE_AVAILABLE"]
        ASSEMBLYAI_API_KEY: str = _COMMON_SETTINGS["ASSEMBLYAI_API_KEY"]
        ASSEMBLYAI_POLLING_INTERVAL: int = _COMMON_SETTINGS["ASSEMBLYAI_POLLING_INTERVAL"]
        ASSEMBLYAI_RETRY_ATTEMPTS: int = _COMMON_SETTINGS["ASSEMBLYAI_RETRY_ATTEMPTS"]
        ASSEMBLYAI_ENABLE_SPEAKER_DIARIZATION: bool = _COMMON_SETTINGS["ASSEMBLYAI_ENABLE_SPEAKER_DIARIZATION"]
        ASSEMBLYAI_TRANSCRIPTION_TIMEOUT: int = _COMMON_SETTINGS["ASSEMBLYAI_TRANSCRIPTION_TIMEOUT"]
        GROQ_API_KEY: str = _COMMON_SETTINGS["GROQ_API_KEY"]
        GROQ_MODEL: str = _COMMON_SETTINGS["GROQ_MODEL"]
        GROQ_TEMPERATURE: float = _COMMON_SETTINGS["GROQ_TEMPERATURE"]
        GROQ_MAX_TOKENS: int = _COMMON_SETTINGS["GROQ_MAX_TOKENS"]
        GROQ_TIMEOUT: int = _COMMON_SETTINGS["GROQ_TIMEOUT"]
        LLM_FALLBACK_ENABLED: bool = _COMMON_SETTINGS["LLM_FALLBACK_ENABLED"]
        LLM_CONFIDENCE_THRESHOLD: float = _COMMON_SETTINGS["LLM_CONFIDENCE_THRESHOLD"]
        PROCESSING_TIMEOUT_SINGLE_FILE: int = _COMMON_SETTINGS["PROCESSING_TIMEOUT_SINGLE_FILE"]
        PROCESSING_TIMEOUT_LITE_FILE: int = _COMMON_SETTINGS["PROCESSING_TIMEOUT_LITE_FILE"]
        ASSEMBLYAI_REBUTTAL_TIMEOUT_SECONDS: int = _COMMON_SETTINGS["ASSEMBLYAI_REBUTTAL_TIMEOUT_SECONDS"]
        READYMODE_USER: Optional[str] = _COMMON_SETTINGS["READYMODE_USER"]
        READYMODE_PASSWORD: Optional[str] = _COMMON_SETTINGS["READYMODE_PASSWORD"]
        ENCRYPTION_KEY: Optional[str] = _COMMON_SETTINGS["ENCRYPTION_KEY"]
        SESSION_SECRET: Optional[str] = _COMMON_SETTINGS["SESSION_SECRET"]
        
        @field_validator('CORS_ORIGINS', mode='before')
        @classmethod
        def parse_cors_origins(cls, v):
            """Parse CORS_ORIGINS from environment, handling empty strings."""
            if v is None or (isinstance(v, str) and not v.strip()):
                return _get_cors_origins()
            if isinstance(v, str):
                # Try to parse as comma-separated list
                origins = [origin.strip() for origin in v.split(",") if origin.strip()]
                if origins:
                    return origins
            if isinstance(v, list):
                return v
            return _get_cors_origins()
        
        model_config = SettingsConfigDict(
            env_file=".env",
            case_sensitive=True,
            extra="ignore",
            env_ignore_empty=True  # Ignore empty environment variables
        )
else:
    class Settings(BaseSettings):
        """Application settings (Pydantic V1)."""
        
        HOST: str = _COMMON_SETTINGS["HOST"]
        PORT: int = _COMMON_SETTINGS["PORT"]
        DEBUG: bool = _COMMON_SETTINGS["DEBUG"]
        CORS_ORIGINS: List[str] = Field(default_factory=_get_cors_origins)
        SECRET_KEY: str = _COMMON_SETTINGS["SECRET_KEY"]
        JWT_SECRET: str = _COMMON_SETTINGS["JWT_SECRET"]
        JWT_ALGORITHM: str = _COMMON_SETTINGS["JWT_ALGORITHM"]
        JWT_EXPIRATION_HOURS: int = _COMMON_SETTINGS["JWT_EXPIRATION_HOURS"]
        DB_TYPE: str = _COMMON_SETTINGS["DB_TYPE"]
        POSTGRES_HOST: str = _COMMON_SETTINGS["POSTGRES_HOST"]
        POSTGRES_PORT: str = _COMMON_SETTINGS["POSTGRES_PORT"]
        POSTGRES_DB: str = _COMMON_SETTINGS["POSTGRES_DB"]
        POSTGRES_USER: str = _COMMON_SETTINGS["POSTGRES_USER"]
        POSTGRES_PASSWORD: str = _COMMON_SETTINGS["POSTGRES_PASSWORD"]
        UPLOAD_DIR: Path = _COMMON_SETTINGS["UPLOAD_DIR"]
        MAX_UPLOAD_SIZE: int = _COMMON_SETTINGS["MAX_UPLOAD_SIZE"]
        READYMODE_AVAILABLE: bool = _COMMON_SETTINGS["READYMODE_AVAILABLE"]
        ASSEMBLYAI_API_KEY: str = _COMMON_SETTINGS["ASSEMBLYAI_API_KEY"]
        ASSEMBLYAI_POLLING_INTERVAL: int = _COMMON_SETTINGS["ASSEMBLYAI_POLLING_INTERVAL"]
        ASSEMBLYAI_RETRY_ATTEMPTS: int = _COMMON_SETTINGS["ASSEMBLYAI_RETRY_ATTEMPTS"]
        ASSEMBLYAI_ENABLE_SPEAKER_DIARIZATION: bool = _COMMON_SETTINGS["ASSEMBLYAI_ENABLE_SPEAKER_DIARIZATION"]
        ASSEMBLYAI_TRANSCRIPTION_TIMEOUT: int = _COMMON_SETTINGS["ASSEMBLYAI_TRANSCRIPTION_TIMEOUT"]
        GROQ_API_KEY: str = _COMMON_SETTINGS["GROQ_API_KEY"]
        GROQ_MODEL: str = _COMMON_SETTINGS["GROQ_MODEL"]
        GROQ_TEMPERATURE: float = _COMMON_SETTINGS["GROQ_TEMPERATURE"]
        GROQ_MAX_TOKENS: int = _COMMON_SETTINGS["GROQ_MAX_TOKENS"]
        GROQ_TIMEOUT: int = _COMMON_SETTINGS["GROQ_TIMEOUT"]
        LLM_FALLBACK_ENABLED: bool = _COMMON_SETTINGS["LLM_FALLBACK_ENABLED"]
        LLM_CONFIDENCE_THRESHOLD: float = _COMMON_SETTINGS["LLM_CONFIDENCE_THRESHOLD"]
        PROCESSING_TIMEOUT_SINGLE_FILE: int = _COMMON_SETTINGS["PROCESSING_TIMEOUT_SINGLE_FILE"]
        PROCESSING_TIMEOUT_LITE_FILE: int = _COMMON_SETTINGS["PROCESSING_TIMEOUT_LITE_FILE"]
        ASSEMBLYAI_REBUTTAL_TIMEOUT_SECONDS: int = _COMMON_SETTINGS["ASSEMBLYAI_REBUTTAL_TIMEOUT_SECONDS"]
        READYMODE_USER: Optional[str] = _COMMON_SETTINGS["READYMODE_USER"]
        READYMODE_PASSWORD: Optional[str] = _COMMON_SETTINGS["READYMODE_PASSWORD"]
        ENCRYPTION_KEY: Optional[str] = _COMMON_SETTINGS["ENCRYPTION_KEY"]
        SESSION_SECRET: Optional[str] = _COMMON_SETTINGS["SESSION_SECRET"]
        
        @validator('CORS_ORIGINS', pre=True)
        @classmethod
        def parse_cors_origins(cls, v):
            """Parse CORS_ORIGINS from environment, handling empty strings."""
            if v is None or (isinstance(v, str) and not v.strip()):
                return _get_cors_origins()
            if isinstance(v, str):
                # Try to parse as comma-separated list
                origins = [origin.strip() for origin in v.split(",") if origin.strip()]
                if origins:
                    return origins
            if isinstance(v, list):
                return v
            return _get_cors_origins()
        
        class Config:
            env_file = ".env"
            case_sensitive = True
            extra = "ignore"
            env_file_encoding = 'utf-8'


settings = Settings()
