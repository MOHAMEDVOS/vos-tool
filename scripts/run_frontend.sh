#!/bin/bash

# VOS Tool - Frontend (Streamlit) Launcher
# This script launches only the Streamlit frontend application

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
echo "  VOS Frontend - Starting Application"
echo "========================================"
echo ""

echo "Current directory: $PROJECT_ROOT"
echo ""

# Set default environment variables
export FRONTEND_PORT=${FRONTEND_PORT:-8501}
export BACKEND_URL=${BACKEND_URL:-http://localhost:8000}

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
echo -e "${BLUE}[INFO]${NC} Configuration:"
echo "  - Frontend Port: $FRONTEND_PORT"
echo "  - Backend URL: $BACKEND_URL"
echo ""
echo -e "${YELLOW}[INFO]${NC} Make sure the backend is running at $BACKEND_URL"
echo -e "${YELLOW}[INFO]${NC} If backend is not running, start it with: ./run_backend.sh"
echo ""
echo -e "${BLUE}[INFO]${NC} Starting Streamlit server on port $FRONTEND_PORT..."
echo -e "${BLUE}[INFO]${NC} Frontend will be available at: http://localhost:$FRONTEND_PORT"
echo -e "${BLUE}[INFO]${NC} Press Ctrl+C to stop the server"
echo ""
echo "========================================"
echo ""

# Function to check if port is in use
check_port() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        lsof -i :$port >/dev/null 2>&1
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tuln | grep -q ":$port "
    elif command -v ss >/dev/null 2>&1; then
        ss -tuln | grep -q ":$port "
    else
        timeout 1 bash -c "echo >/dev/tcp/localhost/$port" 2>/dev/null
    fi
}

# Check if port is in use
if check_port $FRONTEND_PORT; then
    echo -e "${YELLOW}[WARNING]${NC} Port $FRONTEND_PORT is already in use!"
    echo -e "${YELLOW}[INFO]${NC} You can:"
    echo "  1. Use a different port: export FRONTEND_PORT=8502"
    echo "  2. Close the application using port $FRONTEND_PORT"
    echo ""
    read -p "Continue anyway? (y/n): " CONTINUE
    if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}[INFO]${NC} Exiting. Please free the port and try again."
        exit 1
    fi
fi

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

# Export BACKEND_URL for the application
export BACKEND_URL=$BACKEND_URL

# Start frontend
$PYTHON_CMD -m streamlit run app.py --server.port $FRONTEND_PORT --server.address 0.0.0.0

# If streamlit command fails, show error
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo -e "${RED}[ERROR]${NC} Failed to start Streamlit application"
    echo -e "${YELLOW}[INFO]${NC} Make sure Streamlit is installed: pip install streamlit"
    echo -e "${YELLOW}[INFO]${NC} Make sure all dependencies are installed: pip install -r requirements-production.txt"
    echo ""
    exit $EXIT_CODE
fi

