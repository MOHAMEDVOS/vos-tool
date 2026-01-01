@echo off
echo ========================================
echo VOS Tool - Cloudflare Tunnel (NO DOMAIN)
echo ========================================
echo.

REM Change to project root directory
cd /d "%~dp0.."

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Starting Streamlit app...
start "VOS Tool" python -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0

echo.
echo Waiting for app to start (10 seconds)...
timeout /t 10 /nobreak > nul

echo.
echo ========================================
echo 🚀 STARTING CLOUDFLARE TUNNEL...
echo ========================================
echo.
echo This will create a FREE temporary URL!
echo Example: https://abc123.trycloudflare.com
echo.
echo Press Ctrl+C to stop the tunnel anytime
echo.

cloudflared tunnel --url http://localhost:8501

echo.
pause
