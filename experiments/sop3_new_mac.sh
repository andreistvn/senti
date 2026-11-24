#!/bin/sh
# SOP 3, attacker VM only: give the attacker a fresh MAC for each trial while
# keeping its IP, so no DHCP lease is taken and the relay and agents need no
# restart (the previous trial's MAC stays blacklisted; the new one is unknown).
#
#   sudo ./sop3_new_mac.sh <trial number>   switch to the MAC for that trial
#   sudo ./sop3_new_mac.sh restore          original MAC, back to DHCP
#
# Trial MACs are locally administered: 02:53:33:00:HH:LL (HH:LL = trial number).

STATE=/var/tmp/sop3_attacker.state

if [ "$(id -u)" != 0 ]; then echo "Run with sudo."; exit 1; fi

set_mac() {
    ip link set dev "$IF" down &&
    ip link set dev "$IF" address "$1" &&
    ip link set dev "$IF" up || { echo "Could not set MAC $1 on $IF."; exit 1; }
}

case "$1" in
restore)
    [ -f "$STATE" ] || { echo "Nothing to restore (no saved state)."; exit 1; }
    . "$STATE"
    set_mac "$MAC"
    nmcli device set "$IF" managed yes
    rm -f "$STATE"
    sleep 5
    echo "Restored:"
    ip -4 -br addr show "$IF"
    ip -br link show "$IF"
    ;;
''|*[!0-9]*)
    echo "usage: sudo $0 <trial number> | restore"; exit 1
    ;;
*)
    N=$(echo "$1" | sed "s/^0*//"); N=${N:-0}
    if [ "$N" -lt 1 ] || [ "$N" -gt 65535 ]; then echo "Trial must be 1-65535."; exit 1; fi

    # First use: remember the real identity and stop NetworkManager doing DHCP.
    if [ ! -f "$STATE" ]; then
        IF=$(ip route show default | awk '{print $5; exit}')
        GW=$(ip route show default | awk '{print $3; exit}')
        [ -n "$IF" ] || { echo "No default route found."; exit 1; }
        MAC=$(cat "/sys/class/net/$IF/address")
        CIDR=$(ip -4 -o addr show dev "$IF" scope global | awk '{print $4; exit}')
        [ -n "$CIDR" ] || { echo "No IPv4 address on $IF."; exit 1; }
        printf 'IF=%s\nGW=%s\nMAC=%s\nCIDR=%s\n' "$IF" "$GW" "$MAC" "$CIDR" > "$STATE"
        nmcli device set "$IF" managed no
    fi
    . "$STATE"

    NEW=$(printf '02:53:33:00:%02x:%02x' $((N / 256)) $((N % 256)))
    set_mac "$NEW"
    ip addr replace "$CIDR" dev "$IF"
    ip route replace default via "$GW" dev "$IF"
    sleep 1
    echo "Trial $N: $IF is $NEW at $CIDR"
    ;;
esac
