#!/bin/bash
#
# SentiNet — agent-side diagnostic.
#
# Answers, in one command, why this machine is not showing up on the admin
# dashboard. Run it ON THE AGENT MACHINE, with the relay's address:
#
#     ./launch_scripts/doctor_agent.sh 192.168.1.50
#
# It checks, in the order the connection actually happens:
#   1. what the daemon believes the relay address is
#   2. whether that address answers plain HTTP  (network reachable?)
#   3. whether the socket.io handshake completes (the transport agents use)
#   4. whether the daemon and tray processes are alive
#   5. whether protection is toggled ON (an agent only registers once it is)
#   6. what the daemon's own log says about the relay
#
# Read-only: it starts and stops nothing.

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ $# -ge 1 ]; then
    case "$1" in
        http://*|https://*) RELAY_URL="$1" ;;
        *)                  RELAY_URL="http://$1:8771" ;;
    esac
elif [ -n "${SENTINET_RELAY_URL:-}" ]; then
    RELAY_URL="$SENTINET_RELAY_URL"
else
    RELAY_URL="http://localhost:8771"
fi

PASS="  [ ok ]"
FAIL="  [FAIL]"
WARN="  [warn]"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo " SentiNet — agent diagnostic"
echo " This machine : $(hostname)"
echo " Relay under test: $RELAY_URL"
echo "════════════════════════════════════════════════════════════════"

# ─── 1. What the daemon actually thinks ─────────────────────────────────────
echo ""
echo "[1] Relay address the daemon is using"
DAEMON_TARGET="$(grep -a 'Relay target:' /tmp/sentinet_daemon.log 2>/dev/null | tail -n1 | sed 's/.*Relay target: //')"
if [ -z "$DAEMON_TARGET" ]; then
    echo "$WARN No 'Relay target:' line in /tmp/sentinet_daemon.log."
    echo "       Either the daemon has not run since this diagnostic was added,"
    echo "       or the log is missing. Restart the agent and re-run."
elif [ "$DAEMON_TARGET" = "$RELAY_URL" ]; then
    echo "$PASS $DAEMON_TARGET"
else
    echo "$FAIL The daemon is using: $DAEMON_TARGET"
    echo "       ...but you are testing: $RELAY_URL"
    echo "       The agent is talking to the wrong relay. Restart it with:"
    echo "         ./launch_scripts/start_agent_node.sh $RELAY_URL"
fi

# ─── 2. Plain HTTP reachability ─────────────────────────────────────────────
echo ""
echo "[2] Is $RELAY_URL reachable at all?"
HTTP_BODY="$(curl -s --max-time 6 "$RELAY_URL/health" 2>/dev/null)"
if echo "$HTTP_BODY" | grep -q '"ok"'; then
    echo "$PASS /health responded: $HTTP_BODY"
    NET_OK=1
else
    NET_OK=0
    echo "$FAIL No response from $RELAY_URL/health"
    HOST="$(echo "$RELAY_URL" | sed -E 's#https?://##; s#:.*##')"
    if ping -c 1 -W 2 "$HOST" >/dev/null 2>&1 || ping -c 1 -t 2 "$HOST" >/dev/null 2>&1; then
        echo "       Host $HOST pings, so the port is the problem:"
        echo "         - firewall on the relay machine blocking TCP 8771"
        echo "         - the relay is not running, or bound to 127.0.0.1 only"
        echo "       On the relay, check it is listening on all interfaces."
    else
        echo "       Host $HOST does not even ping. That is a network problem:"
        echo "         - wrong relay IP (check 'ipconfig'/'ip addr' on the relay)"
        echo "         - different subnets (compare the first three octets)"
        echo "         - router client/AP isolation, or a guest network"
    fi
fi

# ─── 3. socket.io handshake ─────────────────────────────────────────────────
echo ""
echo "[3] Does the socket.io handshake complete?"
if [ "$NET_OK" = "1" ]; then
    HANDSHAKE="$(curl -s --max-time 6 "$RELAY_URL/socket.io/?EIO=4&transport=polling" 2>/dev/null)"
    if echo "$HANDSHAKE" | grep -q '"sid"'; then
        echo "$PASS The relay accepted a socket.io handshake."
        echo "       So the transport the agent uses is working."
    else
        echo "$FAIL HTTP works but socket.io did not hand back a session id."
        echo "       Response was: ${HANDSHAKE:0:120}"
        echo "       Something is proxying or intercepting the connection."
    fi
else
    echo "       Skipped — plain HTTP already failed."
fi

# ─── 4. Local processes ─────────────────────────────────────────────────────
echo ""
echo "[4] Are the agent processes running?"
if pgrep -f "sentinet_daemon.py" >/dev/null 2>&1; then
    echo "$PASS capture daemon"
else
    echo "$FAIL capture daemon is NOT running — nothing will ever register."
fi

if pgrep -f "sentinet_tray.py" >/dev/null 2>&1; then
    echo "$PASS tray app"
else
    echo "$FAIL tray app is NOT running."
    echo "       Without it you cannot toggle protection, and an agent only"
    echo "       registers with the relay once protection is ON."
    echo "       On a VM or over SSH this usually means no desktop session:"
    echo "       pystray cannot create a tray icon with no DISPLAY."
fi

# ─── 5. Is protection actually ON? ──────────────────────────────────────────
echo ""
echo "[5] Is protection toggled ON?"
TRAY_API="$(curl -s --max-time 4 http://127.0.0.1:8770/api/status 2>/dev/null)"
if [ -z "$TRAY_API" ]; then
    echo "$WARN The tray's local API on 127.0.0.1:8770 did not answer."
    echo "       Falling back to the daemon log below."
elif echo "$TRAY_API" | grep -q '"protected"[[:space:]]*:[[:space:]]*true'; then
    echo "$PASS Protection is ON."
else
    echo "$FAIL Protection is OFF. Toggle it from the tray icon or the agent"
    echo "       dashboard — the agent does not connect to the relay until then."
fi

# ─── 6. What the daemon logged about the relay ───────────────────────────────
echo ""
echo "[6] Last relay-connection lines from the daemon"
if [ -f /tmp/sentinet_daemon.log ]; then
    LINES="$(grep -a 'BayanihanClient' /tmp/sentinet_daemon.log 2>/dev/null | tail -n 12)"
    if [ -n "$LINES" ]; then
        echo "$LINES" | sed 's/^/       /'
        echo ""
        if echo "$LINES" | grep -q 'Connected to Relay Node'; then
            echo "$PASS The agent has connected to the relay at least once."
            echo "       If it still is not on the dashboard, check the relay's own"
            echo "       console for a 'Agent registered' line for this machine."
        elif echo "$LINES" | grep -q 'Cannot reach the relay'; then
            echo "$FAIL The agent is failing to connect — the reason is printed above."
        elif echo "$LINES" | grep -q 'Waiting for protection'; then
            echo "$FAIL The agent has never tried to connect: protection was never"
            echo "       toggled ON, or the toggle never reached the daemon."
        fi
    else
        echo "$WARN No BayanihanClient lines yet. Restart the agent so the current"
        echo "       build writes them, then re-run this diagnostic."
    fi
else
    echo "$WARN /tmp/sentinet_daemon.log does not exist — the daemon has not run."
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo " Paste this whole output when asking for help — it covers every"
echo " step between this machine and the relay."
echo "════════════════════════════════════════════════════════════════"
echo ""
