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

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib_services.sh
source "$ROOT/launch_scripts/lib_services.sh"

# ─── 1. Node processes (dashboards) and the FastAPI relay ───────────────────
# Each is found by its command and directory as well as its recorded PID, so
# this also catches instances started by hand or left over from earlier runs.
stop_service "admin_backend"   "admin-backend"
stop_service "admin_dashboard" "admin-dashboard"
stop_service "tray_app"        "tray-app"
stop_service "agent_dashboard" "agent-dashboard"

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

# A daemon that had to be force-killed cannot clean up after itself, which on
# Linux would leave its kernel rules dropping blacklisted MACs indefinitely.
NFT_BIN="$(command -v nft 2>/dev/null || true)"
# Not on an ordinary user's PATH on Debian-family systems.
[ -z "$NFT_BIN" ] && [ -x /usr/sbin/nft ] && NFT_BIN=/usr/sbin/nft
if [ -n "$NFT_BIN" ] && sudo "$NFT_BIN" list table netdev sentinet >/dev/null 2>&1; then
    echo "  Removing leftover SentiNet kernel block rules..."
    sudo "$NFT_BIN" delete table netdev sentinet
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
