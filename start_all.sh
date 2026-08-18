#!/bin/bash

echo "==========================================="
echo "🚀 Booting SentiNet Local Dev Environment"
echo "==========================================="

# Helper function to run a command in the background and log it
start_service() {
    local name=$1
    local dir=$2
    local cmd=$3
    local log_file="/tmp/sentinet_${name}.log"

    echo "Starting $name..."
    cd "$dir" || exit
    
    # If using venv, ensure we use it
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    
    # Run the command in the background, redirecting output to log file
    eval "$cmd" > "$log_file" 2>&1 &
    
    # Save the Process ID so we can kill it later
    echo $! > "/tmp/sentinet_${name}.pid"
    cd - > /dev/null
}

# 1. Admin Backend (Relay Node)
start_service "admin_backend" "admin-backend" "python3 main.py"

# 2. Admin Dashboard (Vite)
start_service "admin_dashboard" "admin-dashboard" "npm run dev"

# 3. Agent Daemon (Requires Sudo - will prompt for password!)
# Note: we use sudo -b to run it in the background
echo "Starting Agent Daemon (Sudo required for Scapy)..."
cd tray-app
source venv/bin/activate
sudo -b venv/bin/python3 sentinet_daemon.py > /tmp/sentinet_daemon.log 2>&1
# Finding the PID of the sudo command is tricky, so we'll just pkill it in stop_all.sh
cd - > /dev/null

# 4. Agent Tray App
start_service "tray_app" "tray-app" "python3 sentinet_tray.py"

# 5. Agent Dashboard (Vite)
start_service "agent_dashboard" "agent-dashboard" "npm run dev"

echo ""
echo "✅ All services started in the background!"
echo "   - Admin Backend: http://localhost:8771"
echo "   - Admin Dashboard: http://localhost:5175"
echo "   - Agent Dashboard: http://localhost:5173"
echo ""
echo "Logs are located at: /tmp/sentinet_*.log"
echo "To stop everything, run: ./stop_all.sh"
