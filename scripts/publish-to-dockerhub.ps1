# VOS Tool - Docker Hub Publishing Script
# This script builds, tags, and pushes Docker images to Docker Hub

param(
    [Parameter(Mandatory=$true)]
    [string]$DockerHubUsername,
    
    [Parameter(Mandatory=$false)]
    [string]$Version = "latest"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "VOS Tool - Docker Hub Publishing" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Validate Docker is running
Write-Host "Checking Docker..." -ForegroundColor Yellow
$dockerCheck = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}
Write-Host "✓ Docker is running" -ForegroundColor Green

# Check if logged into Docker Hub
Write-Host "Checking Docker Hub login..." -ForegroundColor Yellow
$loginCheck = docker info 2>&1 | Select-String -Pattern "Username"
if (-not $loginCheck) {
    Write-Host "⚠ Not logged into Docker Hub. Please run: docker login" -ForegroundColor Yellow
    Write-Host "Attempting to login..." -ForegroundColor Yellow
    docker login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Docker login failed. Please login manually: docker login" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✓ Logged into Docker Hub" -ForegroundColor Green
}

Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  Docker Hub Username: $DockerHubUsername" -ForegroundColor White
Write-Host "  Version Tag: $Version" -ForegroundColor White
Write-Host "  Backend Image: ${DockerHubUsername}/vos-backend:${Version}" -ForegroundColor White
Write-Host "  Frontend Image: ${DockerHubUsername}/vos-frontend:${Version}" -ForegroundColor White
Write-Host ""

$confirm = Read-Host "Continue with building and pushing? (y/N)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "Cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 1: Building Backend Image" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
docker build -t "${DockerHubUsername}/vos-backend:${Version}" -f backend/Dockerfile .
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Backend build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Backend image built successfully" -ForegroundColor Green

# Also tag as latest if version is not latest
if ($Version -ne "latest") {
    Write-Host "Tagging as latest..." -ForegroundColor Yellow
    docker tag "${DockerHubUsername}/vos-backend:${Version}" "${DockerHubUsername}/vos-backend:latest"
    Write-Host "✓ Tagged as latest" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 2: Building Frontend Image" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
docker build -t "${DockerHubUsername}/vos-frontend:${Version}" -f frontend/Dockerfile .
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Frontend build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Frontend image built successfully" -ForegroundColor Green

# Also tag as latest if version is not latest
if ($Version -ne "latest") {
    Write-Host "Tagging as latest..." -ForegroundColor Yellow
    docker tag "${DockerHubUsername}/vos-frontend:${Version}" "${DockerHubUsername}/vos-frontend:latest"
    Write-Host "✓ Tagged as latest" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 3: Pushing Images to Docker Hub" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "Pushing backend image..." -ForegroundColor Yellow
docker push "${DockerHubUsername}/vos-backend:${Version}"
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Backend push failed!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Backend image pushed successfully" -ForegroundColor Green

if ($Version -ne "latest") {
    Write-Host "Pushing backend:latest..." -ForegroundColor Yellow
    docker push "${DockerHubUsername}/vos-backend:latest"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠ Latest tag push failed (non-critical)" -ForegroundColor Yellow
    } else {
        Write-Host "✓ Backend:latest pushed successfully" -ForegroundColor Green
    }
}

Write-Host "Pushing frontend image..." -ForegroundColor Yellow
docker push "${DockerHubUsername}/vos-frontend:${Version}"
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Frontend push failed!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Frontend image pushed successfully" -ForegroundColor Green

if ($Version -ne "latest") {
    Write-Host "Pushing frontend:latest..." -ForegroundColor Yellow
    docker push "${DockerHubUsername}/vos-frontend:latest"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠ Latest tag push failed (non-critical)" -ForegroundColor Yellow
    } else {
        Write-Host "✓ Frontend:latest pushed successfully" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "✓ SUCCESS! Images published to Docker Hub" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Your images are now available at:" -ForegroundColor Cyan
Write-Host "  https://hub.docker.com/r/${DockerHubUsername}/vos-backend" -ForegroundColor White
Write-Host "  https://hub.docker.com/r/${DockerHubUsername}/vos-frontend" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Update docker-compose.example.yml with your Docker Hub username" -ForegroundColor White
Write-Host "2. Share the repository with users" -ForegroundColor White
Write-Host "3. Users can now pull images with: docker-compose pull" -ForegroundColor White
Write-Host ""
