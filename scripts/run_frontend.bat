@echo off
REM VOS Tool - Frontend (Streamlit) Launcher
REM This script launches only the Streamlit frontend application

echo ========================================
echo   VOS Frontend - Starting Application
echo ========================================
echo.

REM Change to project root (parent of scripts directory)
cd /d "%~dp0\.."
echo Current directory: %CD%
echo.

REM Enable delayed expansion for variables in loops
setlocal enabledelayedexpansion

REM Set default environment variables
if "%FRONTEND_PORT%"=="" set FRONTEND_PORT=8501
if "%BACKEND_URL%"=="" set BACKEND_URL=http://localhost:8000

REM Check if .env file exists
if exist ".env" (
    echo [INFO] .env file found - environment variables will be loaded
) else (
    echo [WARNING] .env file not found - using default/System environment variables
)

echo.
echo [INFO] Configuration:
echo   - Frontend Port: %FRONTEND_PORT%
echo   - Backend URL: %BACKEND_URL%
echo.
echo [INFO] Make sure the backend is running at %BACKEND_URL%
echo [INFO] If backend is not running, start it with: run_backend.bat
echo.
echo [INFO] Starting Streamlit server on port %FRONTEND_PORT%...
echo [INFO] Frontend will be available at: http://localhost:%FRONTEND_PORT%
echo [INFO] Press Ctrl+C to stop the server
echo.
echo ========================================
echo.

REM Set BACKEND_URL for the application
set BACKEND_URL=%BACKEND_URL%

REM Check if port is in use
netstat -an | findstr ":%FRONTEND_PORT% " >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [WARNING] Port %FRONTEND_PORT% is already in use!
    echo [INFO] You can:
    echo   1. Run kill_ports.bat to free the port
    echo   2. Use a different port: set FRONTEND_PORT=8502
    echo   3. Close the application using port %FRONTEND_PORT%
    echo.
    set /p CONTINUE="Continue anyway? (y/n): "
    if /i not "!CONTINUE!"=="y" (
        echo [INFO] Exiting. Please free the port and try again.
        pause
        exit /b 1
    )
)

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

REM Start frontend
%PYTHON_CMD% -m streamlit run app.py --server.port %FRONTEND_PORT% --server.address 0.0.0.0

REM If streamlit command fails, show error
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to start Streamlit application
    echo [INFO] Make sure Streamlit is installed: pip install streamlit
    echo [INFO] Make sure all dependencies are installed: pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

pause

