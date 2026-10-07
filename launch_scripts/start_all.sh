#!/bin/bash
#
# SentiNet — all-in-one launcher (single machine, local testing only)
#
# Runs the relay node and one agent node on this machine. This is the convenience
# path for development; it does NOT demonstrate the decentralized architecture.
# For the POC demo, run start_relay_node.sh and start_agent_node.sh on separate
# machines — see POC_DEMO_GUIDE.md.
#
# Usage:  ./launch_scripts/start_all.sh

set -u

SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "════════════════════════════════════════════════════"
echo " SentiNet — Local Dev Environment (relay + agent)"
echo "════════════════════════════════════════════════════"

# Options (e.g. --attacker <MAC>) are the relay's.
bash "$SCRIPTS/start_relay_node.sh" "$@" || {
    echo "Relay node failed to start — aborting."
    exit 1
}

# Give the relay's Socket.io server a moment before the agent dials in.
sleep 3

bash "$SCRIPTS/start_agent_node.sh" "http://localhost:8771"

echo "════════════════════════════════════════════════════"
echo " All services running on this machine:"
echo "   Admin Dashboard:  http://localhost:5175"
echo "   Agent Dashboard:  http://localhost:5173"
echo "   Admin API:        http://localhost:8771"
echo ""
echo " Stop everything:  ./launch_scripts/stop_all.sh"
echo "════════════════════════════════════════════════════"
echo ""
