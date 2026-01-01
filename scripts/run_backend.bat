@echo off
REM VOS Tool - Backend API Server Launcher
REM This script launches only the FastAPI backend server

echo ========================================
echo   VOS Backend API - Starting Server
echo ========================================
echo.

REM Change to project root (parent of scripts directory)
cd /d "%~dp0\.."
echo Current directory: %CD%
echo.

REM Set default environment variables
if "%BACKEND_PORT%"=="" set BACKEND_PORT=8000
if "%BACKEND_HOST%"=="" set BACKEND_HOST=0.0.0.0

REM Check if .env file exists
if exist ".env" (
    echo [INFO] .env file found - environment variables will be loaded
) else (
    echo [WARNING] .env file not found - using default/System environment variables
)

echo.
echo [INFO] Starting Backend API Server...
echo [INFO] Host: %BACKEND_HOST%
echo [INFO] Port: %BACKEND_PORT%
echo [INFO] API will be available at: http://localhost:%BACKEND_PORT%
echo [INFO] API docs will be available at: http://localhost:%BACKEND_PORT%/docs
echo.
echo [INFO] Press Ctrl+C to stop the server
echo ========================================
echo.

REM Check if Python is available
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    where py >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Python not found. Please install Python 3.8 or higher.
        pause
        exit /b 1
    )
    set PYTHON_CMD=py
) else (
    set PYTHON_CMD=python
)

REM Start backend
%PYTHON_CMD% -m uvicorn backend.main:app --host %BACKEND_HOST% --port %BACKEND_PORT% --reload

REM If uvicorn command fails, show error
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to start backend API server
    echo [INFO] Make sure uvicorn is installed: pip install uvicorn[standard]
    echo [INFO] Make sure backend dependencies are installed: pip install -r backend/requirements.txt
    echo.
    pause
    exit /b 1
)

pause

