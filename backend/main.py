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
from backend.api import auth, audio, dashboard, settings as settings_api, readymode, user_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting VOS Backend API...")

    # Initialize database
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    # Preload semantic model for rebuttal detection
    try:
        logger.info("=" * 60)
        logger.info("Preloading semantic model (Railway optimization)...")
        logger.info("=" * 60)

        from models.manager import get_semantic_model
        model, embeddings = get_semantic_model()

        if model is not None:
            logger.info("✅ Semantic model preloaded successfully")
            logger.info(f"✅ Precomputed embeddings for {len(embeddings['metadata']) if embeddings else 0} phrases")
        else:
            logger.warning("⚠️ Semantic model preload failed - using exact matching fallback")
    except Exception as e:
        logger.error(f"❌ Failed to preload semantic model: {e}")
        logger.warning("Application will use exact matching for rebuttal detection")

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

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(audio.router, prefix="/api/audio", tags=["Audio Processing"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["Settings"])
app.include_router(readymode.router, prefix="/api/readymode", tags=["ReadyMode"])
app.include_router(user_data.router, prefix="/api/user", tags=["User Data"])


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
    """Health check endpoint."""
    return {"status": "healthy"}


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

