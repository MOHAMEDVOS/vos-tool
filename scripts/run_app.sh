#!/bin/bash

# VOS Tool - Backend and Frontend Launcher
# This script launches both the FastAPI backend and Streamlit frontend

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
echo "  VOS Tool - Starting Backend and Frontend"
echo "========================================"
echo ""

echo "Current directory: $PROJECT_ROOT"
echo ""

# Set default environment variables if not already set
export FORCE_READYMODE=${FORCE_READYMODE:-true}
export DEPLOYMENT_MODE=${DEPLOYMENT_MODE:-enterprise}
export BACKEND_PORT=${BACKEND_PORT:-8000}
export FRONTEND_PORT=${FRONTEND_PORT:-8501}
export BACKEND_URL=${BACKEND_URL:-http://localhost:$BACKEND_PORT}
export BACKEND_HOST=${BACKEND_HOST:-0.0.0.0}

# Check if .env file exists
if [ -f ".env" ]; then
    echo -e "${GREEN}[INFO]${NC} .env file found - environment variables will be loaded"
    # Load .env file
    set -a
    source .env
    set +a
else
    echo -e "${YELLOW}[WARNING]${NC} .env file not found - using default/System environment variables"
    echo -e "${YELLOW}[INFO]${NC} To use PostgreSQL database, create a .env file with database credentials"
fi

echo ""
echo -e "${BLUE}[INFO]${NC} Configuration:"
echo "  - Backend URL: $BACKEND_URL"
echo "  - Backend Port: $BACKEND_PORT"
echo "  - Frontend Port: $FRONTEND_PORT"
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
        # Fallback: try to connect to the port
        timeout 1 bash -c "echo >/dev/tcp/localhost/$port" 2>/dev/null
    fi
}

# Function to kill process on port
kill_port() {
    local port=$1
    local pid=""
    
    if command -v lsof >/dev/null 2>&1; then
        pid=$(lsof -ti :$port)
    elif command -v fuser >/dev/null 2>&1; then
        pid=$(fuser $port/tcp 2>/dev/null | awk '{print $1}')
    elif command -v netstat >/dev/null 2>&1; then
        pid=$(netstat -tlnp 2>/dev/null | grep ":$port " | awk '{print $7}' | cut -d'/' -f1 | head -1)
    fi
    
    if [ -n "$pid" ]; then
        echo -e "${YELLOW}[INFO]${NC} Killing process $pid on port $port..."
        kill -9 $pid 2>/dev/null && echo -e "${GREEN}[INFO]${NC} Killed process on port $port" || echo -e "${RED}[WARNING]${NC} Could not kill process. You may need sudo."
        sleep 2
    fi
}

# Check if ports are available
echo -e "${BLUE}[INFO]${NC} Checking if ports are available..."

# Check backend port
if check_port $BACKEND_PORT; then
    echo -e "${YELLOW}[WARNING]${NC} Port $BACKEND_PORT is already in use!"
    echo -e "${YELLOW}[INFO]${NC} This might be from a previous backend instance."
    echo -e "${YELLOW}[INFO]${NC} Options:"
    echo "  1. Kill the process using port $BACKEND_PORT"
    echo "  2. Use a different port (export BACKEND_PORT=8001)"
    echo "  3. Manually close the application using port $BACKEND_PORT"
    echo ""
    read -p "Kill process on port $BACKEND_PORT? (y/n): " KILL_BACKEND
    if [[ "$KILL_BACKEND" =~ ^[Yy]$ ]]; then
        kill_port $BACKEND_PORT
    else
        echo -e "${YELLOW}[INFO]${NC} Please close the application using port $BACKEND_PORT and try again."
        exit 1
    fi
fi

