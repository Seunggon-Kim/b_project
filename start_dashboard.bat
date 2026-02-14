@echo off
echo ========================================
echo KBO Analytics Dashboard - Web Server
echo ========================================
echo.

cd /d "%~dp0\dashboard_js"

echo Starting local web server...
echo Dashboard will be available at: http://localhost:8080
echo.
echo Make sure the API server is running on port 8000!
echo.
echo Press Ctrl+C to stop the server
echo.

python -m http.server 8080

pause
