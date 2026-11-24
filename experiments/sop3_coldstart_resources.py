#!/usr/bin/env python3
"""SOP 3, Table 17 (Cold-Start Condition): CPU and RAM of the SentiNet agent
daemon during a cold-start trial.

The 60-trial batch did not record CPU/RAM, and they cannot be reconstructed
afterwards, so this fills only those two columns. Everything else in Table 17
(model load, inference, confidence, pre-block packets, first-detection time)
already comes from /tmp/sentinet_detections.csv.

Measured exactly like the SOP 1 sampler (experiment paper Tables 7-9), straight
from /proc, so the numbers are comparable:
    CPU usage (%)   process CPU time used during the window / wall seconds x100
                    (percent of ONE vCPU, like top), summed over the daemon's
                    processes.
    RAM usage (MB)  RssAnon + VmSwap summed over those processes, mean of the
                    0.25 s samples.

Run on Kali A (the detecting node), as root so every process is readable, at
the moment you launch the attack for the trial:

    sudo python3 sop3_coldstart_resources.py --seconds 15

One row is appended per run to ./sop3_results/Table17_resources.csv (override
with --out). Start the agent fresh (cold start) before each trial, the same way
the detection batch did.
"""
import argparse
import csv
import os
import statistics
import sys
import time
from datetime import datetime

# The agent daemon's process (started under sudo as `python3 sentinet_daemon.py`).
PATTERN = "sentinet_daemon.py"
WRAPPERS = {"sudo", "sh", "bash", "dash", "zsh", "stdbuf", "nohup", "timeout"}
TICK = os.sysconf("SC_CLK_TCK")


def matching_pids(pattern):
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
        if pattern in cmd:
            pids.append(int(name))
    return pids


def cpu_ticks(pid):
    with open(f"/proc/{pid}/stat") as f:
        fields = f.read().rsplit(")", 1)[1].split()
    return int(fields[11]) + int(fields[12])  # utime + stime


def private_mb(pid):
    kb = 0
    with open(f"/proc/{pid}/status") as f:
        for line in f:
            if line.startswith(("RssAnon:", "VmSwap:")):
                kb += int(line.split()[1])
    return kb / 1024


def sample(pattern, seconds, interval=0.25):
    prev = {}
    for pid in matching_pids(pattern):
        try:
            prev[pid] = cpu_ticks(pid)
        except OSError:
            pass
    used = 0.0
    ram = []
    start = time.monotonic()
    next_t = start + interval
    while time.monotonic() - start <= seconds + 1e-3:
        time.sleep(max(0, next_t - time.monotonic()))
        total = 0.0
        for pid in matching_pids(pattern):
            try:
                t = cpu_ticks(pid)
                total += private_mb(pid)
            except OSError:
                continue
            used += t - prev.get(pid, t)
            prev[pid] = t
        if total:
            ram.append(total)
        next_t += interval
    wall = time.monotonic() - start
    cpu_pct = used / TICK / wall * 100 if wall else 0.0
    return cpu_pct, (statistics.mean(ram) if ram else 0.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=float, default=15.0,
                    help="length of the cold-start sampling window (default 15)")
    ap.add_argument("--scenario", choices=["S2", "S3"], default="",
                    help="optional label written into the row")
    ap.add_argument("--out", default="sop3_results")
    a = ap.parse_args()

    if os.geteuid() != 0:
        sys.exit("Run with sudo so the daemon's /proc files are readable.")
    if not matching_pids(PATTERN):
        sys.exit(f"No agent daemon is running (looked for '{PATTERN}'). Start the agent first.")

    print(f"Sampling the agent daemon for {a.seconds:.0f} s — launch the attack now.")
    cpu, ram = sample(PATTERN, a.seconds)

    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, "Table17_resources.csv")
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["trial", "scenario", "timestamp", "window_s",
                        "cpu_percent", "ram_mb"])
        trial = sum(1 for _ in open(path)) if not new else 1
        w.writerow([trial, a.scenario, datetime.now().strftime("%H:%M:%S"),
                    f"{a.seconds:.0f}", f"{cpu:.2f}", f"{ram:.1f}"])
    print(f"Trial {trial}: CPU {cpu:.2f}% of one vCPU, RAM {ram:.1f} MB  ->  {path}")


if __name__ == "__main__":
    main()
