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

:: Pre-flight. On a fresh clone these are missing and the tray and dashboard die
:: instantly, while the script used to report success anyway.
:: Both venv and .venv are accepted - older setup instructions used .venv.
set "TRAY_PY="
if exist "%ROOT%\tray-app\venv\Scripts\python.exe"  set "TRAY_PY=%ROOT%\tray-app\venv\Scripts\python.exe"
if exist "%ROOT%\tray-app\.venv\Scripts\python.exe" set "TRAY_PY=%ROOT%\tray-app\.venv\Scripts\python.exe"

set "MISSING=0"
if not defined TRAY_PY (
    echo.
    echo ERROR: no tray-app virtualenv found ^(looked for venv and .venv^). Create one:
    echo     cd tray-app
    echo     python -m venv venv
    echo     venv\Scripts\activate
    echo     pip install -r requirements.txt
    set "MISSING=1"
)
if not "%SKIP_DASHBOARD%"=="1" (
    if not exist "%ROOT%\agent-dashboard\node_modules" (
        echo.
        echo ERROR: agent-dashboard\node_modules is missing. Install it:
        echo     cd agent-dashboard ^&^& npm install
        set "MISSING=1"
    )
)
if "%MISSING%"=="1" (
    echo.
    echo Run those from the repository root, then start the agent again.
    echo See README.md for the full first-time install.
    pause
    exit /b 1
)

echo [2/3] Starting agent daemon...
:: SENTINET_RELAY_URL is already set above, so the new window inherits it.
:: Tee-Object writes output to both the window and a log file - cmd /k alone
:: leaves nothing on disk, and the checks below plus doctor_agent.bat read it.
:: start's /D sets the working directory, avoiding quotes nested inside the
:: quoted command, which breaks on paths containing a space.
set "DAEMON_LOG=%TEMP%\sentinet_daemon.log"
del "%DAEMON_LOG%" >nul 2>&1
start "SentiNet Agent Daemon" /D "%ROOT%\tray-app" powershell -NoProfile -ExecutionPolicy Bypass -Command "& '%TRAY_PY%' sentinet_daemon.py 2>&1 | Tee-Object -FilePath '%DAEMON_LOG%'"

timeout /t 2 /nobreak >nul

if "%SKIP_TRAY%"=="1" (
    echo       Skipping tray app ^(SKIP_TRAY=1^) - the agent dashboard will have no data source.
) else (
    echo       Starting tray app...
    start "SentiNet Tray App" /D "%ROOT%\tray-app" powershell -NoProfile -ExecutionPolicy Bypass -Command "& '%TRAY_PY%' sentinet_tray.py 2>&1 | Tee-Object -FilePath '%TEMP%\sentinet_tray_app.log'"
)

if "%SKIP_DASHBOARD%"=="1" (
    echo [3/3] Skipping agent dashboard ^(SKIP_DASHBOARD=1^).
) else (
    echo [3/3] Starting agent dashboard...
    start "SentiNet Agent Dashboard" /D "%ROOT%\agent-dashboard" cmd /k "npm run dev"
)

timeout /t 4 /nobreak >nul

set "FAILED=0"

:: The daemon's IPC listens on TCP 8769 on Windows (Unix sockets are unavailable),
:: and the tray serves the dashboard's API on 8770. Checking the ports is more
:: reliable than matching window titles or python.exe in the task list.
call :check_port 8769
if errorlevel 1 (
    echo.
    echo ERROR: the agent daemon is not running. Last lines of %DAEMON_LOG%:
    echo ---
    if exist "%DAEMON_LOG%" (powershell -NoProfile -Command "Get-Content -Tail 15 '%DAEMON_LOG%'") else (echo    ^(no log written^))
    echo ---
    echo Common causes: Scapy needs Administrator, or a missing dependency.
    set "FAILED=1"
) else (
    echo       Daemon is running.
)

:: Confirm the daemon received the relay address. It is started as a separate
:: process, so a failure to pass it through would otherwise only show up later
:: as "this machine never appears on the dashboard".
if exist "%DAEMON_LOG%" (
    for /f "tokens=*" %%t in ('powershell -NoProfile -Command "$m = Select-String -Path '%DAEMON_LOG%' -Pattern 'Relay target: (.+)' ^| Select-Object -Last 1; if ($m) { $m.Matches[0].Groups[1].Value.Trim() }"') do set "DAEMON_TARGET=%%t"
)
if defined DAEMON_TARGET (
    if /i not "!DAEMON_TARGET!"=="!RELAY_URL!" (
        echo.
        echo ERROR: the daemon is using the wrong relay address.
        echo          started with : !RELAY_URL!
        echo          daemon using : !DAEMON_TARGET!
        echo.
        echo The address did not reach the daemon. It would never find the relay.
        set "FAILED=1"
    ) else (
        echo       Daemon is targeting !DAEMON_TARGET!
    )
)

if not "%SKIP_TRAY%"=="1" (
    call :check_port 8770
    if errorlevel 1 (
        echo.
        echo ERROR: the tray app exited. Last lines of its log:
        echo ---
        if exist "%TEMP%\sentinet_tray_app.log" (powershell -NoProfile -Command "Get-Content -Tail 15 '%TEMP%\sentinet_tray_app.log'") else (echo    ^(no log written^))
        echo ---
        echo Without the tray you cannot toggle protection, and an agent only
        echo registers with the relay once protection is ON.
        set "FAILED=1"
    ) else (
        echo       Tray app is running.
    )
)

if not "%SKIP_DASHBOARD%"=="1" (
    call :check_port 5173
    if errorlevel 1 (
        echo       WARNING: the agent dashboard is not serving on 5173 yet.
        echo       Vite can be slow to start; check the "SentiNet Agent Dashboard" window.
    ) else (
        echo       Agent dashboard is running.
    )
)

if "%FAILED%"=="1" (
    echo.
    echo One or more components did not start. Stop what did with:
    echo     launch_scripts\stop_all.bat
    pause
    exit /b 1
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

goto :eof

:check_port
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %1 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
exit /b %errorlevel%
