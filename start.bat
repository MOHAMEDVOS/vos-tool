@echo off
echo =========================================
echo    Starting VOS Railway Application
echo =========================================
echo.

echo [1/2] Starting Backend API (FastAPI)...
start "VOS Railway Backend" cmd /k "python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

echo [2/2] Starting Frontend WebApp (React/Vite)...
cd webapp
start "VOS Railway Frontend" cmd /k "npm run dev"

echo.
echo Application successfully started in separate windows!
echo.
echo -----------------------------------------
echo Backend API : http://localhost:8000
echo Frontend UI : http://localhost:5173
echo -----------------------------------------
echo.
echo Note: To stop the servers, close the newly opened command prompt windows.
pause
