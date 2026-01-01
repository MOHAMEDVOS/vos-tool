@echo off
REM VOS Tool - Cleanup Unused Packages
REM Removes unused packages to free up disk space

echo ========================================
echo   VOS Tool - Cleaning Up Unused Packages
echo ========================================
echo.

echo [INFO] This will remove the following unused packages:
echo   - vosk (replaced by AssemblyAI)
echo   - openai-whisper (replaced by AssemblyAI, saves ~5-10GB)
echo   - jellyfish (not used in codebase)
echo.

set /p CONFIRM="Continue with cleanup? (y/n): "
if /i not "%CONFIRM%"=="y" (
    echo [INFO] Cleanup cancelled.
    pause
    exit /b 0
)

echo.
echo [INFO] Checking installed packages...
echo.

REM Check if packages are installed
pip show vosk >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Found: vosk
    set VOSK_FOUND=1
) else (
    echo [INFO] Not found: vosk
    set VOSK_FOUND=0
)

pip show openai-whisper >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Found: openai-whisper
    set WHISPER_FOUND=1
) else (
    echo [INFO] Not found: openai-whisper
    set WHISPER_FOUND=0
)

pip show jellyfish >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Found: jellyfish
    set JELLYFISH_FOUND=1
) else (
    echo [INFO] Not found: jellyfish
    set JELLYFISH_FOUND=0
)

echo.
echo [INFO] Starting cleanup...
echo.

if %VOSK_FOUND% EQU 1 (
    echo [INFO] Uninstalling vosk...
    pip uninstall -y vosk
    if %ERRORLEVEL% EQU 0 (
        echo [SUCCESS] vosk uninstalled
    ) else (
        echo [WARNING] Failed to uninstall vosk
    )
)

if %WHISPER_FOUND% EQU 1 (
    echo [INFO] Uninstalling openai-whisper (this may take a moment)...
    pip uninstall -y openai-whisper
    if %ERRORLEVEL% EQU 0 (
        echo [SUCCESS] openai-whisper uninstalled (~5-10GB freed)
    ) else (
        echo [WARNING] Failed to uninstall openai-whisper
    )
)

if %JELLYFISH_FOUND% EQU 1 (
    echo [INFO] Uninstalling jellyfish...
    pip uninstall -y jellyfish
    if %ERRORLEVEL% EQU 0 (
        echo [SUCCESS] jellyfish uninstalled
    ) else (
        echo [WARNING] Failed to uninstall jellyfish
    )
)

echo.
echo ========================================
echo [INFO] Cleanup completed!
echo ========================================
echo.
echo [INFO] Estimated space freed:
echo   - vosk: ~100MB
echo   - openai-whisper: ~5-10GB (models)
echo   - jellyfish: ~1MB
echo.
echo [INFO] You can verify with: pip list
echo.

pause

