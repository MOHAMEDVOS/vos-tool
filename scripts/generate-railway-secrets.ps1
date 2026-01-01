# PowerShell Script: Generate Security Keys for Railway
# Usage: .\scripts\generate-railway-secrets.ps1

Write-Host "========================================" -ForegroundColor Green
Write-Host "RAILWAY SECURITY KEYS GENERATOR" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Generating SECRET_KEY and JWT_SECRET..." -ForegroundColor Cyan
Write-Host ""

try {
    $secretKey = python -c "import secrets; print(secrets.token_urlsafe(32))"
    $jwtSecret = python -c "import secrets; print(secrets.token_urlsafe(32))"
    
    Write-Host "Keys generated successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Copy these to Railway Backend Service -> Variables:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "SECRET_KEY=$secretKey" -ForegroundColor White
    Write-Host "JWT_SECRET=$jwtSecret" -ForegroundColor White
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "IMPORTANT: Save these keys securely!" -ForegroundColor Yellow
    Write-Host "You'll need them for Railway environment variables." -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Green
    
} catch {
    Write-Host "ERROR: Failed to generate keys. Make sure Python is installed." -ForegroundColor Red
    exit 1
}
