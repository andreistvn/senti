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
echo   Closing service windows...
taskkill /FI "WINDOWTITLE eq SentiNet Admin Backend*"   /F /T >nul 2>&1
taskkill /FI "WINDOWTITLE eq SentiNet Admin Dashboard*" /F /T >nul 2>&1
taskkill /FI "WINDOWTITLE eq SentiNet Agent Daemon*"    /F /T >nul 2>&1

:: Tray app first gets a non-forceful close so its CTRL_CLOSE handler can run
:: and remove the notification-area icon (a force-killed process never gets
:: to call Shell_NotifyIcon NIM_DELETE, leaving a "ghost" icon behind).
taskkill /FI "WINDOWTITLE eq SentiNet Tray App*"        /T >nul 2>&1
timeout /t 2 /nobreak >nul
taskkill /FI "WINDOWTITLE eq SentiNet Tray App*"        /F /T >nul 2>&1

taskkill /FI "WINDOWTITLE eq SentiNet Agent Dashboard*" /F /T >nul 2>&1

:: Window titles from the pre-reorganisation scripts, for good measure.
taskkill /FI "WINDOWTITLE eq Admin Backend*"   /F /T >nul 2>&1
taskkill /FI "WINDOWTITLE eq Admin Dashboard*" /F /T >nul 2>&1
taskkill /FI "WINDOWTITLE eq Agent Daemon*"    /F /T >nul 2>&1
taskkill /FI "WINDOWTITLE eq Tray App*"        /F /T >nul 2>&1
taskkill /FI "WINDOWTITLE eq Agent Dashboard*" /F /T >nul 2>&1

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
