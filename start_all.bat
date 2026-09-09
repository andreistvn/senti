@echo off

:: Check for admin rights and request if missing
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Administrative permissions confirmed.
) else (
    echo Requesting administrative privileges for Scapy...
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

:: Ensure we are in the script's directory (elevation changes it to System32)
cd /d "%~dp0"

echo.
echo Booting SentiNet Local Dev Environment (Windows)
echo.

echo Starting Admin Backend...
start "Admin Backend" cmd /k "cd admin-backend && if exist venv\Scripts\activate (call venv\Scripts\activate) && python main.py"

echo Starting Admin Dashboard...
start "Admin Dashboard" cmd /k "cd admin-dashboard && npm run dev"

echo Starting Agent Daemon (Requires Admin Rights for Scapy)...
start "Agent Daemon" cmd /k "cd tray-app && if exist venv\Scripts\activate (call venv\Scripts\activate) && python sentinet_daemon.py"

echo Starting Tray App...
start "Tray App" cmd /k "cd tray-app && if exist venv\Scripts\activate (call venv\Scripts\activate) && python sentinet_tray.py"

echo Starting Agent Dashboard...
start "Agent Dashboard" cmd /k "cd agent-dashboard && npm run dev"

echo.
echo All services started in separate windows!
echo    - Admin Backend: http://localhost:8771
echo    - Admin Dashboard: http://localhost:5175
echo    - Agent Dashboard: http://localhost:5173
echo.
echo To stop everything, run: stop_all.bat
pause
