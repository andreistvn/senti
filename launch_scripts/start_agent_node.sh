#!/bin/bash
#
# SentiNet — Agent Node launcher (Machines 2 & 3)
#
# Starts the endpoint side of the system:
#   1. sentinet_daemon.py  — privileged Scapy capture + Tier 1/2 engines (needs sudo)
#   2. sentinet_tray.py    — tray UI, also serves the loopback API on :8770
#   3. agent-dashboard     — Vite UI, reads that loopback API
#
# Usage:  ./launch_scripts/start_agent_node.sh <RELAY_IP>
#         ./launch_scripts/start_agent_node.sh 192.168.10.10
#         ./launch_scripts/start_agent_node.sh            # defaults to localhost
#
# Environment overrides:
#   SENTINET_RELAY_URL=http://host:8771   Full relay URL (wins over the argument)
#   SKIP_TRAY=1                           Headless box with no GUI for pystray
#   SKIP_DASHBOARD=1                      Daemon only

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Relay location: explicit env var > positional arg > loopback.
if [ -n "${SENTINET_RELAY_URL:-}" ]; then
    RELAY_URL="$SENTINET_RELAY_URL"
elif [ $# -ge 1 ]; then
    case "$1" in
        http://*|https://*) RELAY_URL="$1" ;;
        *)                  RELAY_URL="http://$1:8771" ;;
    esac
else
    RELAY_URL="http://localhost:8771"
fi
export SENTINET_RELAY_URL="$RELAY_URL"

echo ""
echo "SentiNet — Starting AGENT NODE"
echo "Relay: $RELAY_URL"
echo ""

# Fail fast with a clear message rather than letting the daemon retry silently.
echo "[1/3] Checking relay reachability..."
if curl -s --max-time 4 "$RELAY_URL/health" >/dev/null 2>&1; then
    echo "      Relay is reachable."
else
    echo "      WARNING: $RELAY_URL/health did not respond."
    echo "      Start the relay first, or check the IP and any firewall on port 8771."
    echo "      Continuing anyway — the agent will keep retrying the connection."
fi

start_service() {
    local name=$1 dir=$2 cmd=$3
    local log_file="/tmp/sentinet_${name}.log"

    echo "      Starting $name (log: $log_file)"
    (
        cd "$ROOT/$dir" || exit 1
        [ -d venv ] && source venv/bin/activate
        eval "$cmd" > "$log_file" 2>&1 &
        echo $! > "/tmp/sentinet_${name}.pid"
    )
}

# ─── 1. Privileged capture daemon ───────────────────────────────────────────
# Scapy needs raw socket access, so this one runs under sudo. sudo -b detaches it,
# which means we can't capture a usable PID — stop_all.sh pkills it by name.
echo "[2/3] Starting agent daemon (sudo required for Scapy)..."
(
    cd "$ROOT/tray-app" || exit 1
    [ -d venv ] && source venv/bin/activate
    # sudo resets the environment and PATH, so pass the relay URL through `env` and
    # resolve python3 to the venv interpreter before privileges are dropped in.
    sudo -b env SENTINET_RELAY_URL="$RELAY_URL" \
        "$(command -v python3)" sentinet_daemon.py > /tmp/sentinet_daemon.log 2>&1
)

sleep 2

# Don't claim success if sudo was declined or Scapy failed to bind — that failure
# is otherwise invisible until you wonder why no threats ever appear.
if ! pgrep -f "sentinet_daemon.py" >/dev/null 2>&1; then
    echo ""
    echo "ERROR: the agent daemon is not running. Last lines of /tmp/sentinet_daemon.log:"
    echo "---"
    tail -n 10 /tmp/sentinet_daemon.log 2>/dev/null || echo "(no log written)"
    echo "---"
    echo "Common causes: sudo password declined, or Scapy lacks raw-socket permission."
    echo "Without the daemon there is no packet capture — fix this before demoing."
    exit 1
fi
echo "      Daemon is running."

# ─── 2. Tray app (serves the dashboard's loopback API) ──────────────────────
if [ "${SKIP_TRAY:-0}" != "1" ]; then
    start_service "tray_app" "tray-app" "python3 sentinet_tray.py"
else
    echo "      Skipping tray app (SKIP_TRAY=1) — the agent dashboard will have no data source."
fi

# ─── 3. Agent dashboard ─────────────────────────────────────────────────────
if [ "${SKIP_DASHBOARD:-0}" != "1" ]; then
    echo "[3/3] Starting agent dashboard..."
    start_service "agent_dashboard" "agent-dashboard" "npm run dev"
else
    echo "[3/3] Skipping agent dashboard (SKIP_DASHBOARD=1)."
fi

sleep 3

echo ""
echo "AGENT NODE is up."
echo "   Agent Dashboard:  http://localhost:5173"
echo "   Local tray API:   http://127.0.0.1:8770"
echo "   Reporting to:     $RELAY_URL"
echo ""
echo "   Toggle protection ON from the tray icon, then confirm this agent"
echo "   appears in the relay's Admin Dashboard agent list."
echo ""
echo "   Logs: /tmp/sentinet_*.log     Stop: ./launch_scripts/stop_all.sh"
echo ""
