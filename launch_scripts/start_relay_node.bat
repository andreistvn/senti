@echo off
:: ===========================================================================
:: SentiNet - Relay Node launcher (Machine 1, Windows)
::
:: 1. Creates the MultiChain chain if missing, starts multichaind
:: 2. Generates admin-backend\.env from the node's real RPC credentials
:: 3. Starts the FastAPI relay + admin dashboard in separate windows
::
:: Usage:  launch_scripts\start_relay_node.bat
::
:: Environment overrides:
::   CHAIN_NAME=sentinet     MultiChain chain name
::   BIND_HOST=0.0.0.0       Relay bind address (0.0.0.0 so remote agents can reach it)
::   SKIP_DASHBOARD=1        Start the API only, no Vite dev server
::   REQUIRE_CHAIN=1         Fail instead of degrading when multichaind is missing
:: ===========================================================================
setlocal EnableDelayedExpansion

:: Repo root is one level up from this script.
cd /d "%~dp0.."
set "ROOT=%CD%"

if "%CHAIN_NAME%"=="" set "CHAIN_NAME=sentinet"
if "%BIND_HOST%"=="" set "BIND_HOST=0.0.0.0"
if "%REQUIRE_CHAIN%"=="" set "REQUIRE_CHAIN=0"
set "CHAIN_DIR=%APPDATA%\MultiChain\%CHAIN_NAME%"

:: The relay is useful without a chain: detection, blacklist broadcast and both
:: dashboards work, only the ledger is unavailable. So a missing node degrades
:: instead of aborting - set REQUIRE_CHAIN=1 (demo day) to make it fatal.
set "CHAIN_AVAILABLE=1"

echo.
echo SentiNet - Starting RELAY NODE
echo Repository: %ROOT%
echo.

:: --- 1. MultiChain node --------------------------------------------------
:: setup_windows_relay.bat installs MultiChain here. Add it to this session's
:: PATH if it isn't already on the system PATH, so nobody has to fiddle with
:: environment variables or reopen their terminal.
set "MC_HOME=%LOCALAPPDATA%\SentiNet\multichain"
if exist "%MC_HOME%\multichaind.exe" set "PATH=%MC_HOME%;%PATH%"

:: A missing node is not fatal: detection, blocking and the Tier 3 blacklist
:: broadcast all work without it - only the ledger is unavailable. This mirrors
:: start_relay_node.sh. Set REQUIRE_CHAIN=1 to make it a hard error instead.
set "CHAIN_AVAILABLE=1"
where multichaind >nul 2>&1
if errorlevel 1 (
    if "%REQUIRE_CHAIN%"=="1" (
        echo ERROR: 'multichaind' not found and REQUIRE_CHAIN=1.
        echo.
        echo        Run the one-time setup first:
        echo            launch_scripts\setup_windows_relay.bat
        echo.
        echo        See WINDOWS_RELAY_SETUP.md for the full walkthrough.
        pause
        exit /b 1
    )
    set "CHAIN_AVAILABLE=0"
    echo ----------------------------------------------------------------------
    echo   WARNING: 'multichaind' not found - starting WITHOUT the ledger.
    echo ----------------------------------------------------------------------
    echo   Tier 1/2 detection and the Tier 3 blacklist broadcast still work.
    echo   Chain Status will read DEGRADED and no ledger entries will appear.
    echo.
    echo   Run the one-time setup to enable the ledger:
    echo       launch_scripts\setup_windows_relay.bat
    echo   See WINDOWS_RELAY_SETUP.md for the full walkthrough.
    echo.
    echo   Use REQUIRE_CHAIN=1 to make a missing node a hard error instead.
    echo ----------------------------------------------------------------------
    echo.
)

if "%CHAIN_AVAILABLE%"=="0" goto :chain_skip

