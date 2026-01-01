#!/bin/bash

# VOS Tool - Backend API Server Launcher
# This script launches only the FastAPI backend server

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Change to project root (parent of scripts directory)
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "========================================"
echo "  VOS Backend API - Starting Server"
echo "========================================"
echo ""

echo "Current directory: $PROJECT_ROOT"
echo ""

# Set default environment variables
export BACKEND_PORT=${BACKEND_PORT:-8000}
export BACKEND_HOST=${BACKEND_HOST:-0.0.0.0}

# Check if .env file exists
if [ -f ".env" ]; then
    echo -e "${GREEN}[INFO]${NC} .env file found - environment variables will be loaded"
    set -a
    source .env
    set +a
else
    echo -e "${YELLOW}[WARNING]${NC} .env file not found - using default/System environment variables"
fi

echo ""
echo -e "${BLUE}[INFO]${NC} Starting Backend API Server..."
echo -e "${BLUE}[INFO]${NC} Host: $BACKEND_HOST"
echo -e "${BLUE}[INFO]${NC} Port: $BACKEND_PORT"
echo -e "${BLUE}[INFO]${NC} API will be available at: http://localhost:$BACKEND_PORT"
echo -e "${BLUE}[INFO]${NC} API docs will be available at: http://localhost:$BACKEND_PORT/docs"
echo ""
echo -e "${BLUE}[INFO]${NC} Press Ctrl+C to stop the server"
echo "========================================"
echo ""

# Check if Python is available
if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
    echo -e "${RED}[ERROR]${NC} Python not found. Please install Python 3.8 or higher."
    exit 1
fi

# Determine Python command
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD=python3
else
    PYTHON_CMD=python
fi

# Verify Python version
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
REQUIRED_VERSION="3.8"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}[ERROR]${NC} Python 3.8 or higher is required. Found: $PYTHON_VERSION"
    exit 1
fi

# Start backend
$PYTHON_CMD -m uvicorn backend.main:app --host $BACKEND_HOST --port $BACKEND_PORT --reload

# If uvicorn command fails, show error
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo -e "${RED}[ERROR]${NC} Failed to start backend API server"
    echo -e "${YELLOW}[INFO]${NC} Make sure uvicorn is installed: pip install uvicorn[standard]"
    echo -e "${YELLOW}[INFO]${NC} Make sure backend dependencies are installed: pip install -r requirements-production.txt"
    echo ""
    exit $EXIT_CODE
fi

