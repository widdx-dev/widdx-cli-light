@echo off
REM WIDDX Nexus — Web Launcher
REM Place this file in any folder and double-click to start WIDDX Web

set WIDDX_HOME=C:\widdx-cli-light-master
cd /d "%~dp0"
python "%WIDDX_HOME%\widdx_web.py"
