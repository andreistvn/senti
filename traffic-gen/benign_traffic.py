"""
Benign background traffic (experiment paper Table 6): web requests, ARP cache
flush and local subnet sweep. Runs alone for S1 and alongside the attack in
S2/S3, so False Positives and True Negatives stay measurable.

Run on each Kali agent, as root (the flush and the sweep need it):
    sudo python3 traffic-gen/benign_traffic.py --minutes 10

  web requests   a random site every 1-5 s (DNS lookup + HTTP GET)
  ARP flush      `ip neigh flush` every --flush-every s, so the host re-resolves
                 its neighbours with ordinary ARP requests
  subnet sweep   one ARP request to every address in the local subnet every
                 --sweep-every s, paced at --sweep-pps (host discovery, as a
                 normal device or tool on the network would do)

Every flush and sweep is printed with a timestamp, for Table 27 and scoring.
"""
import argparse
import ipaddress
import random
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime

import requests

# A list of top websites to simulate normal browsing
SITES = [
    "http://www.google.com",
    "http://www.youtube.com",
    "http://www.facebook.com",
    "http://www.wikipedia.org",
    "http://www.yahoo.com",
    "http://www.reddit.com",
    "http://www.amazon.com",
]

stop = threading.Event()


def log(msg):
    print(f"[BenignTraffic {datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {msg}", flush=True)


def local_network():
    """(interface, own IP, subnet) of the default route."""
    out = subprocess.run(["ip", "-4", "route", "show", "default"],
                         capture_output=True, text=True).stdout.split()
    if "dev" not in out:
        sys.exit("No default route; connect the VM to the network first.")
    iface = out[out.index("dev") + 1]
    addr = subprocess.run(["ip", "-4", "-o", "addr", "show", "dev", iface],
                          capture_output=True, text=True).stdout.split()
    cidr = addr[addr.index("inet") + 1]
    intf = ipaddress.ip_interface(cidr)
    return iface, intf.ip, intf.network


def web_requests():
    while not stop.is_set():
        target = random.choice(SITES)
        try:
            log(f"Browsing {target}")
            hostname = target.replace("http://", "").replace("https://", "").split("/")[0]
            socket.gethostbyname(hostname)
            requests.get(target, timeout=2.0)
            # Simulate a user reading the page (1 to 5 seconds)
            stop.wait(random.uniform(1.0, 5.0))
        except Exception as e:
            log(f"Error accessing {target}: {e}")
            stop.wait(1)


def arp_flush(iface, every):
    while not stop.wait(every):
        subprocess.run(["ip", "neigh", "flush", "dev", iface])
        log(f"ARP cache flushed on {iface}")


def subnet_sweep(iface, own_ip, network, every, pps):
    from scapy.all import ARP, Ether, conf, sendp
    conf.verb = 0
    hosts = [h for h in network.hosts() if h != own_ip]
    while not stop.wait(every):
        log(f"Subnet sweep of {network} started ({len(hosts)} addresses at {pps} pps)")
        for h in hosts:
            if stop.is_set():
                return
            sendp(Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(op=1, pdst=str(h)), iface=iface)
            time.sleep(1.0 / pps)
        log("Subnet sweep finished")


def main():
    ap = argparse.ArgumentParser(description="SentiNet benign background traffic (Table 6)")
    ap.add_argument("--minutes", type=float, default=0, help="stop after this long (0 = until Ctrl+C)")
    ap.add_argument("--flush-every", type=float, default=60, help="seconds between ARP cache flushes")
    ap.add_argument("--sweep-every", type=float, default=120, help="seconds between subnet sweeps")
    ap.add_argument("--sweep-pps", type=float, default=20, help="ARP requests per second during a sweep")
    ap.add_argument("--web-only", action="store_true", help="web requests only (no root needed)")
    a = ap.parse_args()

    log("Starting benign traffic generator...")
    workers = [threading.Thread(target=web_requests, daemon=True)]
    if not a.web_only:
        import os
        if os.geteuid() != 0:
            sys.exit("ARP flush and subnet sweep need root: run with sudo (or use --web-only).")
        iface, own_ip, network = local_network()
        log(f"Interface {iface}, address {own_ip}, subnet {network}")
        workers.append(threading.Thread(target=arp_flush, args=(iface, a.flush_every), daemon=True))
        workers.append(threading.Thread(
            target=subnet_sweep, args=(iface, own_ip, network, a.sweep_every, a.sweep_pps), daemon=True))
    for w in workers:
        w.start()
    try:
        if a.minutes:
            stop.wait(a.minutes * 60)
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    stop.set()
    log("Stopped.")


if __name__ == "__main__":
    main()
