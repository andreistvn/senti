#!/bin/sh
# SOP 2 trial capture (experiment paper Tables 12-14). Run on the victim node (Kali A).
#
#   sudo ./sop2_trial.sh <sentinet|traditional> <trial 1-10> <S2|S3> [minutes, default 10]
#
# Captures every ARP frame at this node's NIC for the trial (ARP has no payload,
# so this is header-only, RA 10173), then saves the system's own decision log
# next to it:
#   sentinet     /tmp/sentinet_blocks.csv        (what Tier 1 / Tier 2 blocked, and when)
#   traditional  /var/log/tidps/alert_csv.txt + blocks.csv   (Snort alerts, blocks)
# Start benign traffic on both Kalis and the attack at the same moment as this.
# Score on the Mac afterwards with experiments/sop2_score.py.

SYSTEM=$1; TRIAL=$2; SCEN=$3; MIN=${4:-10}
case "$SYSTEM" in sentinet|traditional) ;; *) echo "usage: sudo $0 <sentinet|traditional> <trial> <S2|S3> [minutes]"; exit 1;; esac
case "$SCEN" in S2|S3) ;; *) echo "scenario must be S2 or S3"; exit 1;; esac
[ -n "$TRIAL" ] || { echo "trial number missing"; exit 1; }

IF=$(ip route show default | awk '{print $5; exit}')
DIR=$(cd "$(dirname "$0")" && pwd)/sop2_results/${SYSTEM}_T${TRIAL}_${SCEN}
[ -e "$DIR" ] && { echo "$DIR already exists; remove it or use another trial number."; exit 1; }
mkdir -p "$DIR"

if [ "$SYSTEM" = sentinet ]; then
    pgrep -f sentinet_daemon.py >/dev/null || { echo "SentiNet daemon is not running."; exit 1; }
    # A fresh trial starts with an empty blacklist (cold start).
    [ "$(wc -l < /tmp/sentinet_blocks.csv 2>/dev/null)" -le 1 ] 2>/dev/null || {
        echo "WARNING: /tmp/sentinet_blocks.csv already has blocks; reset (flush relay, restart agents) first."; }
else
    pgrep -f "snort -c /etc/snort/tidps.lua" >/dev/null || { echo "Traditional IDPS is not running (tidps.sh start)."; exit 1; }
fi

cat /sys/class/net/$IF/address > "$DIR/victim_mac.txt"
echo "$SYSTEM trial $TRIAL ($SCEN) on $IF for $MIN min -> $DIR"
echo "Start the benign traffic and the attack now."
date +%s%3N > "$DIR/start_ms.txt"
timeout $((MIN * 60)) tcpdump -i "$IF" -n -w "$DIR/arp.pcap" arp 2> "$DIR/tcpdump.log"
date +%s%3N > "$DIR/end_ms.txt"

if [ "$SYSTEM" = sentinet ]; then
    cp /tmp/sentinet_blocks.csv "$DIR/"
else
    cp /var/log/tidps/alert_csv.txt /var/log/tidps/blocks.csv "$DIR/"
fi
chmod -R a+r "$DIR"
tail -2 "$DIR/tcpdump.log"
echo "Trial saved in $DIR. Stop the attack now."
