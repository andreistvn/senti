#!/bin/bash

echo ""
echo "Stopping SentiNet Local Dev Environment"
echo ""

stop_service() {
    local name=$1
    local pid_file="/tmp/sentinet_${name}.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        echo "Killing $name (PID $pid)..."
        # We use pkill -P to kill the process and all its children (e.g. npm spawns node)
        pkill -P "$pid" 2>/dev/null
        kill "$pid" 2>/dev/null
        rm "$pid_file"
    else
        echo "$name does not appear to be running."
    fi
}

stop_service "admin_backend"
stop_service "admin_dashboard"
stop_service "tray_app"
stop_service "agent_dashboard"

# The daemon was started with sudo, so we must kill it with sudo
echo "Killing Agent Daemon (requires sudo)..."
sudo pkill -f "sentinet_daemon.py"

echo "All SentiNet services stopped!"
