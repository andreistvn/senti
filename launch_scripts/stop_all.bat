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
if "%CHAIN_NAME%"=="" set "CHAIN_NAME=sentinet"

echo.
echo Stopping SentiNet services...
echo.

:: --- 1. Service windows launched by our scripts --------------------------
echo   Closing service windows...
taskkill /FI "WINDOWTITLE eq SentiNet Admin Backend*"   /F /T >nul 2>&1
taskkill /FI "WINDOWTITLE eq SentiNet Admin Dashboard*" /F /T >nul 2>&1
taskkill /FI "WINDOWTITLE eq SentiNet Agent Daemon*"    /F /T >nul 2>&1
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

where multichain-cli >nul 2>&1
if errorlevel 1 (
    echo   multichain-cli not on PATH - skipping chain shutdown.
    goto :done
)

multichain-cli %CHAIN_NAME% getinfo >nul 2>&1
if errorlevel 1 (
    echo   MultiChain node '%CHAIN_NAME%' is not running.
) else (
    echo   Stopping MultiChain node '%CHAIN_NAME%'...
    multichain-cli %CHAIN_NAME% stop >nul 2>&1
    :: multichaind flushes its wallet on shutdown; give it a moment.
    timeout /t 2 /nobreak >nul
)

:: If the node ignored the graceful stop, close its window too.
taskkill /FI "WINDOWTITLE eq SentiNet MultiChain Node*" /F /T >nul 2>&1

:done
echo.
echo All SentiNet services stopped.
echo.
pause
