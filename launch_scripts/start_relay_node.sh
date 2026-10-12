#!/bin/bash
#
# SentiNet — Relay Node launcher (Machine 1)
#
# Brings up the Tier 3 'Bayanihan' layer:
#   1. MultiChain node (created on first run)
#   2. admin-backend/.env generated from the node's real RPC credentials
#   3. FastAPI relay server
#   4. Admin dashboard (Vite)
#
# Usage:  ./launch_scripts/start_relay_node.sh [--attacker <MAC>[,<MAC>...]]
#
#   --attacker   MAC address of the attack generator for this run. Declares the
#                ground truth for the SOP tab's live confusion matrix: packets
#                from this MAC are attacks, all others are benign. Use the MAC
#                the victims actually see (on the attacker: `ip link show eth0`,
#                or on macOS `ifconfig en1 | grep ether`). Without it the SOP
#                tab shows the model's held-out test set figures only.
#
# Environment overrides:
#   CHAIN_NAME=sentinet     MultiChain chain name
#   BIND_HOST=0.0.0.0       Relay bind address (0.0.0.0 so remote agents can reach it)
#   SKIP_DASHBOARD=1        Start the API only, no Vite dev server

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ATTACKER_MACS="${SOP_ATTACKER_MACS:-}"
while [ $# -gt 0 ]; do
    case "$1" in
        --attacker)
            if [ $# -lt 2 ]; then
                echo "ERROR: --attacker needs a MAC address, e.g. --attacker ce:d6:36:4d:0a:9f"
                exit 1
            fi
            ATTACKER_MACS="$2"; shift 2 ;;
        --attacker=*)
            ATTACKER_MACS="${1#--attacker=}"; shift ;;
        *)
            echo "ERROR: unknown option '$1'."
            echo "Usage: ./launch_scripts/start_relay_node.sh [--attacker <MAC>[,<MAC>...]]"
            exit 1 ;;
    esac
done

# Catch a typo here rather than as a confusion matrix that quietly counts the
# real attacker's packets as false positives.
if [ -n "$ATTACKER_MACS" ]; then
    for mac in $(echo "$ATTACKER_MACS" | tr ',' ' '); do
        if ! echo "$mac" | grep -Eiq '^([0-9a-f]{2}[:-]){5}[0-9a-f]{2}$'; then
            echo "ERROR: '$mac' is not a MAC address (expected the form ce:d6:36:4d:0a:9f)."
            exit 1
        fi
    done
fi
export SOP_ATTACKER_MACS="$ATTACKER_MACS"

CHAIN_NAME="${CHAIN_NAME:-sentinet}"
CHAIN_DIR="$HOME/.multichain/$CHAIN_NAME"
BIND_HOST="${BIND_HOST:-0.0.0.0}"

echo ""
echo "SentiNet — Starting RELAY NODE"
echo "Repository: $ROOT"
if [ -n "$ATTACKER_MACS" ]; then
    echo "Attacker (ground truth for the live confusion matrix): $ATTACKER_MACS"
else
    echo "No --attacker given: the SOP tab will show test-set figures only."
fi
echo ""

# ─── 1. MultiChain node ─────────────────────────────────────────────────────

# The relay is useful without a chain: detection, blacklist broadcast and both
# dashboards work, only the ledger is unavailable. So a missing node degrades
# instead of aborting — set REQUIRE_CHAIN=1 (demo day) to make it fatal.
CHAIN_AVAILABLE=1

