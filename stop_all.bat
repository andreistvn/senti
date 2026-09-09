@echo off
cd /d "%~dp0"
echo.
echo Stopping SentiNet Local Dev Environment (Windows)
echo.

echo Killing services...
taskkill /FI "WINDOWTITLE eq Admin Backend*" /F /T >nul 2>&1
taskkill /FI "WINDOWTITLE eq Admin Dashboard*" /F /T >nul 2>&1
taskkill /FI "WINDOWTITLE eq Agent Daemon*" /F /T >nul 2>&1
taskkill /FI "WINDOWTITLE eq Tray App*" /F /T >nul 2>&1
taskkill /FI "WINDOWTITLE eq Agent Dashboard*" /F /T >nul 2>&1

echo All SentiNet services stopped!
pause
