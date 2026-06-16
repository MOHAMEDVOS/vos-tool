"""
FastAPI Backend Application for VOS (Voice Observation System)
Main entry point for the REST API backend service.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to access lib modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Any
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from backend.core.config import settings
from backend.core.database import init_db

# Configure logging
from lib.logging_config import setup_backend_logging
setup_backend_logging()
logger = logging.getLogger(__name__)

# Import routers (database initialization happens in lifespan)
from backend.api import auth, audio, dashboard, settings as settings_api, readymode, readymode_users, user_data, jobs, phrases, quota, sharing, system as system_api, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("=" * 60)
    logger.info("Starting VOS Backend API...")
    logger.info("=" * 60)

    # CRITICAL: Preload semantic models FIRST (before accepting requests)
    # This prevents the first user from triggering a 30-second blocking load
    logger.info("🔄 [STARTUP] Preloading AI models...")
    try:
        from models.manager import get_semantic_model
        model, embeddings = get_semantic_model()
        if model is not None:
            count = len(embeddings['metadata']) if embeddings else 0
            logger.info(f"✅ [STARTUP] Semantic model ready ({count} phrases preloaded)")
        else:
            logger.warning("⚠️  [STARTUP] Semantic model failed - using exact matching fallback")
    except Exception as e:
        logger.error(f"❌ [STARTUP] Failed to preload semantic model: {e}")
        logger.warning("⚠️  [STARTUP] Continuing with exact matching only (degraded mode)")

    # Initialize database (after models to fail fast if models broken)
    logger.info("🔄 [STARTUP] Initializing database connection pool...")
    try:
        init_db()
        logger.info("✅ [STARTUP] Database initialized successfully")
        
        # Phrase backup restore script removed (data is now persisted in PostgreSQL)
            
        try:
            from lib.phrase_learning import PhraseLearningManager
            phrase_manager = PhraseLearningManager()
            logger.info("✅ [STARTUP] Phrase learning manager initialized")
        except Exception as e:
            logger.error(f"❌ [STARTUP] Failed to initialize PhraseLearningManager: {e}")
            
    except Exception as e:
        logger.error(f"❌ [STARTUP] Database initialization failed: {e}")

    logger.info("=" * 60)
    logger.info("✅ VOS Backend API Ready - Accepting Requests")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("Shutting down VOS Backend API...")


# Create FastAPI application
app = FastAPI(
    title="VOS Backend API",
    description="Voice Observation System - Backend REST API",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# TEMPORARILY DISABLED: Rate limiting (slowapi not installing on Railway due to cache issues)
# from backend.core.rate_limit import limiter, rate_limit_exceeded_handler  
# from slowapi.errors import RateLimitExceeded

# app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
# logger.info("✅ Rate limiting enabled")
logger.info("⚠️  Rate limiting DISABLED (temporary workaround)")

# Include routers
from backend.api import health as health_api

app.include_router(health_api.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(audio.router, prefix="/api/audio", tags=["Audio Processing"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["Settings"])
app.include_router(readymode.router, prefix="/api/readymode", tags=["ReadyMode"])
app.include_router(readymode_users.router, prefix="/api/readymode-users", tags=["ReadyMode Users"])
app.include_router(user_data.router, prefix="/api/user", tags=["User Data"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(phrases.router, prefix="/api/phrases", tags=["Phrases"])

app.include_router(quota.router, prefix="/api/quota", tags=["Quota"])
app.include_router(sharing.router, prefix="/api/sharing", tags=["Sharing"])
app.include_router(system_api.router, prefix="/api/system", tags=["System"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "VOS Backend API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    from lib.database import get_db_manager
    
    db = get_db_manager()
    db_healthy = db.test_connection() if db else False
    
    return {
        "status": "healthy" if db_healthy else "degraded",
        "database": "connected" if db_healthy else "disconnected"
    }


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with resource metrics."""
    import threading
    import psutil
    from lib.database import get_db_manager
    from models.manager import _SEMANTIC_MODEL
    
    db = get_db_manager()
    pool_stats = db.get_pool_stats() if db else {}
    
    return {
        "status": "healthy",
        "timestamp": __import__('datetime').datetime.now().isoformat(),
        "database": {
            "connected": db.test_connection() if db else False,
            "pool_max": pool_stats.get('max_connections', 0),
            "pool_used": pool_stats.get('used_connections', 0),
            "pool_available": pool_stats.get('available_connections', 0),
            "pool_usage_percent": round(pool_stats.get('usage_percent', 0), 2),
            "healthy": pool_stats.get('usage_percent', 0) < 80
        },
        "threading": {
            "active_threads": threading.active_count(),
            "thread_names": [t.name for t in threading.enumerate()[:10]]  # First 10
        },
        "memory": {
            "used_mb": round(psutil.Process().memory_info().rss / 1024 / 1024, 2),
            "percent": psutil.Process().memory_percent()
        },
        "models": {
            "semantic_loaded": _SEMANTIC_MODEL is not None
        }
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

