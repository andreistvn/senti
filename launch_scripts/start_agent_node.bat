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

:: Scapy needs raw sockets - re-launch elevated if we aren't already.
net session >nul 2>&1
if not errorlevel 1 (
    echo Administrative permissions confirmed.
<<<<<<< HEAD
) else (
    echo Requesting administrative privileges for Scapy...
    if "%~1"=="" (
        powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    ) else (
        powershell -Command "Start-Process '%~dpnx0' -ArgumentList '%1' -Verb RunAs"
    )
    exit /b
=======
    goto :have_admin
>>>>>>> origin/main
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

:: Relay location: env var > argument > loopback.
if not "%SENTINET_RELAY_URL%"=="" (
    set "RELAY_URL=%SENTINET_RELAY_URL%"
) else if not "%~1"=="" (
    echo %~1 | findstr /b "http" >nul
    if errorlevel 1 (
        set "RELAY_URL=http://%~1:8771"
    ) else (
        set "RELAY_URL=%~1"
    )
) else (
    set "RELAY_URL=http://localhost:8771"
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

<<<<<<< HEAD
set "TRAY_PY=python"
if exist "%ROOT%\tray-app\venv\Scripts\python.exe" set "TRAY_PY=%ROOT%\tray-app\venv\Scripts\python.exe"
if exist "%ROOT%\tray-app\.venv\Scripts\python.exe" set "TRAY_PY=%ROOT%\tray-app\.venv\Scripts\python.exe"

echo [2/3] Starting agent daemon...
start "SentiNet Agent Daemon" /D "%ROOT%\tray-app" cmd /k call "%TRAY_PY%" sentinet_daemon.py
=======
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
>>>>>>> origin/main

timeout /t 2 /nobreak >nul

:: Don't claim success if elevation was declined or Scapy failed to bind -
:: that failure is otherwise invisible until you wonder why no threats appear.
powershell -NoProfile -Command "$found = (Get-CimInstance Win32_Process -Filter \"Name like 'python%%'\").Where({ $_.CommandLine -match 'sentinet_daemon\.py' }); if ($found) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: the agent daemon is not running.
    echo        Check the "SentiNet Agent Daemon" window for the reason.
    echo        Common causes: UAC/elevation declined, a missing dependency, or
    echo        the loopback tray API port already in use.
    echo        Without the daemon there is no packet capture - fix this before demoing.
    pause
    exit /b 1
)
echo       Daemon is running.

if "%SKIP_TRAY%"=="1" (
    echo       Skipping tray app ^(SKIP_TRAY=1^) - the agent dashboard will have no data source.
) else (
    echo       Starting tray app...
<<<<<<< HEAD
    start "SentiNet Tray App" /D "%ROOT%\tray-app" cmd /k call "%TRAY_PY%" sentinet_tray.py
=======
    start "SentiNet Tray App" /D "%ROOT%\tray-app" cmd /k "if exist venv\Scripts\activate.bat (call venv\Scripts\activate.bat) && python sentinet_tray.py"
>>>>>>> origin/main
)

if "%SKIP_DASHBOARD%"=="1" (
    echo [3/3] Skipping agent dashboard ^(SKIP_DASHBOARD=1^).
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
