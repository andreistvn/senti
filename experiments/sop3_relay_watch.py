#!/usr/bin/env python3
"""SOP 3, Table 24 (Relay Node Offline Sub-Test — Degraded Mode).

Watches one SentiNet agent through its loopback API while you take the relay
offline, attack the node, and bring the relay back. Every row of Table 24 is
measured on this machine; nothing is written down by hand.

    Fell back to Local Detection     protection stayed ON while the agent showed
                                     the relay offline
    Time to detect relay failure     relay stopped answering /health
                                     -> agent shows relay "offline"
    Tier 1 + Tier 2 operational      the attacker was detected and blacklisted
                                     (Tier 2) and frames were dropped (Tier 1)
                                     while the relay was offline
    Cross-node sync active           whether the agent showed the relay online at
                                     any point during the outage (expected: No)
    CPU / RAM during degraded mode   sentinet_daemon.py while the agent showed the
                                     relay offline, measured as in Table 17
                                     (percent of one vCPU; RssAnon + VmSwap)
    Missed detections                1 if the attacker was never blacklisted
                                     during the outage, else 0
    Blacklist retained after recovery  the attacker is still on the blacklist
                                     when you end the trial (after resync)
    Time to resync after restore     relay answers /health again
                                     -> agent shows relay "online"
    Queued reports committed         reports pending during the outage that
                                     drained after resync (count)

The relay's /health is polled every 0.1 s. A change counts only after three
polls in a row agree, so a single dropped request is not mistaken for an
outage. If there are several outages, the longest one is used.

Do NOT restart the agent or delete its database during a trial: that discards
the queued reports and voids the result.

Run on the agent node (sudo so the daemon's /proc files are readable):

    sudo python3 sop3_relay_watch.py --relay 192.168.68.101 --trial 1

Then: (1) wait for "agent relay: None -> online"; (2) stop the relay;
(3) attack this node for about 5 s; (4) restart the relay; (5) once you see
"pending reports: N -> 0", press Ctrl-C. One row is appended to
./sop3_results/Table24_degraded.csv (override with --out).
"""
import argparse
import csv
import json
import os
import statistics
import threading
import time
import urllib.request
from datetime import datetime

PATTERN = "sentinet_daemon.py"
WRAPPERS = {"sudo", "sh", "bash", "dash", "zsh", "stdbuf", "nohup", "timeout"}
TICK = os.sysconf("SC_CLK_TCK")
CONFIRM = 3          # consecutive /health polls needed to call a change


