#!/usr/bin/env python3
"""SOP 3, Table 23 (Rate of Blocked / Reduced Attacks Across Distributed Nodes).

Runs on Node B (Kali B), the node that receives the blacklist from Node A over
the relay but does not itself detect. For one trial it measures, for attacker
ARP frames arriving at Node B AFTER the broadcast:

    attempts   attacker ARP frames seen at Node B           (every frame, since
               the sniffer is fed ahead of the kernel's drop hook)
    blocked    frames the Tier-1 blacklist dropped in the   (the nft counter on
               kernel                                         table netdev sentinet)
    tier2      attempts - blocked: frames that still reached Tier 2
    block rate blocked / attempts x 100

Because Node A's broadcast reaches Node B before Node B is attacked, the
attacker's MAC is already blacklisted there, so nearly every frame is dropped by
the blacklist and almost none reach Tier 2 — which is exactly what this table is
meant to show.

How it lines up with the attack: it waits for the FIRST attacker ARP frame
(Phase 2 of sop3_attack_ab.py), snapshots the kernel drop counter at that
instant, counts for --window seconds, then snapshots the counter again. So start
this first, then run the attack driver on the attacker.

    sudo python3 sop3_table23_nodeB.py --attacker d6:25:89:a3:42:63 --window 12

One row per run is appended to ./sop3_results/Table23_nodeB.csv (override with
--out). Run as root (the sniffer and nft both need it). Keep the agent running
with protection ON, the same cold-start agent used for the detection trial.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime

from scapy.all import ARP, sniff

NFT_TABLE = "sentinet"
NFT_CHAIN = "ingress"


def nft_dropped():
    """ARP frames the agent's kernel rule has dropped so far, or None."""
    for nft in ("nft", "/usr/sbin/nft", "/sbin/nft"):
        try:
            r = subprocess.run([nft, "-j", "list", "chain", "netdev", NFT_TABLE, NFT_CHAIN],
                               capture_output=True, text=True)
        except FileNotFoundError:
            continue
        if r.returncode != 0:
            return None
        try:
            for item in json.loads(r.stdout).get("nftables", []):
                for expr in item.get("rule", {}).get("expr", []):
                    if "counter" in expr:
                        return int(expr["counter"].get("packets", 0))
        except (ValueError, KeyError):
            return None
        return None
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--attacker", required=True, help="attacker MAC (e.g. d6:25:89:a3:42:63)")
    ap.add_argument("--window", type=float, default=12.0,
                    help="seconds to count once the first attacker frame arrives (default 12)")
    ap.add_argument("--scenario", choices=["S2", "S3"], default="")
    ap.add_argument("--iface", default=None, help="capture interface (default: scapy's default)")
    ap.add_argument("--out", default="sop3_results")
    a = ap.parse_args()

    if os.geteuid() != 0:
        sys.exit("Run with sudo (the sniffer and nft both need root).")
    attacker = a.attacker.lower()
    if nft_dropped() is None:
        print("WARNING: could not read the nft counter on 'table netdev sentinet'.")
        print("         Is the agent running with protection ON on this node? Continuing;")
        print("         'blocked' will be blank if the rule never appears.")

    state = {"count": 0, "before": None, "deadline": None, "started": None}

    def on_pkt(pkt):
        if not pkt.haslayer(ARP):
            return
        if (pkt[ARP].hwsrc or "").lower() != attacker:
            return
        now = time.monotonic()
        if state["before"] is None:
            state["before"] = nft_dropped() or 0
            state["started"] = datetime.now().strftime("%H:%M:%S")
            state["deadline"] = now + a.window
            print(f"First attacker frame seen; counting for {a.window:.0f} s...")
        state["count"] += 1

    def stop(pkt):
        return state["deadline"] is not None and time.monotonic() >= state["deadline"]

    print(f"Waiting for the first ARP frame from {attacker} (start the attack now)...")
    sniff(prn=on_pkt, stop_filter=stop, store=False,
          filter="arp", iface=a.iface, timeout=None)

    if state["before"] is None:
        sys.exit("No attacker frames were seen. Did Phase 2 of the attack run against this node?")

    after = nft_dropped()
    attempts = state["count"]
    blocked = (after - state["before"]) if after is not None else None
    if blocked is not None:
        blocked = max(0, min(blocked, attempts))
        tier2 = max(0, attempts - blocked)
        rate = (blocked / attempts * 100) if attempts else 0.0
    else:
        tier2 = None
        rate = None

    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, "Table23_nodeB.csv")
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["trial", "scenario", "start_time", "window_s",
                        "attempts", "blocked_by_blacklist", "processed_by_tier2",
                        "block_rate_percent", "remarks"])
        trial = sum(1 for _ in open(path)) if not new else 1
        w.writerow([trial, a.scenario, state["started"], f"{a.window:.0f}",
                    attempts,
                    "" if blocked is None else blocked,
                    "" if tier2 is None else tier2,
                    "" if rate is None else f"{rate:.1f}",
                    "nft counter unavailable" if blocked is None else ""])
    print(f"Trial {trial}: attempts {attempts}, blocked {blocked}, "
          f"to Tier 2 {tier2}, block rate {'' if rate is None else f'{rate:.1f}%'}  ->  {path}")


if __name__ == "__main__":
    main()
