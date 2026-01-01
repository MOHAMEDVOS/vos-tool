# VOS Tool - Database Configuration Setup Script
# This script helps you quickly configure database settings for Docker Hub images

param(
    [Parameter(Mandatory=$false)]
    [string]$PostgresHost = "host.docker.internal",
    
    [Parameter(Mandatory=$false)]
    [string]$PostgresPort = "5432",
    
    [Parameter(Mandatory=$false)]
    [string]$PostgresDb = "vos_tool",
    
    [Parameter(Mandatory=$false)]
    [string]$PostgresUser = "vos_user",
    
    [Parameter(Mandatory=$true)]
    [string]$PostgresPassword
)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "VOS Tool - Database Configuration" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env file exists
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
        Copy-Item ".env.example" ".env"
        Write-Host "✓ .env file created" -ForegroundColor Green
    } else {
        Write-Host "✗ .env.example not found. Please create .env manually." -ForegroundColor Red
        exit 1
    }
}

# Read .env file
$envContent = Get-Content ".env" -Raw

# Update database settings
Write-Host "Updating database configuration..." -ForegroundColor Yellow

# Replace POSTGRES_HOST
$envContent = $envContent -replace "POSTGRES_HOST=.*", "POSTGRES_HOST=$PostgresHost"

# Replace POSTGRES_PORT
$envContent = $envContent -replace "POSTGRES_PORT=.*", "POSTGRES_PORT=$PostgresPort"

# Replace POSTGRES_DB
$envContent = $envContent -replace "POSTGRES_DB=.*", "POSTGRES_DB=$PostgresDb"

# Replace POSTGRES_USER
$envContent = $envContent -replace "POSTGRES_USER=.*", "POSTGRES_USER=$PostgresUser"

# Replace POSTGRES_PASSWORD
$envContent = $envContent -replace "POSTGRES_PASSWORD=.*", "POSTGRES_PASSWORD=$PostgresPassword"

# Write updated content
Set-Content ".env" -Value $envContent -NoNewline

Write-Host "✓ Database configuration updated in .env file" -ForegroundColor Green
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  Host: $PostgresHost" -ForegroundColor White
Write-Host "  Port: $PostgresPort" -ForegroundColor White
Write-Host "  Database: $PostgresDb" -ForegroundColor White
Write-Host "  User: $PostgresUser" -ForegroundColor White
Write-Host "  Password: [HIDDEN]" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Review .env file to ensure all settings are correct" -ForegroundColor White
Write-Host "  2. Run: docker-compose pull" -ForegroundColor White
Write-Host "  3. Run: docker-compose up -d" -ForegroundColor White
Write-Host ""

