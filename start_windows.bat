@echo off
title Audilect — Active Learning Cockpit
echo ===================================================
echo   Starting Audilect Active Learning Cockpit...
echo ===================================================

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not found in PATH.
    echo Please install Python 3.9+ from https://www.python.org/
    pause
    exit /b 1
)

echo Checking dependencies...
pip install -r requirements.txt --quiet

echo Launching web cockpit on http://localhost:8000
start http://localhost:8000
python run.py --host 127.0.0.1 --port 8000
pause
