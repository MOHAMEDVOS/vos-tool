@echo off

if "%FORCE_READYMODE%"=="" set FORCE_READYMODE=true
if "%DEPLOYMENT_MODE%"=="" set DEPLOYMENT_MODE=enterprise
if "%PORT%"=="" set PORT=8501

cd /d "%~dp0"

py -3.10 -m streamlit run app.py --server.port %PORT% --server.address 0.0.0.0

pause
