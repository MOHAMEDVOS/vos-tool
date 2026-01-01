@echo off
REM VOS Tool - Backend and Frontend Launcher
REM This script launches both the FastAPI backend and Streamlit frontend

echo ========================================
echo   VOS Tool - Starting Backend and Frontend
echo ========================================
echo.

REM Change to project root (parent of scripts directory)
cd /d "%~dp0\.."
echo Current directory: %CD%
echo.

REM Enable delayed expansion for variables in loops
setlocal enabledelayedexpansion

REM Set default environment variables if not already set
if "%FORCE_READYMODE%"=="" set FORCE_READYMODE=true
if "%DEPLOYMENT_MODE%"=="" set DEPLOYMENT_MODE=enterprise
if "%BACKEND_PORT%"=="" set BACKEND_PORT=8000
if "%FRONTEND_PORT%"=="" set FRONTEND_PORT=8501
if "%BACKEND_URL%"=="" set BACKEND_URL=http://localhost:%BACKEND_PORT%

REM Check if .env file exists
if exist ".env" (
    echo [INFO] .env file found - environment variables will be loaded
) else (
    echo [WARNING] .env file not found - using default/System environment variables
    echo [INFO] To use PostgreSQL database, create a .env file with database credentials
)

echo.
echo [INFO] Configuration:
echo   - Backend URL: %BACKEND_URL%
echo   - Backend Port: %BACKEND_PORT%
echo   - Frontend Port: %FRONTEND_PORT%
echo.

REM Function to check if port is in use
echo [INFO] Checking if ports are available...

REM Check backend port
netstat -an | findstr ":%BACKEND_PORT% " >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [WARNING] Port %BACKEND_PORT% is already in use!
    echo [INFO] This might be from a previous backend instance.
    echo [INFO] Options:
    echo   1. Kill the process using port %BACKEND_PORT%
    echo   2. Use a different port (set BACKEND_PORT=8001)
    echo   3. Manually close the application using port %BACKEND_PORT%
    echo.
    set /p KILL_BACKEND="Kill process on port %BACKEND_PORT%? (y/n): "
    if /i "!KILL_BACKEND!"=="y" (
        echo [INFO] Attempting to kill process on port %BACKEND_PORT%...
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%BACKEND_PORT% " ^| findstr "LISTENING"') do (
            taskkill /F /PID %%a >nul 2>&1
            if !ERRORLEVEL! EQU 0 (
                echo [INFO] Killed process on port %BACKEND_PORT%
            ) else (
                echo [WARNING] Could not kill process. You may need admin rights.
            )
        )
        timeout /t 2 /nobreak >nul
    ) else (
        echo [INFO] Please close the application using port %BACKEND_PORT% and try again.
        pause
        exit /b 1
    )
)

REM Check frontend port
netstat -an | findstr ":%FRONTEND_PORT% " >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [WARNING] Port %FRONTEND_PORT% is already in use!
    echo [INFO] This might be from a previous Streamlit instance.
    echo [INFO] Options:
    echo   1. Kill the process using port %FRONTEND_PORT%
    echo   2. Use a different port (set FRONTEND_PORT=8502)
    echo   3. Manually close the application using port %FRONTEND_PORT%
    echo.
    setlocal enabledelayedexpansion
    set /p KILL_FRONTEND="Kill process on port %FRONTEND_PORT%? (y/n): "
    if /i "!KILL_FRONTEND!"=="y" (
        echo [INFO] Attempting to kill process on port %FRONTEND_PORT%...
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%FRONTEND_PORT% " ^| findstr "LISTENING"') do (
            taskkill /F /PID %%a >nul 2>&1
            if !ERRORLEVEL! EQU 0 (
                echo [INFO] Killed process on port %FRONTEND_PORT%
            ) else (
                echo [WARNING] Could not kill process. You may need admin rights.
            )
        )
        timeout /t 2 /nobreak >nul
    ) else (
        echo [INFO] Please close the application using port %FRONTEND_PORT% and try again.
        pause
        exit /b 1
    )
    endlocal
)

echo [INFO] Ports are available.
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

echo [INFO] Starting Backend API Server on port %BACKEND_PORT%...
echo [INFO] Backend will be available at: %BACKEND_URL%
echo.

REM Start backend in a new window (from project root)
start "VOS Backend API" cmd /k "cd /d %CD% && %PYTHON_CMD% -m uvicorn backend.main:app --host 0.0.0.0 --port %BACKEND_PORT% --reload"

REM Wait a few seconds for backend to start
echo [INFO] Waiting for backend to initialize...
timeout /t 5 /nobreak >nul

REM Check if backend is running (simple check)
echo [INFO] Verifying backend is running...
timeout /t 2 /nobreak >nul

echo.
echo [INFO] Starting Frontend (Streamlit) on port %FRONTEND_PORT%...
echo [INFO] Frontend will be available at: http://localhost:%FRONTEND_PORT%
echo [INFO] Backend API docs: %BACKEND_URL%/docs
echo.
echo ========================================
echo [INFO] Both services are starting...
echo [INFO] Backend is running in a separate window
echo [INFO] Press Ctrl+C to stop the frontend
echo [INFO] Close the backend window to stop the backend
echo ========================================
echo.

REM Set BACKEND_URL for frontend
set BACKEND_URL=%BACKEND_URL%

REM Start frontend in current window
%PYTHON_CMD% -m streamlit run app.py --server.port %FRONTEND_PORT% --server.address 0.0.0.0

REM If streamlit command fails, show error
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to start Streamlit application
    echo.
    echo [TROUBLESHOOTING]
    echo 1. Check if port %FRONTEND_PORT% is still in use:
    echo    netstat -an ^| findstr ":%FRONTEND_PORT% "
    echo.
    echo 2. Try using a different port:
    echo    set FRONTEND_PORT=8502
    echo    run_app.bat
    echo.
    echo 3. Make sure Streamlit is installed:
    echo    pip install streamlit
    echo.
    echo 4. Make sure all dependencies are installed:
    echo    pip install -r requirements.txt
    echo    pip install -r backend/requirements.txt
    echo.
    pause
    exit /b 1
)

pause
