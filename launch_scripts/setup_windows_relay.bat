@echo off
:: ===========================================================================
:: SentiNet - one-time Relay Node setup for Windows.
::
:: Installs everything start_relay_node.bat needs:
::   1. Checks for Python 3 and Node.js (installs via winget if available)
::   2. Downloads MultiChain and installs it to a private folder
::   3. Creates the admin-backend Python venv + dependencies
::   4. Installs admin-dashboard npm dependencies
::   5. Opens the Windows Firewall ports the agents connect to
::
:: Run ONCE on the relay machine, then use start_relay_node.bat every time.
:: Safe to re-run - each step skips work already done.
::
:: Usage:  launch_scripts\setup_windows_relay.bat
:: ===========================================================================
setlocal EnableDelayedExpansion

:: Firewall rules need admin, so elevate up front rather than failing at step 5.
net session >nul 2>&1
if not errorlevel 1 (
    echo Administrative permissions confirmed.
) else (
    echo Requesting administrative privileges ^(needed for firewall rules^)...
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

:: Elevation resets the working directory to System32.
cd /d "%~dp0.."
set "ROOT=%CD%"
set "MC_HOME=%LOCALAPPDATA%\SentiNet\multichain"
set "MC_VERSION=2.3.3"

echo.
echo ================================================================
echo  SentiNet - Relay Node setup (Windows)
echo  Repository: %ROOT%
echo ================================================================
echo.

if not exist "%ROOT%\admin-backend\requirements.txt" (
    echo ERROR: can't find admin-backend\requirements.txt under %ROOT%
    echo        Run this from inside the cloned repository.
    pause
    exit /b 1
)

:: --- 1. Python and Node --------------------------------------------------
echo [1/5] Checking prerequisites...

set "PY_CMD="
where python >nul 2>&1 && set "PY_CMD=python"
if not defined PY_CMD (
    where py >nul 2>&1 && set "PY_CMD=py"
)

if not defined PY_CMD (
    echo       Python not found. Attempting install via winget...
    where winget >nul 2>&1
    if errorlevel 1 (
        echo.
        echo ERROR: Python 3 is required and winget is unavailable.
        echo        Install Python 3.11+ from https://www.python.org/downloads/
        echo        IMPORTANT: tick "Add python.exe to PATH" in the installer.
        echo        Then re-run this script.
        pause
        exit /b 1
    )
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    echo.
    echo       Python installed. CLOSE THIS WINDOW and re-run this script so
    echo       the new PATH takes effect.
    pause
    exit /b 0
)
for /f "delims=" %%v in ('%PY_CMD% --version 2^>^&1') do echo       Python: %%v

where node >nul 2>&1
if errorlevel 1 (
    echo       Node.js not found. Attempting install via winget...
    where winget >nul 2>&1
    if errorlevel 1 (
        echo.
        echo ERROR: Node.js is required for the dashboard and winget is unavailable.
        echo        Install the LTS build from https://nodejs.org/
        echo        Then re-run this script.
        pause
        exit /b 1
    )
    winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
    echo.
    echo       Node.js installed. CLOSE THIS WINDOW and re-run this script so
    echo       the new PATH takes effect.
    pause
    exit /b 0
)
for /f "delims=" %%v in ('node --version 2^>^&1') do echo       Node.js: %%v

:: --- 2. MultiChain -------------------------------------------------------
echo.
if exist "%MC_HOME%\multichaind.exe" (
    echo [2/5] MultiChain already installed at %MC_HOME%
) else (
    echo [2/5] Downloading MultiChain %MC_VERSION% ^(~19 MB^)...

    if not exist "%MC_HOME%" mkdir "%MC_HOME%" 2>nul

    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\launch_scripts\windows\Install-MultiChain.ps1" -Destination "%MC_HOME%" -Version "%MC_VERSION%"

    if errorlevel 1 (
        echo.
        echo ERROR: MultiChain download or extraction failed.
        echo        Check your internet connection, then re-run this script.
        echo        Or download manually from:
        echo          https://www.multichain.com/download/multichain-windows-%MC_VERSION%.zip
        echo        and extract it into: %MC_HOME%
        pause
        exit /b 1
    )
)

:: Verify the binaries actually run before moving on.
set "PATH=%MC_HOME%;%PATH%"
multichaind --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo       WARNING: multichaind.exe would not run.
    echo       Two causes, and they need different fixes:
    echo        1. Antivirus quarantined it - MultiChain's own README warns
    echo           about this. Add an exclusion for:
    echo               %MC_HOME%
    echo           then re-run this script.
    echo        2. Windows 11 Smart App Control blocked it for being unsigned.
    echo           Event Viewer, Applications and Services Logs, Microsoft,
    echo           Windows, CodeIntegrity, Operational will name the file.
    echo           Do NOT turn Smart App Control off - it cannot be turned back
    echo           on without reinstalling Windows. Use a machine without it,
    echo           or run the relay in a Linux VM, instead.
    set "MC_BROKEN=1"
) else (
    for /f "delims=" %%v in ('multichaind --version 2^>^&1') do (
        echo       Verified: %%v
        goto :mc_done
    )
)
:mc_done

