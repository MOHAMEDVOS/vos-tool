#!/bin/bash
# Backend Entrypoint Script for Railway
# Starts server immediately - model preloading happens asynchronously in main.py

set -e  # Exit on error

echo "=========================================="
echo "VOS Tool Backend - Railway Startup"
echo "=========================================="

# 1. Check environment
echo ""
echo "[1/2] Checking environment..."
echo "  Python version: $(python --version)"
echo "  Working directory: $(pwd)"
echo "  PORT: ${PORT:-8000}"
echo "  HF_HOME: ${HF_HOME:-not set}"

# 2. Start the backend server immediately
# Model preloading happens asynchronously in backend/main.py lifespan event
echo ""
echo "[2/2] Starting backend server..."
echo "  Command: uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"
echo "  Note: Semantic models will load in background (see main.py lifespan)"
echo "=========================================="
echo ""

exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