if not exist "%CHAIN_DIR%\params.dat" (
    echo [1/4] Chain '%CHAIN_NAME%' not found - creating it...
    multichain-util create %CHAIN_NAME%
    if errorlevel 1 (
        echo ERROR: multichain-util create failed.
        echo.
        echo        multichain-util.exe is unsigned, so Windows Smart App Control
        echo        or an antivirus can block it from running at all. Check
        echo        Event Viewer under Applications and Services Logs,
        echo        Microsoft, Windows, CodeIntegrity, Operational for a block
        echo        naming multichain-util.exe.
        echo.
        echo        A chain created on another machine can be copied into
        echo        %%APPDATA%%\MultiChain\ instead - the node itself runs fine.
        pause
        exit /b 1
    )
) else (
    echo [1/4] Chain '%CHAIN_NAME%' already exists.
)

:: Liveness is checked over HTTP JSON-RPC rather than with multichain-cli.
:: multichain-cli.exe is unsigned, so Smart App Control or an antivirus can block
:: it outright - and when the probe cannot run, the old code here concluded "no
:: node is running" and started a SECOND multichaind on a chain that already had
:: one. The two collide on the permissions.db LevelDB lock and the new one dies
:: with "The handle is invalid", which looks like a corrupt chain but is not.
::
:: The relay never uses the CLI either: admin-backend\multichain.py speaks
:: JSON-RPC and reads its credentials from multichain.conf. So this probe tests
:: the same path the relay will actually use. See windows\Test-ChainRpc.ps1.
set "MC_LOG=%TEMP%\sentinet_chainrpc.log"
>"%MC_LOG%" echo [%DATE% %TIME%] SentiNet MultiChain probe log

call :probe_rpc
if not errorlevel 1 goto :chain_running

:: Probe said no. Before launching anything, ask whether a daemon is already
:: alive - this is the check that was missing.
set "MC_RUNNING="
tasklist /FI "IMAGENAME eq multichaind.exe" 2>nul | find /i "multichaind.exe" >nul
if not errorlevel 1 set "MC_RUNNING=1"

:: MultiChain's own Windows README states "The multichaind -daemon flag does not
:: work, so open another cmd prompt." So the node gets its own window instead of
:: daemonising, left open with cmd /k so a crash can be read. This comment sits
:: outside the if/else below on purpose: a :: line inside a ( ) block is parsed
:: as a label and can break the block.
if defined MC_RUNNING (
    echo       multichaind.exe is already running - not starting a second one.
) else (
    echo       Starting multichaind in its own window...
    start "SentiNet MultiChain Node" cmd /k "multichaind %CHAIN_NAME%"
)

echo       Waiting for RPC to accept connections...
set "CHAIN_UP="
for /l %%i in (1,1,30) do (
    if not defined CHAIN_UP (
        timeout /t 1 /nobreak >nul
        call :probe_rpc
        if not errorlevel 1 set "CHAIN_UP=1"
    )
)
if defined CHAIN_UP goto :chain_up

echo.
echo ERROR: the MultiChain node is not answering JSON-RPC.
if defined MC_RUNNING goto :chain_err_orphan
echo        No multichaind.exe process is running, so it exited during startup.
echo        Read the "SentiNet MultiChain Node" window for the reason -
echo        antivirus quarantining multichaind.exe is the usual cause.
goto :chain_err_tail

:chain_err_orphan
echo        A multichaind.exe process IS running but never answered RPC.
echo        Either it is still replaying the chain, or an orphan from an
echo        earlier session is holding it. Run launch_scripts\stop_all.bat
echo        to clear it, then start again.

:chain_err_tail
echo.
echo        Probe log - this is the real error, no longer swallowed by nul:
type "%MC_LOG%"
echo.
pause
exit /b 1

:chain_up
echo       Node is up.
goto :chain_done

:chain_running
echo       Node is already running.
goto :chain_done

:chain_skip
echo [1/4] Skipping MultiChain node ^(not installed^).

:chain_done

