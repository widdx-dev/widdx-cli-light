@echo off
title WIDDX Nexus — Web UI
cd /d "%~dp0"
echo ============================================
echo   WIDDX Nexus — Mission Control
echo   By MUHAMMAD MUSLIH (widdx.com)
echo ============================================
echo.
echo Starting Web UI at http://localhost:8009
echo Press Ctrl+C to stop
echo.
python scripts/web_app.py --port 8009
pause
