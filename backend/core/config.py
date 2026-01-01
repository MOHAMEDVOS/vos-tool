"""
Backend configuration settings.
"""

import os
from typing import List, Optional
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    PYDANTIC_V2 = True
except ImportError:
    # Fallback for older pydantic versions
    from pydantic_settings import BaseSettings
    PYDANTIC_V2 = False
from pathlib import Path


if PYDANTIC_V2:
    class Settings(BaseSettings):
        """Application settings."""
        
        # Server settings
        HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
        PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
        DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
        
        # CORS settings
        # Allow multiple origins from environment or default
        _frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8501")
        _cors_origins_env = os.getenv("CORS_ORIGINS", "")
        if _cors_origins_env:
            # Support comma-separated list from environment
            CORS_ORIGINS: List[str] = [origin.strip() for origin in _cors_origins_env.split(",")]
        else:
            CORS_ORIGINS: List[str] = [
                "http://localhost:8501",
                "http://127.0.0.1:8501",
                _frontend_url
            ]
        
        # Security
        SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
        JWT_SECRET: str = os.getenv("JWT_SECRET", "your-jwt-secret-change-in-production")
        JWT_ALGORITHM: str = "HS256"
        JWT_EXPIRATION_HOURS: int = 24
        
        # Database
        DB_TYPE: str = os.getenv("DB_TYPE", "postgresql")
        POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
        POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
        POSTGRES_DB: str = os.getenv("POSTGRES_DB", "vos_tool")
        POSTGRES_USER: str = os.getenv("POSTGRES_USER", "vos_user")
        POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
        
        # File storage
        UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", "Recordings"))
        MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
        
        # ReadyMode
        READYMODE_AVAILABLE: bool = os.getenv("FORCE_READYMODE", "false").lower() == "true"
        
        # AssemblyAI Configuration
        ASSEMBLYAI_API_KEY: str = os.getenv("ASSEMBLYAI_API_KEY", "")
        ASSEMBLYAI_POLLING_INTERVAL: int = int(os.getenv("ASSEMBLYAI_POLLING_INTERVAL", "5"))  # seconds
        ASSEMBLYAI_RETRY_ATTEMPTS: int = int(os.getenv("ASSEMBLYAI_RETRY_ATTEMPTS", "3"))
        ASSEMBLYAI_ENABLE_SPEAKER_DIARIZATION: bool = os.getenv("ASSEMBLYAI_ENABLE_SPEAKER_DIARIZATION", "true").lower() == "true"
        
        # Optional: Allow extra environment variables (for compatibility with existing .env)
        # These are used by other parts of the application but not needed by backend
        READYMODE_USER: Optional[str] = None
        READYMODE_PASSWORD: Optional[str] = None
        ENCRYPTION_KEY: Optional[str] = None
        SESSION_SECRET: Optional[str] = None
        
        model_config = SettingsConfigDict(
            env_file=".env",
            case_sensitive=True,
            extra="ignore"  # Ignore extra environment variables not defined in this class
        )
else:
    class Settings(BaseSettings):
        """Application settings."""
        
        # Server settings
        HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
        PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
        DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
        
        # CORS settings
        # Allow multiple origins from environment or default
        _frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8501")
        _cors_origins_env = os.getenv("CORS_ORIGINS", "")
        if _cors_origins_env:
            # Support comma-separated list from environment
            CORS_ORIGINS: List[str] = [origin.strip() for origin in _cors_origins_env.split(",")]
        else:
            CORS_ORIGINS: List[str] = [
                "http://localhost:8501",
                "http://127.0.0.1:8501",
                _frontend_url
            ]
        
        # Security
        SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
        JWT_SECRET: str = os.getenv("JWT_SECRET", "your-jwt-secret-change-in-production")
        JWT_ALGORITHM: str = "HS256"
        JWT_EXPIRATION_HOURS: int = 24
        
        # Database
        DB_TYPE: str = os.getenv("DB_TYPE", "postgresql")
        POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
        POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
        POSTGRES_DB: str = os.getenv("POSTGRES_DB", "vos_tool")
        POSTGRES_USER: str = os.getenv("POSTGRES_USER", "vos_user")
        POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
        
        # File storage
        UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", "Recordings"))
        MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
        
        # ReadyMode
        READYMODE_AVAILABLE: bool = os.getenv("FORCE_READYMODE", "false").lower() == "true"
        
        # AssemblyAI Configuration
        ASSEMBLYAI_API_KEY: str = os.getenv("ASSEMBLYAI_API_KEY", "")
        ASSEMBLYAI_POLLING_INTERVAL: int = int(os.getenv("ASSEMBLYAI_POLLING_INTERVAL", "5"))  # seconds
        ASSEMBLYAI_RETRY_ATTEMPTS: int = int(os.getenv("ASSEMBLYAI_RETRY_ATTEMPTS", "3"))
        ASSEMBLYAI_ENABLE_SPEAKER_DIARIZATION: bool = os.getenv("ASSEMBLYAI_ENABLE_SPEAKER_DIARIZATION", "true").lower() == "true"
        
        # Optional: Allow extra environment variables (for compatibility with existing .env)
        # These are used by other parts of the application but not needed by backend
        READYMODE_USER: Optional[str] = None
        READYMODE_PASSWORD: Optional[str] = None
        ENCRYPTION_KEY: Optional[str] = None
        SESSION_SECRET: Optional[str] = None
        
        class Config:
            env_file = ".env"
            case_sensitive = True
            extra = "ignore"  # Ignore extra environment variables not defined in this class


settings = Settings()
