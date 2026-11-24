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

# Relay location: the positional argument wins, then SENTINET_RELAY_URL.
#
# There is deliberately NO loopback default. It used to fall back to
# http://localhost:8771, which is only ever correct on the relay machine
# itself — on an agent it means "connect to myself", the connection is refused,
# and the agent never appears on the dashboard. Requiring the address makes that
# mistake impossible instead of quiet.
#
# The argument is checked first so that passing an address always wins: a
# leftover SENTINET_RELAY_URL in the shell used to silently override it.
if [ $# -ge 1 ] && [ -n "$1" ]; then
    case "$1" in
        http://*|https://*) RELAY_URL="$1" ;;
        *)                  RELAY_URL="http://$1:8771" ;;
    esac
    if [ -n "${SENTINET_RELAY_URL:-}" ] && [ "$SENTINET_RELAY_URL" != "$RELAY_URL" ]; then
        echo "Note: ignoring SENTINET_RELAY_URL=$SENTINET_RELAY_URL in favour of the argument."
    fi
elif [ -n "${SENTINET_RELAY_URL:-}" ]; then
    RELAY_URL="$SENTINET_RELAY_URL"
else
    echo ""
    echo "ERROR: no relay address given."
    echo ""
    echo "  Usage: ./launch_scripts/start_agent_node.sh <RELAY-IP>"
    echo "         ./launch_scripts/start_agent_node.sh 192.168.1.4"
    echo ""
    echo "  The relay's start script prints the exact command to use. There is no"
    echo "  default on purpose: assuming localhost makes an agent try to connect to"
    echo "  itself, which fails quietly and leaves it missing from the dashboard."
    echo ""
    echo "  Running everything on one machine for development? Use:"
    echo "      ./launch_scripts/start_all.sh"
    echo ""
    exit 1
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

# ─── Pre-flight: dependencies ───────────────────────────────────────────────
# On a fresh clone these are missing, and without them the tray and dashboard
# die instantly. Catch it here rather than letting them fail into a log file
# nobody reads while the script cheerfully reports success.
MISSING=""

if [ ! -f "$ROOT/tray-app/venv/bin/activate" ]; then
    MISSING="$MISSING
  tray-app/venv is missing. Create it:
      cd tray-app && python3 -m venv --system-site-packages venv && source venv/bin/activate \\
        && pip install -r requirements.txt"
fi

if [ "${SKIP_DASHBOARD:-0}" != "1" ] && [ ! -d "$ROOT/agent-dashboard/node_modules" ]; then
    MISSING="$MISSING
  agent-dashboard/node_modules is missing. Install it:
      cd agent-dashboard && npm install"
fi

if [ -n "$MISSING" ]; then
    echo ""
    echo "ERROR: this machine is missing first-time setup.$MISSING"
    echo ""
    echo "Run those from the repository root, then start the agent again."
    echo "See README.md for the full first-time install."
    exit 1
fi

# shellcheck source=lib_services.sh
source "$ROOT/launch_scripts/lib_services.sh"

start_service() {
    local name=$1 dir=$2 cmd=$3
    local log_file="/tmp/sentinet_${name}.log"

    # An instance left over from an earlier run would keep its port, pushing
    # this one onto a different port than everything else expects.
    stop_service "$name" "$dir" quiet

    echo "      Starting $name (log: $log_file)"
    (
        cd "$ROOT/$dir" || exit 1
        [ -d venv ] && source venv/bin/activate
        eval "$cmd" > "$log_file" 2>&1 &
        echo $! > "/tmp/sentinet_${name}.pid"
    )
}

# Confirm a backgrounded service is still alive; report its log if it isn't.
# Without this a dead tray or dashboard is invisible until you go looking for
# a tray icon that never appeared.
verify_service() {
    local name=$1 label=$2
    local pid_file="/tmp/sentinet_${name}.pid"
    local log_file="/tmp/sentinet_${name}.log"
    local pid=""

    [ -f "$pid_file" ] && pid="$(cat "$pid_file" 2>/dev/null)"

    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "      $label is running."
        return 0
    fi

    echo ""
    echo "ERROR: $label exited immediately. Last lines of $log_file:"
    echo "---"
    tail -n 15 "$log_file" 2>/dev/null || echo "(no log written)"
    echo "---"
    FAILED=1
    return 1
}

