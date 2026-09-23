#!/bin/bash
echo "==========================================="
echo "🚽 Flushing SentiNet Database"
echo "==========================================="

echo "1. Stopping all active SentiNet services..."
./launch_scripts/stop_all.sh

echo "2. Deleting persistent SQLite database..."
rm -f admin-backend/sentinet.db

echo "✅ Database flushed! Your MAC address has been cleared."
echo "You can now run ./launch_scripts/start_all.sh to boot up with a clean slate."
