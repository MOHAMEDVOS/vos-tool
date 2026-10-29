#!/bin/bash
# Backend Entrypoint Script for Railway

set -e

export DISABLE_TQDM=1
export READYMODE_HEADLESS="${READYMODE_HEADLESS:-false}"

echo "=========================================="
echo "VOS Tool Backend - Railway Startup"
echo "=========================================="

echo ""
echo "[1/2] Checking environment..."
echo "  Python version: $(python --version)"
echo "  Working directory: $(pwd)"
echo "  PORT: ${PORT:-8000}"
echo "  HF_HOME: ${HF_HOME:-not set}"
echo "  READYMODE_HEADLESS: ${READYMODE_HEADLESS} (virtual display enabled)"

echo ""
echo "[2/2] Starting backend server..."
echo "  Command: uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"
echo "  Note: model preload and schema setup run in backend.main lifespan."
echo "=========================================="
echo ""

exec xvfb-run -a uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
