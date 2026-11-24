#!/usr/bin/env python3
"""SOP 1 resource sampler (experiment paper Tables 7, 8 and 9).

Measures CPU and RAM of one IDPS's processes on this machine, the same way for
every system, straight from /proc (standard library only, so it runs unchanged
on the Kali agents and the Debian router VM).

  CPU Usage (%)  process CPU time used during the minute / 60 s, x100.
                 Percent of ONE vCPU (like top), summed over the matched processes.
  RAM Usage (MB) private memory = RssAnon + VmSwap from /proc/<pid>/status,
                 summed over the matched processes, mean of 1-second samples.
                 Plain RSS is not used: on a VM under memory pressure it falls
                 as pages are swapped out although the process did not shrink.

Systems (which processes are counted):
  sentinet     sentinet_daemon.py              (the SentiNet Agent Daemon)
  traditional  snort (tidps.lua) + tidps_blocker.py   (per-node ARP layer)
  suricata     suricata                        (gateway layer, router VM)

Usage (run with sudo so every process is readable):
  sudo python3 sop1_sampler.py --system sentinet --idle          # Table 7: 60 s, no traffic
  sudo python3 sop1_sampler.py --system sentinet --scenario S2   # Table 8/9: 10 x 1 min
Start a scenario run at the moment traffic injection begins.
Results go to ./sop1_results/<system>_<scenario>_<date-time>.csv
"""
import argparse
import csv
import os
import statistics
import sys
import time
from datetime import datetime

SYSTEMS = {
    "sentinet": ["sentinet_daemon.py"],
    "traditional": ["/etc/snort/tidps.lua", "tidps_blocker.py"],
    "suricata": ["suricata"],
}
# Launchers whose command line also contains the pattern but do no IDPS work.
WRAPPERS = {"sudo", "sh", "bash", "dash", "zsh", "stdbuf", "nohup", "timeout"}

TICK = os.sysconf("SC_CLK_TCK")


def matching_pids(patterns):
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
        if comm in WRAPPERS:
            continue
        if any(p in cmd for p in patterns):
            pids.append(int(name))
    return pids


def cpu_ticks(pid):
    with open(f"/proc/{pid}/stat") as f:
        # comm may contain spaces; the fields after ')' are fixed.
        fields = f.read().rsplit(")", 1)[1].split()
    return int(fields[11]) + int(fields[12])        # utime + stime


def private_mb(pid):
    """RssAnon + VmSwap in MB: the process's own memory, in RAM or swapped out."""
    kb = 0
    with open(f"/proc/{pid}/status") as f:
        for line in f:
            if line.startswith(("RssAnon:", "VmSwap:")):
                kb += int(line.split()[1])
    return kb / 1024


def sample_minute(patterns, seconds=60):
    """Sample once a second; return (cpu_pct, ram_mb_mean)."""
    prev = {}
    for pid in matching_pids(patterns):
        try:
            prev[pid] = cpu_ticks(pid)
        except OSError:
            pass
    used = 0
    ram = []
    start = time.monotonic()
    next_t = start + 1
    while next_t - start <= seconds + 0.001:
        time.sleep(max(0, next_t - time.monotonic()))
        total = 0.0
        for pid in matching_pids(patterns):
            try:
                t = cpu_ticks(pid)
                total += private_mb(pid)
            except OSError:
                continue
            # A process first seen now only counts from now on.
            used += t - prev.get(pid, t)
            prev[pid] = t
        ram.append(total)
        next_t += 1
    wall = time.monotonic() - start
    return used / TICK / wall * 100, statistics.mean(ram)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--system", required=True, choices=sorted(SYSTEMS))
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--idle", action="store_true", help="Table 7 idle baseline: one 60 s window, no traffic")
    g.add_argument("--scenario", choices=["S1", "S2", "S3"])
    ap.add_argument("--minutes", type=int, default=10)
    ap.add_argument("--out", default="sop1_results")
    a = ap.parse_args()

    patterns = SYSTEMS[a.system]
    if not matching_pids(patterns):
        sys.exit(f"No {a.system} process is running (looked for {patterns}). Start it first.")
    if os.geteuid() != 0:
        print("Warning: not running as root; some processes may be unreadable.")

    scen = "Idle" if a.idle else a.scenario
    windows = 1 if a.idle else a.minutes
    os.makedirs(a.out, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(a.out, f"{a.system}_{scen}_{stamp}.csv")
    print(f"Sampling {a.system} ({scen}) on {os.uname().nodename}: {windows} x 60 s -> {path}")

    cpus, rams = [], []
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Scenario", "Minute", "CPU Usage (%)", "RAM Usage (MB)"])
        for m in range(1, windows + 1):
            cpu, ram = sample_minute(patterns)
            cpus.append(cpu)
            rams.append(ram)
            w.writerow([scen, m, f"{cpu:.3f}", f"{ram:.2f}"])
            f.flush()
            print(f"  {scen} minute {m:2d}: CPU {cpu:7.3f} %   RAM {ram:8.2f} MB")
        if windows > 1:
            w.writerow([scen, "Mean", f"{statistics.mean(cpus):.3f}", f"{statistics.mean(rams):.2f}"])
            w.writerow([scen, "SD", f"{statistics.stdev(cpus):.3f}", f"{statistics.stdev(rams):.2f}"])
            print(f"  Mean: CPU {statistics.mean(cpus):.3f} %   RAM {statistics.mean(rams):.2f} MB")
            print(f"  SD:   CPU {statistics.stdev(cpus):.3f}     RAM {statistics.stdev(rams):.2f}")
    print("Saved", path)


if __name__ == "__main__":
    main()
