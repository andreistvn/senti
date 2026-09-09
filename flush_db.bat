@echo off
cd /d "%~dp0"
echo ===========================================
echo 🚽 Flushing SentiNet Database (Windows)
echo ===========================================

echo 1. Stopping all active SentiNet services...
call stop_all.bat

echo 2. Deleting persistent SQLite database...
if exist "admin-backend\sentinet.db" (
    del /F /Q "admin-backend\sentinet.db"
    echo Database deleted.
) else (
    echo No database found, already clean.
)

echo.
echo ✅ Database flushed! Your MAC address has been cleared.
echo You can now run start_all.bat to boot up with a clean slate.
pause
