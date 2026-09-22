@echo off
:: ===========================================================================
:: SentiNet - all-in-one launcher (single machine, local testing only)
::
:: Runs the relay node and one agent node on this machine. Convenience path for
:: development - it does NOT demonstrate the decentralized architecture. For the
:: POC demo, run start_relay_node and start_agent_node on separate machines.
:: See POC_DEMO_GUIDE.md.
:: ===========================================================================
setlocal

cd /d "%~dp0.."
set "ROOT=%CD%"

echo.
echo ====================================================
echo  SentiNet - Local Dev Environment (relay + agent)
echo ====================================================
echo.

echo Starting relay node...
call "%~dp0start_relay_node.bat"

:: Give the relay's Socket.io server a moment before the agent dials in.
timeout /t 3 /nobreak >nul

echo Starting agent node...
call "%~dp0start_agent_node.bat" http://localhost:8771

echo.
echo ====================================================
echo  All services running on this machine:
echo    Admin Dashboard:  http://localhost:5175
echo    Agent Dashboard:  http://localhost:5173
echo    Admin API:        http://localhost:8771
echo.
echo  Stop everything: launch_scripts\stop_all.bat
echo ====================================================
echo.
pause
