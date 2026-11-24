#!/usr/bin/env python3
"""Find what causes SentiNet's periodic CPU bursts (SOP 1, ~3-4 s of CPU every
~140 s, seen in every scenario including benign S1).

Runs on Kali A with the agent already started and protection ON, no attack.
For --seconds it:
  * logs the daemon's CPU every second, total and per thread, to
    spike_cpu.csv (time, total CPU %, and each busy thread's TID and CPU %)
  * runs py-spy at the same time (if --py-spy is given), writing a
    speedscope profile, spike_profile.json, whose samples are in time order,
    so the burst seconds can be matched to the Python code running in them

    sudo python3 sop1_spike_probe.py --seconds 480 --py-spy ~/.local/bin/py-spy

At the end it prints every second where the daemon used more than --burst
percent of one vCPU, and which threads used it.
"""
import argparse
import csv
import os
import subprocess
import sys
import time
from datetime import datetime

PATTERN = "sentinet_daemon.py"
WRAPPERS = {"sudo", "sh", "bash", "dash", "zsh", "stdbuf", "nohup", "timeout"}
TICK = os.sysconf("SC_CLK_TCK")


def daemon_pid():
    me = os.getpid()
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
        if comm not in WRAPPERS and PATTERN in cmd and "spike_probe" not in cmd:
            return int(name)
    return None


def ticks(path):
    with open(path) as f:
        fields = f.read().rsplit(")", 1)[1].split()
    return int(fields[11]) + int(fields[12])


def thread_ticks(pid):
    out = {}
    for tid in os.listdir(f"/proc/{pid}/task"):
        try:
            t = ticks(f"/proc/{pid}/task/{tid}/stat")
            with open(f"/proc/{pid}/task/{tid}/comm") as f:
                name = f.read().strip()
            out[int(tid)] = (t, name)
        except OSError:
            continue
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=int, default=480)
    ap.add_argument("--py-spy", dest="pyspy", default="", help="path to py-spy (optional)")
    ap.add_argument("--burst", type=float, default=20.0,
                    help="report seconds above this CPU %% of one vCPU (default 20)")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()

    if os.geteuid() != 0:
        sys.exit("Run with sudo (py-spy and /proc of a root process need it).")
    pid = daemon_pid()
    if not pid:
        sys.exit("The agent daemon is not running. Start the agent and turn protection ON first.")
    print(f"Agent daemon PID {pid}. Recording {a.seconds} s. Do not attack; leave the agent alone.")

    os.makedirs(a.out, exist_ok=True)
    spy = None
    if a.pyspy:
        spy = subprocess.Popen([a.pyspy, "record", "--pid", str(pid), "--duration", str(a.seconds),
                                "--rate", "50", "--threads", "--format", "speedscope",
                                "--output", os.path.join(a.out, "spike_profile.json")],
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    start_wall = time.time()
    prev_total = ticks(f"/proc/{pid}/stat")
    prev_thr = thread_ticks(pid)
    prev_t = time.monotonic()
    rows, bursts = [], []
    next_t = prev_t + 1.0
    try:
        while time.monotonic() - prev_t < a.seconds + 5 and len(rows) < a.seconds:
            time.sleep(max(0, next_t - time.monotonic()))
            next_t += 1.0
            now = time.monotonic()
            try:
                total = ticks(f"/proc/{pid}/stat")
                thr = thread_ticks(pid)
            except OSError:
                print("The daemon exited."); break
            dt = now - prev_t if rows else now - prev_t
            cpu = (total - prev_total) / TICK / dt * 100
            busy = []
            for tid, (t, name) in thr.items():
                d = (t - prev_thr.get(tid, (t, name))[0]) / TICK / dt * 100
                if d >= 1.0:
                    busy.append((tid, name, d))
            busy.sort(key=lambda x: -x[2])
            elapsed = time.time() - start_wall
            ts = datetime.now().strftime("%H:%M:%S")
            rows.append([f"{elapsed:.0f}", ts, f"{cpu:.1f}",
                         "; ".join(f"{tid}/{name}:{d:.0f}%" for tid, name, d in busy)])
            if cpu >= a.burst:
                bursts.append(rows[-1])
                print(f"  [{ts}] +{elapsed:.0f}s  CPU {cpu:.0f}%  {rows[-1][3]}")
            prev_total, prev_thr, prev_t = total, thr, now
    except KeyboardInterrupt:
        print("Stopped early.")

    with open(os.path.join(a.out, "spike_cpu.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["elapsed_s", "time", "cpu_percent", "busy_threads (tid/name:cpu%)"])
        w.writerows(rows)

    if spy:
        print("Waiting for py-spy to write its profile...")
        _, err = spy.communicate()
        if spy.returncode != 0:
            print("py-spy reported:", err.decode(errors="replace")[-500:])

    print(f"\n{len(bursts)} burst seconds (>= {a.burst:.0f}% CPU) in {len(rows)} s.")
    print(f"Files: {os.path.join(a.out, 'spike_cpu.csv')}"
          + (f", {os.path.join(a.out, 'spike_profile.json')}" if a.pyspy else ""))
    print(f"Recording started at {datetime.fromtimestamp(start_wall).strftime('%H:%M:%S')}.")


if __name__ == "__main__":
    main()