if ! command -v multichaind >/dev/null 2>&1; then
    if [ "${REQUIRE_CHAIN:-0}" = "1" ]; then
        echo "ERROR: 'multichaind' not found on PATH and REQUIRE_CHAIN=1."
        echo "       Install MultiChain: https://www.multichain.com/download-community/"
        echo "       (Linux: tar -xvzf multichain-2.3.3.tar.gz && sudo mv multichain-2.3.3/multichain* /usr/local/bin/)"
        exit 1
    fi

    CHAIN_AVAILABLE=0
    echo "┌──────────────────────────────────────────────────────────────────────┐"
    echo "│  WARNING: 'multichaind' not found — starting WITHOUT the ledger.     │"
    echo "├──────────────────────────────────────────────────────────────────────┤"
    echo "│  Tier 1/2 detection and the Tier 3 blacklist broadcast still work.   │"
    echo "│  Chain Status will read DEGRADED and no ledger entries will appear.  │"
    echo "│                                                                      │"

    # Tailor the cause to the platform — the fix is different on each.
    case "$(uname -s):$(uname -m)" in
        Darwin:*)
            echo "│  MultiChain publishes no macOS build (Windows/Linux x86-64 only).    │"
            echo "│  Host the relay on a Windows PC — see WINDOWS_RELAY_SETUP.md.        │"
            ;;
        Linux:x86_64|Linux:amd64)
            echo "│  You're on x86-64 Linux, so MultiChain is supported here — it just   │"
            echo "│  isn't installed yet:                                                │"
            echo "│    wget https://www.multichain.com/download/multichain-2.3.3.tar.gz  │"
            echo "│    tar -xvzf multichain-2.3.3.tar.gz                                 │"
            echo "│    sudo mv multichain-2.3.3/multichain* /usr/local/bin/              │"
            ;;
        Linux:*)
            echo "│  This is $(uname -m) Linux and MultiChain is x86-64 only — there is no     │"
            echo "│  ARM build. Host the relay on a Windows or x86-64 Linux machine      │"
            echo "│  instead — see WINDOWS_RELAY_SETUP.md.                               │"
            ;;
        *)
            echo "│  Install MultiChain, or see WINDOWS_RELAY_SETUP.md.                  │"
            ;;
    esac

    echo "│                                                                      │"
    echo "│  Use REQUIRE_CHAIN=1 to make a missing node a hard error instead.    │"
    echo "└──────────────────────────────────────────────────────────────────────┘"
    echo ""
fi

if [ "$CHAIN_AVAILABLE" = "0" ]; then
    echo "[1/4] Skipping MultiChain node (not installed)."
elif [ ! -f "$CHAIN_DIR/params.dat" ]; then
    echo "[1/4] Chain '$CHAIN_NAME' not found — creating it..."
    multichain-util create "$CHAIN_NAME" || { echo "ERROR: multichain-util create failed."; exit 1; }
else
    echo "[1/4] Chain '$CHAIN_NAME' already exists."
fi

# multichaind refuses to start twice; check for a live RPC first.
if [ "$CHAIN_AVAILABLE" = "0" ]; then
    :
elif multichain-cli "$CHAIN_NAME" getinfo >/dev/null 2>&1; then
    echo "      Node is already running."
else
    echo "      Starting multichaind (daemon)..."
    multichaind "$CHAIN_NAME" -daemon >/tmp/sentinet_multichaind.log 2>&1

    # The daemon forks immediately but the RPC port takes a moment to bind.
    echo -n "      Waiting for RPC to accept connections"
    for _ in $(seq 1 30); do
        if multichain-cli "$CHAIN_NAME" getinfo >/dev/null 2>&1; then
            echo " — up."
            break
        fi
        echo -n "."
        sleep 1
    done

    if ! multichain-cli "$CHAIN_NAME" getinfo >/dev/null 2>&1; then
        echo ""
        echo "ERROR: MultiChain node did not come up. See /tmp/sentinet_multichaind.log"
        exit 1
    fi
fi

# ─── 2. Generate admin-backend/.env from the node's real credentials ────────

CONF_FILE="$CHAIN_DIR/multichain.conf"
PARAMS_FILE="$CHAIN_DIR/params.dat"

if [ "$CHAIN_AVAILABLE" = "0" ]; then
    echo "[2/4] Writing admin-backend/.env with the ledger disabled..."
    MULTICHAIN_ENABLED="false"
    RPC_USER="multichainrpc"
    RPC_PASSWORD="unused-no-node"
    RPC_PORT="4365"