:: --- 2. Generate admin-backend\.env --------------------------------------
if "%CHAIN_AVAILABLE%"=="1" (
    echo [2/4] Extracting RPC credentials from %CHAIN_DIR%...

    if not exist "%CHAIN_DIR%\multichain.conf" (
        echo ERROR: %CHAIN_DIR%\multichain.conf not found - is the chain initialised?
        pause
        exit /b 1
    )
    set "MC_ENABLED=true"
) else (
    echo [2/4] Writing admin-backend\.env with the ledger disabled...
    set "MC_ENABLED=false"
)

:: The .env generation lives in a real .ps1 file: embedding multi-line
:: PowerShell in a .bat means fighting cmd.exe's pipe/quote escaping rules,
:: which fail on the teammate's machine rather than here.
del "%TEMP%\sentinet_lan_ip.txt" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\launch_scripts\windows\Write-RelayEnv.ps1" -ChainDir "%CHAIN_DIR%" -RepoRoot "%ROOT%" -BindHost "%BIND_HOST%" -MultiChainEnabled "%MC_ENABLED%" -LanIpOutFile "%TEMP%\sentinet_lan_ip.txt"

if errorlevel 1 (
    echo ERROR: failed to generate admin-backend\.env
    pause
    exit /b 1
)

set "LAN_IP=127.0.0.1"
if exist "%TEMP%\sentinet_lan_ip.txt" set /p LAN_IP=<"%TEMP%\sentinet_lan_ip.txt"

:: --- 3 & 4. Relay server + admin dashboard -------------------------------
echo [3/4] Starting admin backend (relay)...
set "PY_RUN=python"
if exist "%ROOT%\admin-backend\venv\Scripts\python.exe" set "PY_RUN=%ROOT%\admin-backend\venv\Scripts\python.exe"
if exist "%ROOT%\admin-backend\.venv\Scripts\python.exe" set "PY_RUN=%ROOT%\admin-backend\.venv\Scripts\python.exe"
rem Nobody can sign in to the admin dashboard until an administrator account
rem exists, so create one the first time (auth.py stores only a password hash).
if not exist "%ROOT%\admin-backend\admin_credentials.json" (
    echo.
    echo       No administrator account on this relay yet. Create one now:
    pushd "%ROOT%\admin-backend"
    "%PY_RUN%" auth.py set
    popd
    if not exist "%ROOT%\admin-backend\admin_credentials.json" (
        echo ERROR: no administrator account was created. Run: cd admin-backend ^&^& python auth.py set
        exit /b 1
    )
    echo.
)

start "SentiNet Admin Backend" /D "%ROOT%\admin-backend" cmd /k call "%PY_RUN%" main.py

if "%SKIP_DASHBOARD%"=="1" (
    echo [4/4] Skipping admin dashboard ^(SKIP_DASHBOARD=1^).
) else (
    echo [4/4] Starting admin dashboard...
    start "SentiNet Admin Dashboard" /D "%ROOT%\admin-dashboard" cmd /k "npm run dev"
)

echo.
echo RELAY NODE is up.
echo    Admin API:        http://%LAN_IP%:8771  (bound on %BIND_HOST%)
echo    Admin Dashboard:  http://localhost:5175
if "%CHAIN_AVAILABLE%"=="1" (
    echo    MultiChain:       %CHAIN_NAME%
) else (
    echo    MultiChain:       *** DISABLED - no ledger, Chain Status = DEGRADED ***
)
echo.
echo    Point agent machines at this relay with:
echo      launch_scripts\start_agent_node.bat %LAN_IP%
echo.
echo    Stop everything: launch_scripts\stop_all.bat
echo.
pause
exit /b 0


:: --- Subroutines ---------------------------------------------------------

:probe_rpc
:: Returns 0 if the node answers getinfo. Output is appended to %MC_LOG% rather
:: than discarded, so a failure leaves a readable reason behind.
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\launch_scripts\windows\Test-ChainRpc.ps1" -ChainDir "%CHAIN_DIR%" >>"%MC_LOG%" 2>&1
exit /b !ERRORLEVEL!
