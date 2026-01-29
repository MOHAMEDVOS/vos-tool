#!/bin/bash
# Backend Entrypoint Script for Railway
# Pre-loads models before starting the server

set -e  # Exit on error

echo "=========================================="
echo "VOS Tool Backend - Railway Startup"
echo "=========================================="

# 1. Check environment
echo ""
echo "[1/3] Checking environment..."
echo "  Python version: $(python --version)"
echo "  Working directory: $(pwd)"
echo "  PORT: ${PORT:-8000}"
echo "  HF_HOME: ${HF_HOME:-not set}"

# 2. Preload models (optional, non-blocking)
echo ""
echo "[2/4] Preloading semantic models..."
if [ -f scripts/preload_models.py ]; then
    if python scripts/preload_models.py; then
        echo "✅ Model preload successful"
    else
        echo "⚠️  Model preload failed - app will use exact matching fallback"
    fi
else
    echo "⚠️  preload_models.py not found, skipping preload"
fi

# 3. Run database migrations
echo ""
echo "[3/4] Running database migrations..."
if [ -f scripts/add_feedback_column.py ]; then
    if python scripts/add_feedback_column.py; then
        echo "✅ Database migration successful"
    else
        echo "⚠️  Database migration failed - proceeding anyway"
    fi
else
    echo "⚠️  add_feedback_column.py not found, skipping migration"
fi

# 4. Start the backend server
echo ""
echo "[4/4] Starting backend server..."
echo "  Command: uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"
echo "=========================================="
echo ""

exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
