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
echo "[2/3] Preloading semantic models..."
if python scripts/preload_models.py; then
    echo "✅ Model preload successful"
else
    echo "⚠️  Model preload failed - app will use exact matching fallback"
    echo "    This is not critical, the app will still work"
fi

# 3. Start the backend server
echo ""
echo "[3/3] Starting backend server..."
echo "  Command: uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"
echo "=========================================="
echo ""

exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
