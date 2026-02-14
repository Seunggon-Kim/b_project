@echo off
echo ========================================
echo KBO Analytics Dashboard - API Server
echo ========================================
echo.

cd /d "%~dp0"

echo Starting FastAPI server...
echo API will be available at: http://localhost:8000
echo API docs will be available at: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo.

python api\main.py

pause
