@echo off
REM VOS Tool - Kill processes on ports 8000 and 8501
REM This script helps free up ports used by VOS Tool

echo ========================================
echo   VOS Tool - Port Cleanup Utility
echo ========================================
echo.

set BACKEND_PORT=8000
set FRONTEND_PORT=8501

echo [INFO] Checking for processes on ports %BACKEND_PORT% and %FRONTEND_PORT%...
echo.

REM Check and kill backend port
netstat -an | findstr ":%BACKEND_PORT% " >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Found process on port %BACKEND_PORT%
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%BACKEND_PORT% " ^| findstr "LISTENING"') do (
        echo [INFO] Killing process PID: %%a
        taskkill /F /PID %%a >nul 2>&1
        if %ERRORLEVEL% EQU 0 (
            echo [SUCCESS] Killed process on port %BACKEND_PORT%
        ) else (
            echo [WARNING] Could not kill process %%a. You may need admin rights.
        )
    )
) else (
    echo [INFO] Port %BACKEND_PORT% is free
)

echo.

REM Check and kill frontend port
netstat -an | findstr ":%FRONTEND_PORT% " >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Found process on port %FRONTEND_PORT%
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%FRONTEND_PORT% " ^| findstr "LISTENING"') do (
        echo [INFO] Killing process PID: %%a
        taskkill /F /PID %%a >nul 2>&1
        if %ERRORLEVEL% EQU 0 (
            echo [SUCCESS] Killed process on port %FRONTEND_PORT%
        ) else (
            echo [WARNING] Could not kill process %%a. You may need admin rights.
        )
    )
) else (
    echo [INFO] Port %FRONTEND_PORT% is free
)

echo.
echo [INFO] Port cleanup complete!
echo.
pause

