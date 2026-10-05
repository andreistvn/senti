#!/bin/bash
#
# SentiNet — stop every local component.
#
# Safe to run on a relay machine, an agent machine, or a combined dev box: it
# skips whatever isn't running.
#
# Usage:  ./launch_scripts/stop_all.sh
#
# Environment overrides:
#   CHAIN_NAME=sentinet   MultiChain chain name
#   KEEP_CHAIN=1          Leave the MultiChain node running

set -u

CHAIN_NAME="${CHAIN_NAME:-sentinet}"

echo ""
echo "Stopping SentiNet services..."
echo ""

stop_service() {
    local name=$1
    local pid_file="/tmp/sentinet_${name}.pid"

    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")
        echo "  Killing $name (PID $pid)..."
        # npm/vite spawn children, so take the whole process group down.
        pkill -P "$pid" 2>/dev/null
        kill "$pid" 2>/dev/null
        rm -f "$pid_file"
    else
        echo "  $name is not running."
    fi
}

# ─── 1. Node processes (dashboards) and the FastAPI relay ───────────────────
stop_service "admin_backend"
stop_service "admin_dashboard"
stop_service "tray_app"
stop_service "agent_dashboard"

# Sweep up anything started outside these scripts (e.g. run by hand).
pkill -f "admin-backend/main.py" 2>/dev/null
pkill -f "sentinet_tray.py"      2>/dev/null

# ─── 2. Privileged daemon ───────────────────────────────────────────────────
if pgrep -f "sentinet_daemon.py" >/dev/null 2>&1; then
    echo "  Killing agent daemon (requires sudo)..."
    sudo pkill -f "sentinet_daemon.py"
    sleep 1
    # The daemon runs as root, so a declined or failed sudo prompt leaves it
    # alive — and it reconnects to the next relay with its old state.
    if pgrep -f "sentinet_daemon.py" >/dev/null 2>&1; then
        echo "  Agent daemon did not exit — forcing it..."
        sudo pkill -9 -f "sentinet_daemon.py"
        sleep 1
    fi
    if pgrep -f "sentinet_daemon.py" >/dev/null 2>&1; then
        echo "  WARNING: agent daemon is STILL running. Run: sudo pkill -9 -f sentinet_daemon.py"
    fi
else
    echo "  Agent daemon is not running."
fi

# ─── 3. MultiChain node ─────────────────────────────────────────────────────
if [ "${KEEP_CHAIN:-0}" = "1" ]; then
    echo "  Leaving MultiChain node running (KEEP_CHAIN=1)."
elif command -v multichain-cli >/dev/null 2>&1; then
    if multichain-cli "$CHAIN_NAME" getinfo >/dev/null 2>&1; then
        echo "  Stopping MultiChain node '$CHAIN_NAME'..."
        multichain-cli "$CHAIN_NAME" stop >/dev/null 2>&1
        # multichaind flushes its wallet on shutdown; give it a moment.
        sleep 2
    else
        echo "  MultiChain node '$CHAIN_NAME' is not running."
    fi
else
    echo "  multichain-cli not on PATH — skipping chain shutdown."
fi

echo ""
echo "All SentiNet services stopped."
echo ""
