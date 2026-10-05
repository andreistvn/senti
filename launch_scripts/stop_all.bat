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
:: Matched by exact "SentiNet ..." window title only. The old fallback filters
:: for the pre-reorganisation titles ("Admin Backend*", "Tray App*", etc.) are
:: gone: WINDOWTITLE is a prefix match against every top-level window on the
:: desktop, not just ours, so a generic title like that can match an unrelated
:: window (a browser tab, another app) and /T then kills that window's whole
:: process tree too.
echo   Closing service windows...

:: Agent Daemon installs no CTRL_CLOSE handler (see sentinet_daemon.py), so a
:: graceful close would do nothing but wait - force it immediately.
taskkill /FI "WINDOWTITLE eq SentiNet Agent Daemon*" /F /T >nul 2>&1

:: Everything else gets a non-forceful close first: WM_CLOSE becomes
:: CTRL_CLOSE_EVENT for the console process group, which the OS default
:: handler (or, for the tray app, its own handler) uses to exit cleanly - for
:: the tray app that is what lets it call Shell_NotifyIcon NIM_DELETE so the
:: notification-area icon doesn't linger as a "ghost". Signalling all of them
:: before waiting, instead of force-killing each in turn, also means the
:: elevated windows aren't all hit with TerminateProcess at the same instant,
:: which has been seen to leave Explorer's shell (taskbar, notification area)
:: briefly unresponsive.
for %%W in ("SentiNet Admin Backend" "SentiNet Admin Dashboard" "SentiNet Tray App" "SentiNet Agent Dashboard") do (
    taskkill /FI "WINDOWTITLE eq %%~W*" /T >nul 2>&1
)
timeout /t 2 /nobreak >nul
for %%W in ("SentiNet Admin Backend" "SentiNet Admin Dashboard" "SentiNet Tray App" "SentiNet Agent Dashboard") do (
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
taskkill /FI "WINDOWTITLE eq SentiNet MultiChain Node*" /F /T >nul 2>&1

:done
echo.
echo All SentiNet services stopped.
echo.
pause
