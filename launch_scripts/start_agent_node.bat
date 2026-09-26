@echo off
:: ===========================================================================
:: SentiNet - Agent Node launcher (Machines 2 & 3, Windows)
::
:: Starts the privileged capture daemon, the tray app (which serves the
:: dashboard's loopback API on :8770), and the agent dashboard.
::
:: Usage:  launch_scripts\start_agent_node.bat <RELAY_IP>
::         launch_scripts\start_agent_node.bat 192.168.10.10
::         launch_scripts\start_agent_node.bat            (defaults to localhost)
:: ===========================================================================
setlocal EnableDelayedExpansion

:: There is deliberately no loopback default: assuming localhost makes an agent
:: try to connect to itself, which is refused and leaves it missing from the
:: dashboard with nothing obviously wrong. Checked before elevating so the error
:: appears in this window instead of one that closes.
if "%~1"=="" if "%SENTINET_RELAY_URL%"=="" (
    echo.
    echo ERROR: no relay address given.
    echo.
    echo   Usage: launch_scripts\start_agent_node.bat ^<RELAY-IP^>
    echo          launch_scripts\start_agent_node.bat 192.168.1.4
    echo.
    echo   The relay's start script prints the exact command to use.
    echo.
    echo   Running everything on one machine for development? Use:
    echo       launch_scripts\start_all.bat
    echo.
    pause
    exit /b 1
)

:: Scapy needs raw sockets - re-launch elevated if we aren't already.
net session >nul 2>&1
if not errorlevel 1 (
    echo Administrative permissions confirmed.
    goto :have_admin
)

echo Requesting administrative privileges for Scapy...
:: Start-Process validates -ArgumentList as NotNullOrEmpty, so passing it when
:: no relay IP was given fails with "Cannot validate argument on parameter
:: 'ArgumentList'" and nothing launches. Only pass it when there is one.
if "%~1"=="" (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
) else (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%~1' -Verb RunAs"
)
exit /b

:have_admin

:: Elevation resets the working directory to System32.
cd /d "%~dp0.."
set "ROOT=%CD%"

:: Relay location: the argument wins, then SENTINET_RELAY_URL. A leftover value
:: in the environment used to silently override an explicitly passed address.
if not "%~1"=="" (
    echo %~1 | findstr /b "http" >nul
    if errorlevel 1 (
        set "RELAY_URL=http://%~1:8771"
    ) else (
        set "RELAY_URL=%~1"
    )
) else (
    set "RELAY_URL=%SENTINET_RELAY_URL%"
)
set "SENTINET_RELAY_URL=!RELAY_URL!"

echo.
echo SentiNet - Starting AGENT NODE
echo Relay: !RELAY_URL!
echo.

echo [1/3] Checking relay reachability...
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '!RELAY_URL!/health' -TimeoutSec 4 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo       WARNING: !RELAY_URL!/health did not respond.
    echo       Start the relay first, or check the IP and Windows Firewall on port 8771.
    echo       Continuing anyway - the agent will keep retrying.
) else (
    echo       Relay is reachable.
)

if not exist "%ROOT%\tray-app\venv\Scripts\activate.bat" (
    echo       WARNING: tray-app\venv not found. The daemon will fall back to
    echo       system Python and fail with "ModuleNotFoundError: scapy" unless
    echo       the dependencies are installed globally. See README.md.
)

echo [2/3] Starting agent daemon...
:: SENTINET_RELAY_URL is already set above, so the new window inherits it.
:: Setting it inside the cmd /k string would capture the space before "&&".
:: start's /D sets the working directory, which avoids nesting quotes inside
:: the quoted cmd /k argument (that breaks on paths containing a space).
start "SentiNet Agent Daemon" /D "%ROOT%\tray-app" cmd /k "if exist venv\Scripts\activate.bat (call venv\Scripts\activate.bat) && python sentinet_daemon.py"

timeout /t 2 /nobreak >nul

if "%SKIP_TRAY%"=="1" (
    echo       Skipping tray app (SKIP_TRAY=1) - the agent dashboard will have no data source.
) else (
    echo       Starting tray app...
    start "SentiNet Tray App" /D "%ROOT%\tray-app" cmd /k "if exist venv\Scripts\activate.bat (call venv\Scripts\activate.bat) && python sentinet_tray.py"
)

if "%SKIP_DASHBOARD%"=="1" (
    echo [3/3] Skipping agent dashboard (SKIP_DASHBOARD=1).
) else (
    echo [3/3] Starting agent dashboard...
    start "SentiNet Agent Dashboard" /D "%ROOT%\agent-dashboard" cmd /k "npm run dev"
)

echo.
echo AGENT NODE is up.
echo    Agent Dashboard:  http://localhost:5173
echo    Local tray API:   http://127.0.0.1:8770
echo    Reporting to:     !RELAY_URL!
echo.
echo    Toggle protection ON from the tray icon, then confirm this agent
echo    appears in the relay's Admin Dashboard agent list.
echo.
echo    Stop everything: launch_scripts\stop_all.bat
echo.
pause
