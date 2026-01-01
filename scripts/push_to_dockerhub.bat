@echo off
REM Docker Hub Push Script for VOS Tool (Windows)
REM This script builds, tags, and pushes Docker images to Docker Hub
REM
REM Usage:
REM   scripts\push_to_dockerhub.bat <dockerhub_username> [version_tag]
REM
REM Example:
REM   scripts\push_to_dockerhub.bat myusername
REM   scripts\push_to_dockerhub.bat myusername v1.0.0

setlocal enabledelayedexpansion

REM Check if Docker is installed
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Docker is not installed or not in PATH
    exit /b 1
)

REM Check if Docker daemon is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Docker daemon is not running
    exit /b 1
)

REM Get Docker Hub username from argument
if "%~1"=="" (
    echo Error: Docker Hub username is required
    echo Usage: %~nx0 ^<dockerhub_username^> [version_tag]
    echo Example: %~nx0 myusername
    echo Example: %~nx0 myusername v1.0.0
    exit /b 1
)

set DOCKERHUB_USERNAME=%~1
set VERSION_TAG=%~2
if "!VERSION_TAG!"=="" set VERSION_TAG=latest

echo ========================================
echo VOS Tool - Docker Hub Push Script
echo ========================================
echo.
echo Docker Hub Username: %DOCKERHUB_USERNAME%
echo Version Tag: %VERSION_TAG%
echo.

REM Get the project root directory (parent of scripts/)
cd /d "%~dp0\.."
set PROJECT_ROOT=%CD%

REM Image names
set BACKEND_IMAGE=%DOCKERHUB_USERNAME%/vos-backend
set FRONTEND_IMAGE=%DOCKERHUB_USERNAME%/vos-frontend

echo Step 1: Building Backend Image...
docker build -t "%BACKEND_IMAGE%:%VERSION_TAG%" -t "%BACKEND_IMAGE%:latest" -f backend\Dockerfile .
if %errorlevel% neq 0 (
    echo Error: Backend image build failed
    exit /b 1
)
echo [OK] Backend image built successfully
echo.

echo Step 2: Building Frontend Image...
docker build -t "%FRONTEND_IMAGE%:%VERSION_TAG%" -t "%FRONTEND_IMAGE%:latest" -f frontend\Dockerfile .
if %errorlevel% neq 0 (
    echo Error: Frontend image build failed
    exit /b 1
)
echo [OK] Frontend image built successfully
echo.

echo Step 3: Logging into Docker Hub...
echo Please enter your Docker Hub credentials:
docker login
if %errorlevel% neq 0 (
    echo Error: Docker Hub login failed
    exit /b 1
)
echo [OK] Successfully logged into Docker Hub
echo.

echo Step 4: Pushing Backend Image...
docker push "%BACKEND_IMAGE%:%VERSION_TAG%"
docker push "%BACKEND_IMAGE%:latest"
if %errorlevel% neq 0 (
    echo Error: Backend image push failed
    exit /b 1
)
echo [OK] Backend image pushed successfully
echo.

echo Step 5: Pushing Frontend Image...
docker push "%FRONTEND_IMAGE%:%VERSION_TAG%"
docker push "%FRONTEND_IMAGE%:latest"
if %errorlevel% neq 0 (
    echo Error: Frontend image push failed
    exit /b 1
)
echo [OK] Frontend image pushed successfully
echo.

echo ========================================
echo [OK] All images pushed successfully!
echo ========================================
echo.
echo Images available at:
echo   - %BACKEND_IMAGE%:%VERSION_TAG%
echo   - %BACKEND_IMAGE%:latest
echo   - %FRONTEND_IMAGE%:%VERSION_TAG%
echo   - %FRONTEND_IMAGE%:latest
echo.
echo To pull these images on another machine:
echo   docker pull %BACKEND_IMAGE%:latest
echo   docker pull %FRONTEND_IMAGE%:latest
echo.
echo See DOCKER_HUB_DEPLOYMENT.md for deployment instructions.

endlocal

