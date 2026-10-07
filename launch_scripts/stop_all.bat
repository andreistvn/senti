@echo off
:: ===========================================================================
:: SentiNet - stop every local component (Windows).
::
:: Safe to run on a relay machine, an agent machine, or a combined dev box:
:: it skips whatever isn't running.
::
:: Environment overrides:
::   CHAIN_NAME=sentinet   MultiChain chain name
::   KEEP_CHAIN=1          Leave the MultiChain node running
:: ===========================================================================
setlocal

cd /d "%~dp0.."
set "ROOT=%CD%"
if "%CHAIN_NAME%"=="" set "CHAIN_NAME=sentinet"
set "CHAIN_DIR=%APPDATA%\MultiChain\%CHAIN_NAME%"

echo.
echo Stopping SentiNet services...
echo.

:: --- 1. Service windows launched by our scripts --------------------------
:: Matched by exact "SentiNet ... Console" window title only. The old fallback
:: filters for the pre-reorganisation titles ("Admin Backend*", "Tray App*",
:: etc.) are gone, and the remaining titles all got a " Console" suffix added
:: in start_relay_node.bat / start_agent_node.bat. Reason: WINDOWTITLE is a
:: prefix match against every top-level window on the desktop, not just ours -
:: and "SentiNet Admin Dashboard" (no suffix) is *exactly* the <title> of the
:: admin-dashboard web page (admin-dashboard\index.html). Open that page in a
:: browser and its window/tab title starts with the same text, so the old
:: filter also matched the browser - and /T then killed the browser's entire
:: process tree (every window and tab), which is what looked like "other
:: applications closing". The " Console" suffix means our filter text is
:: longer than any real page title, so it can no longer match one by prefix.
echo   Closing service windows...

:: Agent Daemon installs no CTRL_CLOSE handler (see sentinet_daemon.py), so a
:: graceful close would do nothing but wait - force it immediately.
taskkill /FI "WINDOWTITLE eq SentiNet Agent Daemon Console*" /F /T >nul 2>&1

:: Everything else gets a non-forceful close first: WM_CLOSE becomes
:: CTRL_CLOSE_EVENT for the console process group, which the OS default
:: handler (or, for the tray app, its own handler) uses to exit cleanly - for
:: the tray app that is what lets it call Shell_NotifyIcon NIM_DELETE so the
:: notification-area icon doesn't linger as a "ghost". Signalling all of them
:: before waiting, instead of force-killing each in turn, also means the
:: elevated windows aren't all hit with TerminateProcess at the same instant,
:: which has been seen to leave Explorer's shell (taskbar, notification area)
:: briefly unresponsive.
for %%W in ("SentiNet Admin Backend Console" "SentiNet Admin Dashboard Console" "SentiNet Tray App Console" "SentiNet Agent Dashboard Console") do (
    taskkill /FI "WINDOWTITLE eq %%~W*" /T >nul 2>&1
)
timeout /t 2 /nobreak >nul
for %%W in ("SentiNet Admin Backend Console" "SentiNet Admin Dashboard Console" "SentiNet Tray App Console" "SentiNet Agent Dashboard Console") do (
    taskkill /FI "WINDOWTITLE eq %%~W*" /F /T >nul 2>&1
)

:: --- 2. Stragglers started outside the scripts ---------------------------
echo   Sweeping up stray python processes...
powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process -Filter \"Name like 'python%%'\" ^| Where-Object { $_.CommandLine -match 'sentinet_daemon\.py|sentinet_tray\.py|admin-backend' } ^| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

:: --- 3. MultiChain node --------------------------------------------------
if "%KEEP_CHAIN%"=="1" (
    echo   Leaving MultiChain node running ^(KEEP_CHAIN=1^).
    goto :done
)

:: Shutdown goes over JSON-RPC, not through multichain-cli. The CLI is unsigned
:: and can be blocked by Smart App Control or an antivirus, in which case this
:: script silently failed to stop anything and left an orphan multichaind holding
:: the chain - which then broke the next start_relay_node.bat run. See
:: windows\Test-ChainRpc.ps1.
if not exist "%CHAIN_DIR%\multichain.conf" (
    echo   No chain at %CHAIN_DIR% - skipping chain shutdown.
    goto :chain_kill
)

echo   Asking MultiChain node '%CHAIN_NAME%' to stop...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\launch_scripts\windows\Test-ChainRpc.ps1" -ChainDir "%CHAIN_DIR%" -Action Stop
set "RC=%ERRORLEVEL%"

if "%RC%"=="0" goto :chain_kill
if "%RC%"=="1" goto :chain_absent
if "%RC%"=="2" goto :chain_absent

:: RC 3 = node up but credentials rejected, RC 4 = asked to stop and refused.
:: Either way it is still holding the chain, and leaving it there is what breaks
:: the next start_relay_node.bat run. multichaind flushes on a clean stop, so an
:: unclean kill here is the lesser evil.
echo   Node would not shut down over RPC - terminating multichaind.exe.
taskkill /IM multichaind.exe /F /T >nul 2>&1
goto :chain_kill

:chain_absent
echo   MultiChain node '%CHAIN_NAME%' was not running.

:chain_kill
:: Close the node's own window if our launcher opened one.
taskkill /FI "WINDOWTITLE eq SentiNet MultiChain Node Console*" /F /T >nul 2>&1

:done
echo.
echo All SentiNet services stopped.
echo.
pause
