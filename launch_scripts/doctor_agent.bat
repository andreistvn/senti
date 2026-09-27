@echo off
:: ===========================================================================
:: SentiNet - agent-side diagnostic (Windows).
::
:: Answers, in one command, why this machine is not showing up on the admin
:: dashboard. Run it ON THE AGENT MACHINE, with the relay's address:
::
::     launch_scripts\doctor_agent.bat 192.168.1.4
::
:: It checks, in the order the connection actually happens:
::   1. what the daemon believes the relay address is
::   2. whether that address answers plain HTTP  (network reachable?)
::   3. whether the socket.io handshake completes (the transport agents use)
::   4. whether the daemon and tray are listening on their local ports
::   5. whether protection is toggled ON (an agent only registers once it is)
::   6. what the daemon's own log says about the relay
::
:: Read-only: it starts and stops nothing.
:: ===========================================================================
setlocal EnableDelayedExpansion

cd /d "%~dp0.."
set "ROOT=%CD%"
set "DAEMON_LOG=%TEMP%\sentinet_daemon.log"
set "TRAY_LOG=%TEMP%\sentinet_tray_app.log"

if not "%~1"=="" (
    echo %~1 | findstr /b "http" >nul
    if errorlevel 1 (
        set "RELAY_URL=http://%~1:8771"
    ) else (
        set "RELAY_URL=%~1"
    )
) else if not "%SENTINET_RELAY_URL%"=="" (
    set "RELAY_URL=%SENTINET_RELAY_URL%"
) else (
    echo.
    echo Usage: launch_scripts\doctor_agent.bat ^<RELAY-IP^>
    echo.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo  SentiNet - agent diagnostic
echo  This machine    : %COMPUTERNAME%
echo  Relay under test: !RELAY_URL!
echo ================================================================

:: --- 1. What the daemon actually thinks -----------------------------------
echo.
echo [1] Relay address the daemon is using
set "DAEMON_TARGET="
if exist "%DAEMON_LOG%" (
    for /f "tokens=*" %%t in ('powershell -NoProfile -Command "$m = Select-String -Path '%DAEMON_LOG%' -Pattern 'Relay target: (.+)' ^| Select-Object -Last 1; if ($m) { $m.Matches[0].Groups[1].Value.Trim() }"') do set "DAEMON_TARGET=%%t"
)
if not defined DAEMON_TARGET (
    echo   [warn] No 'Relay target:' line in %DAEMON_LOG%
    echo          Either the daemon has not run since this diagnostic was added,
    echo          or the log is missing. Restart the agent and re-run.
) else (
    if /i "!DAEMON_TARGET!"=="!RELAY_URL!" (
        echo   [ ok ] !DAEMON_TARGET!
    ) else (
        echo   [FAIL] The daemon is using: !DAEMON_TARGET!
        echo          ...but you are testing: !RELAY_URL!
        echo          The agent is talking to the wrong relay. Restart it with:
        echo            launch_scripts\start_agent_node.bat !RELAY_URL!
    )
)

:: --- 2. Plain HTTP reachability -------------------------------------------
echo.
echo [2] Is !RELAY_URL! reachable at all?
set "NET_OK=0"
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '!RELAY_URL!/health' -TimeoutSec 6 -UseBasicParsing; if ($r.Content -match 'ok') { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] No response from !RELAY_URL!/health
    for /f "tokens=*" %%h in ('powershell -NoProfile -Command "([uri]'!RELAY_URL!').Host"') do set "RHOST=%%h"
    ping -n 1 -w 2000 !RHOST! >nul 2>&1
    if errorlevel 1 (
        echo          Host !RHOST! does not even ping. That is a network problem:
        echo            - wrong relay IP ^(check 'ipconfig' on the relay^)
        echo            - different subnets ^(compare the first three octets^)
        echo            - router client/AP isolation, or a guest network
    ) else (
        echo          Host !RHOST! pings, so the port is the problem:
        echo            - firewall on the relay machine blocking TCP 8771
        echo            - the relay is not running, or bound to 127.0.0.1 only
    )
) else (
    echo   [ ok ] /health responded.
    set "NET_OK=1"
)

:: --- 3. socket.io handshake -----------------------------------------------
echo.
echo [3] Does the socket.io handshake complete?
if "!NET_OK!"=="1" (
    powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '!RELAY_URL!/socket.io/?EIO=4&transport=polling' -TimeoutSec 6 -UseBasicParsing; if ($r.Content -match 'sid') { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
    if errorlevel 1 (
        echo   [FAIL] HTTP works but socket.io did not hand back a session id.
        echo          Something is proxying or intercepting the connection.
    ) else (
        echo   [ ok ] The relay accepted a socket.io handshake.
        echo          So the transport the agent uses is working.
    )
) else (
    echo          Skipped - plain HTTP already failed.
)

:: --- 4. Local processes ---------------------------------------------------
echo.
echo [4] Are the agent processes running?
:: On Windows the daemon's IPC listens on 8769 and the tray serves its API on
:: 8770, so the ports are a more reliable signal than the task list.
call :check_port 8769
if errorlevel 1 (
    echo   [FAIL] capture daemon is NOT running - nothing will ever register.
) else (
    echo   [ ok ] capture daemon
)
call :check_port 8770
if errorlevel 1 (
    echo   [FAIL] tray app is NOT running.
    echo          Without it you cannot toggle protection, and an agent only
    echo          registers with the relay once protection is ON.
) else (
    echo   [ ok ] tray app
)

:: --- 5. Is protection actually ON? ----------------------------------------
echo.
echo [5] Is protection toggled ON?
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8770/api/status' -TimeoutSec 4 -UseBasicParsing; if ($r.Content -match '\"protected\"\s*:\s*true') { exit 0 } else { exit 2 } } catch { exit 1 }" >nul 2>&1
if errorlevel 2 (
    echo   [FAIL] Protection is OFF. Toggle it from the tray icon or the agent
    echo          dashboard - the agent does not connect to the relay until then.
) else (
    if errorlevel 1 (
        echo   [warn] The tray's local API on 127.0.0.1:8770 did not answer.
        echo          Falling back to the daemon log below.
    ) else (
        echo   [ ok ] Protection is ON.
    )
)

:: --- 6. What the daemon logged about the relay -----------------------------
echo.
echo [6] Last relay-connection lines from the daemon
if exist "%DAEMON_LOG%" (
    powershell -NoProfile -Command "$l = Select-String -Path '%DAEMON_LOG%' -Pattern 'BayanihanClient' ^| Select-Object -Last 12; if ($l) { $l.Line ^| ForEach-Object { '       ' + $_.Trim() } } else { '       (no BayanihanClient lines yet)' }"
    echo.
    powershell -NoProfile -Command "$t = Get-Content '%DAEMON_LOG%' -Raw; if ($t -match 'Connected to Relay Node') { '  [ ok ] The agent has connected to the relay at least once.'; '         If it is still not on the dashboard, check the relay console for'; '         an ''Agent registered'' line for this machine.' } elseif ($t -match 'Cannot reach the relay') { '  [FAIL] The agent is failing to connect - the reason is printed above.' } elseif ($t -match 'Waiting for protection') { '  [FAIL] The agent has never tried to connect: protection was never toggled'; '         ON, or the toggle never reached the daemon.' }"
) else (
    echo   [warn] %DAEMON_LOG% does not exist - the daemon has not run.
)

echo.
echo ================================================================
echo  Paste this whole output when asking for help - it covers every
echo  step between this machine and the relay.
echo ================================================================
echo.
pause
goto :eof

:check_port
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %1 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
exit /b %errorlevel%
