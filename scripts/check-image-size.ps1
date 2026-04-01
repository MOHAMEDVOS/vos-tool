# Quick Docker Image Size Checker
# Usage: .\check-image-size.ps1 [backend|frontend]

param(
    [string]$Service = "backend"
)

Write-Host "========================================" -ForegroundColor Green
Write-Host "Docker Image Size Checker" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

$dockerfile = if ($Service -eq "backend") { "backend/Dockerfile" } else { "frontend/Dockerfile" }
$imageName = "vos-$Service-size-test"

Write-Host "Building image: $imageName" -ForegroundColor Cyan
Write-Host "Using Dockerfile: $dockerfile" -ForegroundColor Cyan
Write-Host ""

# Build the image
Write-Host "Building Docker image..." -ForegroundColor Yellow
docker build -f $dockerfile -t $imageName . 2>&1 | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Host "Build successful!" -ForegroundColor Green
    Write-Host ""
    
    # Show image size
    Write-Host "Image Size Information:" -ForegroundColor Cyan
    docker images $imageName --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
    Write-Host ""
    
    # Get detailed size
    $size = docker image inspect $imageName --format='{{.Size}}'
    $sizeGB = [math]::Round([int64]$size / 1GB, 2)
    $sizeMB = [math]::Round([int64]$size / 1MB, 2)
    
    Write-Host "Detailed Size:" -ForegroundColor Cyan
    Write-Host "  Bytes: $size" -ForegroundColor White
    Write-Host "  MB: $sizeMB MB" -ForegroundColor White
    $sizeGBStr = "$sizeGB GB"
    Write-Host "  GB: $sizeGBStr" -ForegroundColor White
    Write-Host ""
    
    if ($sizeGB -gt 4.0) {
        $warningMsg = "WARNING: Image size ($sizeGBStr) exceeds Railway's 4.0 GB limit!"
        Write-Host $warningMsg -ForegroundColor Red
    } else {
        $successMsg = "Image size ($sizeGBStr) is within Railway's 4.0 GB limit"
        Write-Host $successMsg -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "To clean up, run: docker rmi $imageName" -ForegroundColor Yellow
} else {
    Write-Host "Build failed!" -ForegroundColor Red
    Write-Host "Check the error messages above." -ForegroundColor Red
}