else
    echo "[2/4] Extracting RPC credentials from $CHAIN_DIR..."
    MULTICHAIN_ENABLED="true"

    if [ ! -f "$CONF_FILE" ]; then
        echo "ERROR: $CONF_FILE not found — is the chain initialised?"
        exit 1
    fi

    # multichain.conf holds rpcuser/rpcpassword; the port lives in params.dat as
    # 'default-rpc-port' unless multichain.conf overrides it with 'rpcport'.
    RPC_USER="$(sed -n 's/^[[:space:]]*rpcuser[[:space:]]*=[[:space:]]*//p' "$CONF_FILE" | head -n1)"
    RPC_PASSWORD="$(sed -n 's/^[[:space:]]*rpcpassword[[:space:]]*=[[:space:]]*//p' "$CONF_FILE" | head -n1)"
    RPC_PORT="$(sed -n 's/^[[:space:]]*rpcport[[:space:]]*=[[:space:]]*//p' "$CONF_FILE" | head -n1)"

    if [ -z "$RPC_PORT" ] && [ -f "$PARAMS_FILE" ]; then
        # params.dat lines look like:  default-rpc-port = 4365  # comment
        RPC_PORT="$(sed -n 's/^[[:space:]]*default-rpc-port[[:space:]]*=[[:space:]]*\([0-9]*\).*/\1/p' "$PARAMS_FILE" | head -n1)"
    fi

    RPC_USER="${RPC_USER:-multichainrpc}"
    RPC_PORT="${RPC_PORT:-4365}"

    if [ -z "$RPC_PASSWORD" ]; then
        echo "ERROR: could not read rpcpassword from $CONF_FILE"
        exit 1
    fi

    echo "      rpcuser=$RPC_USER  rpcport=$RPC_PORT  rpcpassword=<hidden>"
fi

ENV_FILE="$ROOT/admin-backend/.env"
ENV_EXAMPLE="$ROOT/admin-backend/.env.example"

if [ -f "$ENV_FILE" ]; then
    cp "$ENV_FILE" "$ENV_FILE.bak"
    echo "      Existing .env backed up to .env.bak"
fi

cp "$ENV_EXAMPLE" "$ENV_FILE"

# Detect this machine's LAN address so agents on other machines know where to
# point, and so the dashboard works when opened over the network.
LAN_IP="$(python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(('8.8.8.8', 80))
    print(s.getsockname()[0])
except Exception:
    print('127.0.0.1')
finally:
    s.close()
" 2>/dev/null || echo 127.0.0.1)"

# Rewrite keys in place via python to avoid sed-escaping the generated password.
ENV_FILE="$ENV_FILE" \
RPC_URL="http://127.0.0.1:$RPC_PORT" \
RPC_USER="$RPC_USER" \
RPC_PASSWORD="$RPC_PASSWORD" \
BIND_HOST="$BIND_HOST" \
LAN_IP="$LAN_IP" \
MULTICHAIN_ENABLED="$MULTICHAIN_ENABLED" \
python3 <<'PY'
import os

path = os.environ['ENV_FILE']
updates = {
    'ADMIN_API_HOST': os.environ['BIND_HOST'],
    'MULTICHAIN_ENABLED': os.environ['MULTICHAIN_ENABLED'],
    'MULTICHAIN_RPC_URL': os.environ['RPC_URL'],
    'MULTICHAIN_RPC_USER': os.environ['RPC_USER'],
    'MULTICHAIN_RPC_PASSWORD': os.environ['RPC_PASSWORD'],
    'ADMIN_CORS_ORIGINS': ','.join([
        'http://localhost:5175', 'http://127.0.0.1:5175',
        'http://localhost:5173', 'http://127.0.0.1:5173',
        f"http://{os.environ['LAN_IP']}:5175", f"http://{os.environ['LAN_IP']}:5173",
    ]),
}