# Check frontend port
if check_port $FRONTEND_PORT; then
    echo -e "${YELLOW}[WARNING]${NC} Port $FRONTEND_PORT is already in use!"
    echo -e "${YELLOW}[INFO]${NC} This might be from a previous Streamlit instance."
    echo -e "${YELLOW}[INFO]${NC} Options:"
    echo "  1. Kill the process using port $FRONTEND_PORT"
    echo "  2. Use a different port (export FRONTEND_PORT=8502)"
    echo "  3. Manually close the application using port $FRONTEND_PORT"
    echo ""
    read -p "Kill process on port $FRONTEND_PORT? (y/n): " KILL_FRONTEND
    if [[ "$KILL_FRONTEND" =~ ^[Yy]$ ]]; then
        kill_port $FRONTEND_PORT
    else
        echo -e "${YELLOW}[INFO]${NC} Please close the application using port $FRONTEND_PORT and try again."
        exit 1
    fi
fi

echo -e "${GREEN}[INFO]${NC} Ports are available."
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

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}[INFO]${NC} Shutting down services..."
    if [ -n "$BACKEND_PID" ]; then
        echo -e "${YELLOW}[INFO]${NC} Stopping backend (PID: $BACKEND_PID)..."
        kill $BACKEND_PID 2>/dev/null || true
    fi
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup SIGINT SIGTERM EXIT

# Start backend in background
echo -e "${BLUE}[INFO]${NC} Starting Backend API Server on port $BACKEND_PORT..."
echo -e "${BLUE}[INFO]${NC} Backend will be available at: $BACKEND_URL"
echo ""

# Start backend
$PYTHON_CMD -m uvicorn backend.main:app --host $BACKEND_HOST --port $BACKEND_PORT --reload > backend.log 2>&1 &
BACKEND_PID=$!

# Wait for backend to start
echo -e "${BLUE}[INFO]${NC} Waiting for backend to initialize..."
sleep 5

# Check if backend is running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}[ERROR]${NC} Backend failed to start. Check backend.log for details."
    cat backend.log
    exit 1
fi

# Try to verify backend is responding
echo -e "${BLUE}[INFO]${NC} Verifying backend is running..."
for i in {1..10}; do
    if curl -s http://localhost:$BACKEND_PORT/health >/dev/null 2>&1; then
        echo -e "${GREEN}[INFO]${NC} Backend is running and healthy!"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${YELLOW}[WARNING]${NC} Backend may not be fully ready, but continuing..."
    fi
    sleep 1
done

echo ""
echo -e "${BLUE}[INFO]${NC} Starting Frontend (Streamlit) on port $FRONTEND_PORT..."
echo -e "${BLUE}[INFO]${NC} Frontend will be available at: http://localhost:$FRONTEND_PORT"
echo -e "${BLUE}[INFO]${NC} Backend API docs: $BACKEND_URL/docs"
echo ""
echo "========================================"
echo -e "${GREEN}[INFO]${NC} Both services are starting..."
echo -e "${GREEN}[INFO]${NC} Backend is running in background (PID: $BACKEND_PID)"
echo -e "${GREEN}[INFO]${NC} Press Ctrl+C to stop both services"
echo "========================================"
echo ""

# Export BACKEND_URL for frontend
export BACKEND_URL=$BACKEND_URL

# Start frontend in foreground (this will block)
$PYTHON_CMD -m streamlit run app.py --server.port $FRONTEND_PORT --server.address 0.0.0.0

# If we get here, streamlit exited
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo -e "${RED}[ERROR]${NC} Failed to start Streamlit application"
    echo ""
    echo -e "${YELLOW}[TROUBLESHOOTING]${NC}"
    echo "1. Check if port $FRONTEND_PORT is still in use:"
    echo "   lsof -i :$FRONTEND_PORT"
    echo ""
    echo "2. Try using a different port:"
    echo "   export FRONTEND_PORT=8502"
    echo "   ./run_app.sh"
    echo ""
    echo "3. Make sure Streamlit is installed:"
    echo "   pip install streamlit"
    echo ""
    echo "4. Make sure all dependencies are installed:"
    echo "   pip install -r requirements-production.txt"
    echo ""
    exit $EXIT_CODE
fi