def get(url, timeout=1.5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")
    except Exception:
        return None


def clock():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


# ---- daemon CPU / RAM, same method as sop3_coldstart_resources.py ----
def daemon_pids():
    me = os.getpid()
    pids = []
    for name in os.listdir("/proc"):
        if not name.isdigit() or int(name) == me:
            continue
        try:
            with open(f"/proc/{name}/cmdline", "rb") as f:
                cmd = f.read().replace(b"\0", b" ").decode(errors="replace")
            with open(f"/proc/{name}/comm") as f:
                comm = f.read().strip()
        except OSError:
            continue
        if comm not in WRAPPERS and PATTERN in cmd:
            pids.append(int(name))
    return pids


def cpu_ticks(pid):
    with open(f"/proc/{pid}/stat") as f:
        fields = f.read().rsplit(")", 1)[1].split()
    return int(fields[11]) + int(fields[12])


def private_mb(pid):
    kb = 0
    with open(f"/proc/{pid}/status") as f:
        for line in f:
            if line.startswith(("RssAnon:", "VmSwap:")):
                kb += int(line.split()[1])
    return kb / 1024


class Resources:
    """Accumulates daemon CPU ticks and RAM samples while active."""

    def __init__(self):
        self.prev = {}
        self.ticks = 0
        self.wall = 0.0
        self.ram = []
        self.last = None
        self.ok = True

    def sample(self, active):
        now = time.monotonic()
        total_mb = 0.0
        try:
            for pid in daemon_pids():
                t = cpu_ticks(pid)
                if active and pid in self.prev:
                    self.ticks += t - self.prev[pid]
                self.prev[pid] = t
                total_mb += private_mb(pid)
        except OSError:
            self.ok = False
            return
        if active and self.last is not None:
            self.wall += now - self.last
            if total_mb:
                self.ram.append(total_mb)
        self.last = now if active else None

    def result(self):
        if not self.ok or self.wall <= 0:
            return None, None
        return (self.ticks / TICK / self.wall * 100,
                statistics.mean(self.ram) if self.ram else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--relay", required=True,
                    help="relay IP or URL (e.g. 192.168.68.101 or http://192.168.68.101:8771)")
    ap.add_argument("--attacker", default="d6:25:89:a3:42:63", help="attacker MAC")
    ap.add_argument("--api", default="http://127.0.0.1:8770",
                    help="agent loopback API base (default http://127.0.0.1:8770)")
    ap.add_argument("--trial", type=int, default=0, help="trial number for the row")
    ap.add_argument("--out", default="sop3_results")
    a = ap.parse_args()

    attacker = a.attacker.lower()
    relay_base = a.relay if a.relay.startswith("http") else f"http://{a.relay}:8771"
    health_url = f"{relay_base.rstrip('/')}/health"
    status_url = f"{a.api}/api/status"
    stats_url = f"{a.api}/api/stats"

    if get(status_url) is None:
        raise SystemExit(f"No agent API at {status_url}. Is the agent (tray) running on this node?")
    if get(health_url, timeout=1.0) is None:
        raise SystemExit(f"The relay is not answering {health_url}. Start it before the trial.")
    if not daemon_pids():
        print("WARNING: sentinet_daemon.py not found in /proc; CPU/RAM will be blank.")

    # ---- relay health poller (own thread, 0.1 s, debounced) ----
    lock = threading.Lock()
    outages = []                      # [down_at, up_at or None]
    hstate = {"up": True, "streak": 0, "first": None}
    stop = threading.Event()

    def poll_relay():
        while not stop.is_set():
            ok = get(health_url, timeout=0.3) is not None
            now = time.monotonic()
            with lock:
                if ok == hstate["up"]:
                    hstate["streak"], hstate["first"] = 0, None
                else:
                    if hstate["streak"] == 0:
                        hstate["first"] = now
                    hstate["streak"] += 1
                    if hstate["streak"] >= CONFIRM:
                        hstate["up"] = ok
                        if ok:
                            if outages and outages[-1][1] is None:
                                outages[-1][1] = hstate["first"]
                            print(f"  [{clock()}] RELAY answering /health again")
                        else:
                            outages.append([hstate["first"], None])
                            print(f"  [{clock()}] RELAY stopped answering /health")
                        hstate["streak"], hstate["first"] = 0, None
            stop.wait(0.1)

    threading.Thread(target=poll_relay, daemon=True).start()

    print("Watching. Sequence: wait for agent ONLINE, stop the relay, attack this node ~5 s, "
          "restart the relay, wait for 'pending reports: N -> 0', then Ctrl-C.\n")

    res = Resources()
    agent_relay = None
    offline_at = []                   # agent online->offline instants
    online_at = []                    # agent offline->online instants
    protected_all_offline = None
    online_during_outage = False
    last_pending = None
    max_pending = 0
    final_pending = 0
    in_blacklist_at_offline = None
    blacklisted_while_offline = False
    in_blacklist_now = False
    dropped_at_offline = None
    dropped_while_offline = 0

    try:
        while True:
            st = get(status_url) or {}
            stt = get(stats_url) or {}
            now = time.monotonic()
            cur = st.get("relay")
            protected = st.get("protected")
            pending = (stt.get("bayanihan") or {}).get("pending", 0) or 0
            dropped = stt.get("dropped")
            macs = {(e.get("mac") or "").lower() for e in (stt.get("blacklist") or [])
                    if isinstance(e, dict)}
            in_blacklist_now = attacker in macs

            if last_pending is not None and pending != last_pending:
                print(f"  [{clock()}] pending reports: {last_pending} -> {pending}")
            last_pending = pending
            final_pending = pending

            if cur is not None and cur != agent_relay:
                print(f"  [{clock()}] agent relay: {agent_relay} -> {cur}  "
                      f"(protected={protected}, pending={pending}, attacker blacklisted={in_blacklist_now})")
                if agent_relay == "online" and cur == "offline":
                    offline_at.append(now)
                    if in_blacklist_at_offline is None:
                        in_blacklist_at_offline = in_blacklist_now
                    dropped_at_offline = dropped
                elif agent_relay == "offline" and cur == "online":
                    online_at.append(now)
                agent_relay = cur

            offline = cur == "offline"
            res.sample(offline)
            if offline:
                max_pending = max(max_pending, pending)
                protected_all_offline = bool(protected) if protected_all_offline is None \
                    else (protected_all_offline and bool(protected))
                if in_blacklist_now and not in_blacklist_at_offline:
                    blacklisted_while_offline = True
                if dropped is not None and dropped_at_offline is not None:
                    dropped_while_offline = max(dropped_while_offline, dropped - dropped_at_offline)

            # Sync is "active" during the outage only if the agent still shows the
            # relay online well after the relay stopped answering (detection
            # took 0.1-0.6 s in earlier trials, so 3 s is a safe margin).
            with lock:
                if (cur == "online" and not hstate["up"] and outages
                        and outages[-1][1] is None and now - outages[-1][0] > 3.0):
                    online_during_outage = True

            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()

    with lock:
        done = [o for o in outages if o[1] is not None]
    main_out = max(done, key=lambda o: o[1] - o[0]) if done else None

    detect = resync = outage = None
    if main_out:
        down, up = main_out
        outage = up - down
        offs = [t for t in offline_at if t >= down - 0.5]
        ons = [t for t in online_at if t >= up]
        detect = (offs[0] - down) if offs else None
        resync = (ons[0] - up) if ons else None

    cpu, ram = res.result()
    tiers = "Yes" if (blacklisted_while_offline and dropped_while_offline > 0) else (
        "Tier 2 only" if blacklisted_while_offline else "No / not observed")
    missed = 0 if blacklisted_while_offline else 1
    retained = "Yes" if in_blacklist_now else "No"
    committed = max(0, max_pending - final_pending)
    sync_active = "Yes" if online_during_outage else "No"
    fell_back = "Yes" if protected_all_offline else "No"

    notes = []
    if main_out is None:
        notes.append("no complete relay outage observed")
    if not offline_at:
        notes.append("agent never showed offline")
    if not online_at:
        notes.append("agent never showed online again")
    if in_blacklist_at_offline:
        notes.append("attacker was already blacklisted before the outage")
    if max_pending == 0:
        notes.append("no reports queued")
    if final_pending:
        notes.append(f"{final_pending} still pending at Ctrl-C")
    if len(done) > 1:
        notes.append(f"{len(done)} outages seen, longest used")
    if cpu is None:
        notes.append("CPU/RAM unreadable (run with sudo)")

    def s(x, fmt="{:.2f}"):
        return "" if x is None else fmt.format(x)

    print("\n--- Table 24 observations (this agent) ---")
    print(f"  Fell back to Local Detection Mode:          {fell_back}")
    print(f"  Time to detect relay failure:               {s(detect) or 'not observed'} s")
    print(f"  Tier 1 + Tier 2 operational while offline:  {tiers} "
          f"(Tier-1 drops while offline: {dropped_while_offline})")
    print(f"  Cross-node synchronization active:          {sync_active}")
    print(f"  CPU during degraded mode:                   {s(cpu) or 'n/a'} % of one vCPU")
    print(f"  RAM during degraded mode:                   {s(ram, '{:.1f}') or 'n/a'} MB")
    print(f"  Missed detections while offline:            {missed}")
    print(f"  Blacklist retained after recovery:          {retained}")
    print(f"  Time to resync after relay restored:        {s(resync) or 'not observed'} s")
    print(f"  Queued reports committed after resync:      {committed} of {max_pending}")
    print(f"  Relay outage length:                        {s(outage) or 'not observed'} s")
    if notes:
        print(f"  Notes: {'; '.join(notes)}")

    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, "Table24_degraded.csv")
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["trial", "start_time", "fell_back_to_local", "detect_failure_s",
                        "tier1_tier2_operational", "tier1_drops_offline", "cross_node_sync_active",
                        "cpu_percent_degraded", "ram_mb_degraded", "missed_detections",
                        "blacklist_retained", "resync_after_restore_s",
                        "queued_committed", "queued_total", "relay_outage_s", "notes"])
        trial = a.trial or (sum(1 for _ in open(path)) if not new else 1)
        w.writerow([trial, datetime.now().strftime("%H:%M:%S"), fell_back, s(detect),
                    tiers, dropped_while_offline, sync_active, s(cpu), s(ram, "{:.1f}"),
                    missed, retained, s(resync), committed, max_pending, s(outage),
                    "; ".join(notes)])
    print(f"\nRow appended to {path}")


if __name__ == "__main__":
    main()