# ─── 1. Privileged capture daemon ───────────────────────────────────────────
# Scapy needs raw socket access, so this one runs under sudo. sudo -b detaches it,
# which means we can't capture a usable PID — stop_all.sh pkills it by name.
echo "[2/3] Starting agent daemon (sudo required for Scapy)..."

# A daemon left over from an earlier run keeps its protection state and
# reconnects to the relay by itself, while the tray talks only to the newest
# one — so the dashboard shows an agent the tray says is off. Clear it first.
if pgrep -f "sentinet_daemon.py" >/dev/null 2>&1; then
    echo "      A previous agent daemon is still running — stopping it first."
    sudo pkill -f "sentinet_daemon.py"
    sleep 1
    # One that has already been asked to stop and stalled ignores a second request.
    if pgrep -f "sentinet_daemon.py" >/dev/null 2>&1; then
        sudo pkill -9 -f "sentinet_daemon.py"
        sleep 1
    fi
    if pgrep -f "sentinet_daemon.py" >/dev/null 2>&1; then
        echo "ERROR: could not stop the previous agent daemon. Run: sudo pkill -9 -f sentinet_daemon.py"
        exit 1
    fi
fi

(
    cd "$ROOT/tray-app" || exit 1
    [ -d venv ] && source venv/bin/activate
    # sudo resets the environment and PATH, so pass the relay URL through `env` and
    # resolve python3 to the venv interpreter before privileges are dropped in.
    sudo -b env SENTINET_RELAY_URL="$RELAY_URL" \
        SENTINET_LOG_APPEND="${SENTINET_LOG_APPEND:-}" \
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

# Confirm the daemon actually received the relay address. It runs under sudo,
# which resets the environment, so a passthrough failure here would otherwise
# only show up as "the agent never appears on the dashboard".
DAEMON_TARGET="$(grep -a 'Relay target:' /tmp/sentinet_daemon.log 2>/dev/null | tail -n1 | sed 's/.*Relay target: //')"
if [ -n "$DAEMON_TARGET" ] && [ "$DAEMON_TARGET" != "$RELAY_URL" ]; then
    echo ""
    echo "ERROR: the daemon is using the wrong relay address."
    echo "         started with : $RELAY_URL"
    echo "         daemon using : $DAEMON_TARGET"
    echo ""
    echo "The address did not survive being passed through sudo. The agent would"
    echo "never reach the relay. Stop with ./launch_scripts/stop_all.sh and report"
    echo "this — it is a bug in this script, not in your setup."
    exit 1
elif [ -n "$DAEMON_TARGET" ]; then
    echo "      Daemon is targeting $DAEMON_TARGET"
fi

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

sleep 4

FAILED="${FAILED:-0}"
[ "${SKIP_TRAY:-0}" != "1" ]      && verify_service "tray_app"        "Tray app"
[ "${SKIP_DASHBOARD:-0}" != "1" ] && verify_service "agent_dashboard" "Agent dashboard"

if [ "$FAILED" = "1" ]; then
    echo ""
    echo "The capture daemon is running, but the components above are not."
    echo ""
    echo "Without the tray app you cannot toggle protection ON, and an agent only"
    echo "registers with the relay once protection is enabled — so this machine will"
    echo "never appear on the admin dashboard until this is fixed."
    echo ""
    echo "On a VM or over SSH the usual cause is that the tray needs a desktop"
    echo "session: pystray cannot create a tray icon with no DISPLAY. Run the"
    echo "script from the VM's own desktop rather than an SSH session."
    echo ""
    echo "Stop what did start with: ./launch_scripts/stop_all.sh"
    exit 1
fi

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
