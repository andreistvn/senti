#!/bin/sh
# SOP 3 clock synchronisation (experiment paper Tables 3 and 18).
# Cross-node Time-to-Block subtracts timestamps taken on different machines, so
# their clocks must agree. Run this ONCE on every VM (both Kalis, the attacker,
# the router VM, and the relay if it is Linux). All sync to the same source.
#
#   sudo ./sop3_setup_chrony.sh [NTP_SERVER]
#
# NTP_SERVER defaults to the LAN gateway (fast and common to every node). Pass a
# pool (e.g. pool.ntp.org) instead if the gateway does not answer NTP.
#
# Read the offset any time with:  chronyc tracking
# The "System time ... of NTP time" line is this host's offset; the paper's
# pairwise offsets (Table 18) are the differences between two hosts' values.

SERVER=${1:-$(ip route show default | awk '{print $3; exit}')}
[ -n "$SERVER" ] || { echo "No NTP server given and no default gateway found."; exit 1; }

if [ "$(id -u)" != 0 ]; then echo "Run with sudo."; exit 1; fi

echo "Installing chrony and syncing to $SERVER ..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq chrony || { echo "apt install chrony failed"; exit 1; }

# One known source for every node, polled often so it converges quickly.
cat > /etc/chrony/sources.d/sentinet.sources <<EOF
server $SERVER iburst minpoll 2 maxpoll 4
EOF
# Keep the distribution defaults too, as a fallback, but ours is preferred.
systemctl enable chrony >/dev/null 2>&1
systemctl restart chrony
chronyc reload sources >/dev/null 2>&1

echo "Forcing an immediate step so the offset starts near zero ..."
chronyc makestep >/dev/null 2>&1
sleep 3
chronyc tracking | grep -E "Reference|System time|Last offset|RMS offset"
echo
echo "Done. Re-run 'chronyc tracking' just before a session and record the"
echo "'System time' offset for each node (Table 18). Keep it well under the"
echo "paper's 1 ms only if you can; over Wi-Fi a few ms is realistic — note the"
echo "actual value rather than forcing it. Cross-node TTB subtracts Kali A's clock"
echo "from Kali B's, so its error is at least the offset between those two nodes."