# This file was just reset to .env.example. Carry over the administrator account
# from the previous .env, so a changed ID or password survives a relaunch.
try:
    for old_line in open(path + '.bak').read().splitlines():
        key, sep, value = old_line.strip().partition('=')
        if sep and key.strip() in ('ADMIN_DIGITAL_ID', 'ADMIN_PASSWORD') and value.strip():
            updates[key.strip()] = value.strip()
except OSError:
    pass

lines = open(path).read().splitlines()
seen = set()

for i, line in enumerate(lines):
    stripped = line.strip()
    if not stripped or stripped.startswith('#') or '=' not in stripped:
        continue
    key = stripped.split('=', 1)[0].strip()
    if key in updates:
        lines[i] = f'{key}={updates[key]}'
        seen.add(key)

missing = [k for k in updates if k not in seen]
if missing:
    lines.append('')
    lines.append('# Written by launch_scripts/start_relay_node.sh')
    lines.extend(f'{k}={updates[k]}' for k in missing)

open(path, 'w').write('\n'.join(lines) + '\n')
PY

chmod 600 "$ENV_FILE"
echo "      Wrote $ENV_FILE (contains the RPC password — it is gitignored)"

# The dashboard calls its own origin and Vite proxies /agents, /auth, /ledger
# etc. through to this backend (see admin-dashboard/vite.config.ts). Pointing the
# browser straight at the API on another host would make the request cross-site,
# and the SameSite=Lax session cookie would be dropped - which looks like a login
# that succeeds and then bounces straight back to the login screen.
DASH_ENV="$ROOT/admin-dashboard/.env.local"
if [ -d "$ROOT/admin-dashboard" ]; then
    printf 'VITE_ADMIN_API_BASE_URL=\n' > "$DASH_ENV"
    echo "      Dashboard API: same-origin (proxied by Vite to 127.0.0.1:8771)"
fi

# ─── 3 & 4. Relay server + admin dashboard ──────────────────────────────────

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

echo "[3/4] Starting admin backend (relay)..."
# The relay creates the administrator account itself from ADMIN_DIGITAL_ID /
# ADMIN_PASSWORD in admin-backend/.env — nothing to set up here.
start_service "admin_backend" "admin-backend" "python3 main.py"

if [ "${SKIP_DASHBOARD:-0}" != "1" ]; then
    echo "[4/4] Starting admin dashboard..."
    start_service "admin_dashboard" "admin-dashboard" "npm run dev"
else
    echo "[4/4] Skipping admin dashboard (SKIP_DASHBOARD=1)."
fi

sleep 3

echo ""
echo "RELAY NODE is up."
echo "   Admin API:        http://$LAN_IP:8771  (bound on $BIND_HOST)"

# A machine has one address per interface, and DHCP leases move. Print every
# candidate so a wrong or stale pick is visible here rather than discovered
# later as "the agents never showed up".
OTHER_IPS="$(
    if command -v ipconfig >/dev/null 2>&1; then
        for i in $(ifconfig -l 2>/dev/null); do ipconfig getifaddr "$i" 2>/dev/null; done
    else
        ip -4 -o addr show scope global 2>/dev/null | awk '{split($4,a,"/"); print a[1]}'
    fi | grep -v "^${LAN_IP}$" | tr '\n' ' '
)"
if [ -n "${OTHER_IPS// /}" ]; then
    echo "   Other addresses:  $OTHER_IPS"
    echo "                     (agents must use an address on THEIR subnet)"
fi
echo "   Admin Dashboard:  http://localhost:5175"
if [ "$CHAIN_AVAILABLE" = "1" ]; then
    echo "   MultiChain:       $CHAIN_NAME @ 127.0.0.1:$RPC_PORT"
else
    echo "   MultiChain:       *** DISABLED — no ledger, Chain Status = DEGRADED ***"
fi
echo ""
echo "   Point agent machines at this relay with:"
echo "     ./launch_scripts/start_agent_node.sh $LAN_IP"
echo ""
echo "   Verify the chain: curl -s http://localhost:8771/health"
echo "   Logs: /tmp/sentinet_*.log     Stop: ./launch_scripts/stop_all.sh"
echo ""