:: --- 3. Backend venv -----------------------------------------------------
echo.
echo [3/5] Setting up admin-backend Python environment...
cd /d "%ROOT%\admin-backend"

if not exist venv (
    %PY_CMD% -m venv venv
    if errorlevel 1 (
        echo ERROR: could not create the virtual environment.
        pause
        exit /b 1
    )
    echo       Created venv.
) else (
    echo       venv already exists.
)

call venv\Scripts\activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

python -c "import fastapi, uvicorn, socketio, sqlalchemy, requests, dotenv" >nul 2>&1
if errorlevel 1 (
    echo ERROR: backend imports failed - dependency install is incomplete.
    pause
    exit /b 1
)
echo       Dependencies installed and imports verified.

:: --- 4. Dashboard deps ---------------------------------------------------
echo.
cd /d "%ROOT%\admin-dashboard"
if exist node_modules (
    echo [4/5] Dashboard dependencies already present - skipping.
    echo       Delete admin-dashboard\node_modules to force a reinstall.
) else (
    echo [4/5] Installing dashboard dependencies ^(takes a few minutes^)...
    call npm install --no-fund --no-audit
    if errorlevel 1 (
        echo ERROR: npm install failed.
        pause
        exit /b 1
    )
    echo       Dashboard dependencies installed.
)

:: --- 5. Firewall ---------------------------------------------------------
echo.
echo [5/5] Opening firewall ports for the agent machines...
netsh advfirewall firewall show rule name="SentiNet Relay API 8771" >nul 2>&1
if errorlevel 1 (
    netsh advfirewall firewall add rule name="SentiNet Relay API 8771" dir=in action=allow protocol=TCP localport=8771 >nul 2>&1
    if errorlevel 1 (echo       Could not add rule for 8771.) else (echo       Opened TCP 8771 ^(relay API + Socket.io^))
) else (
    echo       TCP 8771 rule already present.
)

netsh advfirewall firewall show rule name="SentiNet Dashboard 5175" >nul 2>&1
if errorlevel 1 (
    netsh advfirewall firewall add rule name="SentiNet Dashboard 5175" dir=in action=allow protocol=TCP localport=5175 >nul 2>&1
    if errorlevel 1 (echo       Could not add rule for 5175.) else (echo       Opened TCP 5175 ^(admin dashboard^))
) else (
    echo       TCP 5175 rule already present.
)

:: --- Done ----------------------------------------------------------------
cd /d "%ROOT%"

del "%TEMP%\sentinet_lan_ip.txt" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\launch_scripts\windows\Get-LanIp.ps1" -OutFile "%TEMP%\sentinet_lan_ip.txt" >nul 2>&1
set "LAN_IP=127.0.0.1"
if exist "%TEMP%\sentinet_lan_ip.txt" set /p LAN_IP=<"%TEMP%\sentinet_lan_ip.txt"

echo.
echo ================================================================
if "%MC_BROKEN%"=="1" (
    echo  Setup finished - but MultiChain will not run on this machine.
    echo  The relay will start with the ledger DISABLED until that's fixed.
) else (
    echo  Setup complete.
)
echo.
echo  This machine's LAN IP: %LAN_IP%
echo.
echo  Start the relay:
echo      launch_scripts\start_relay_node.bat
echo.
echo  Then on each agent machine:
echo      launch_scripts\start_agent_node.bat %LAN_IP%
echo ================================================================
echo.
pause
