"""
SentiNet Daemon — Root-privileged background process.

This daemon owns all security-critical state: packet capture, the in-memory
blacklist, the ML engine, and the relay connection.  It communicates with the
unprivileged tray process over IPC.

Run with elevated privileges::

    sudo python sentinet_daemon.py

In Phase 2+ this will use Scapy for real packet capture.  For now it runs the
same ``SimulationEngine`` logic to prove the IPC plumbing works end-to-end.
"""

from __future__ import annotations

import os
import random
import signal
import sys
import threading
import time
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import psutil
import scapy.all as scapy

from ml_engine import MLEngine
from bayanihan_client import BayanihanClient

from config import (
    AGENT_VERSION,
    SIM_TICK_SECONDS,
    RELAY_URL,
    FLOOD_PPS_THRESHOLD,
    SCENARIO_WINDOW_SECONDS,
)
from ipc_protocol import (
    IpcServer,
    MSG_BLACKLIST_UPDATE,
    MSG_EVENT_NEW,
    MSG_HEALTH_UPDATE,
    MSG_STATE_UPDATE,
    MSG_TOGGLE_ACK,
    MSG_TOGGLE_REQUEST,
)

# ── Constants ──────────────────────────────────────────────────────────────────

THREAT_LABELS = [
    "ARP Spoofing",
    "MITM Attempt",
    "Malicious ARP Reply",
    "Rogue Gateway Probe",
    "ARP Cache Poisoning",
]

DAEMON_SERVICES = [
    {"id": "scapy",     "name": "Scapy Sniffer",    "status": "active",    "detail": "Capturing ARP frames on wlan0",      "uptime": "0m 0s"},
    {"id": "ml",        "name": "Tier-2 ML Engine",  "status": "loaded",    "detail": "RandomForest model v3.1 in memory",  "uptime": "0m 0s"},
    {"id": "ws",        "name": "WebSocket Relay",   "status": "connected", "detail": "relay.dict.gov.ph:8443 · 12ms ping", "uptime": "0m 0s"},
    {"id": "chain",     "name": "Blockchain Sync",   "status": "active",    "detail": "Block #49,812 · 94% synced",         "uptime": "0m 0s"},
    {"id": "arp",       "name": "ARP Guard Module",  "status": "active",    "detail": "Monitoring 34 active hosts",         "uptime": "0m 0s"},
    {"id": "bayanihan", "name": "Bayanihan Agent",   "status": "connected", "detail": "Peer mesh: 40 nodes reachable",      "uptime": "0m 0s"},
]


def _random_mac() -> str:
    return ":".join(f"{random.randint(0, 255):02X}" for _ in range(6))


def _fmt_uptime(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


# ── Daemon State ───────────────────────────────────────────────────────────────

class DaemonState:
    """Authoritative state container, owned exclusively by the daemon."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.protected: bool = False
        self.started_at: float = time.time()
        self.protected_since: Optional[float] = None

        # Traffic counters
        self.inspected: int = 0
        self.dropped: int = 0
        self.passed: int = 0
        self.blocked: int = 0

        # Telemetry
        self.cpu: float = 4.0
        self.memory: int = 84          # system-wide percent, for the gauge
        self.memory_mb: float = 0.0    # this process's RSS in MB (what the paper wants)
        # Traffic scenario this agent is currently experiencing — "normal",
        # "poisoning" or "flooding". Set by TelemetryEngine; labels each reading.
        self.scenario: str = "normal"

        # Bayanihan
        self.sig_contributions: int = 0

        # Detection log (most recent first)
        self.events: deque = deque(maxlen=50)
        self.last_threat: Optional[Dict[str, str]] = None

        # Blacklist (Phase 2+)
        # Tier 1 keeps a plain set for O(1) membership, as specified in Ch.3.
        # blacklist_meta carries the display detail in parallel.
        self.blacklist: Set[str] = set()
        self.blacklist_meta: Dict[str, Dict[str, str]] = {}

        # This node's own identity, filled in by SentiNetDaemon once detected.
        # The agent dashboard header used to print a hardcoded address.
        self.hostname: str = ""
        self.ip: str = ""
        self.mac: str = ""

        # Change listeners
        self._on_change: List = []

    def add_to_blacklist(self, mac: str, origin: str = "local",
                         attack_type: str = "Unknown", confidence: str = "N/A",
                         reported_by: Optional[str] = None) -> bool:
        """
        Add a MAC to the Tier-1 filter. Returns True if it was not already there.

        `origin` records whether this node detected it itself or received it from
        the relay. That distinction is the visible evidence of the Bayanihan
        layer: an agent that was never attacked should show entries marked
        "relay", proving the intelligence came from another node. `reported_by`
        names which agent originally reported it, for relay-origin entries.

        `tier1Reported` tracks whether a *subsequent* Tier-1 hit on this MAC has
        already been surfaced once (see CaptureEngine._process_packet) — without
        it, every dropped packet from an already-blacklisted MAC would otherwise
        re-report, which is exactly the flood Tier 1 exists to avoid.
        """
        with self._lock:
            is_new = mac not in self.blacklist
            self.blacklist.add(mac)
            if mac not in self.blacklist_meta:
                self.blacklist_meta[mac] = {
                    "mac": mac,
                    "addedAt": datetime.now().strftime("%H:%M:%S"),
                    "origin": origin,
                    "attackType": attack_type,
                    "confidence": confidence,
                    "reportedBy": reported_by,
                    "tier1Reported": False,
                }
            return is_new

    def mark_blacklist_reported(self, mac: str) -> bool:
        """
        Mark a MAC's repeat/Bayanihan block as surfaced. Returns True only the
        first time this is called for a given MAC, False on every call after —
        that's what turns a sustained flood from one already-known MAC into a
        single log line instead of one per dropped packet.
        """
        with self._lock:
            meta = self.blacklist_meta.get(mac)
            if meta is None or meta.get("tier1Reported"):
                return False
            meta["tier1Reported"] = True
            return True

    def remove_from_blacklist(self, mac: str) -> None:
        with self._lock:
            self.blacklist.discard(mac)
            self.blacklist_meta.pop(mac, None)

    def is_blacklisted(self, mac: str) -> bool:
        # thread-safe enough for check, but using lock for strictness
        with self._lock:
            return mac in self.blacklist

    def events_tail(self, n: int = 20) -> List[Dict[str, Any]]:
        """
        The `n` most recent local detections, for BayanihanClient to offer the
        relay as a register_agent backfill. This is independent of whether each
        one's report was actually delivered — it's a cross-check against this
        agent's own display log, catching the case where a detection somehow
        never made it into the pending-report queue at all (a bug, or one
        logged before that queue existed), not just a slow/retrying delivery.
        """
        with self._lock:
            return list(self.events)[:n]

    def on_change(self, callback):
        self._on_change.append(callback)

    def _notify(self):
        for cb in list(self._on_change):
            try:
                cb()
            except Exception:
                pass

    def set_protected(self, value: bool) -> bool:
        with self._lock:
            value = bool(value)
            if value == self.protected:
                return self.protected
            self.protected = value
            self.protected_since = time.time() if value else None
        self._notify()
        return value

    def toggle(self) -> bool:
        return self.set_protected(not self.protected)

    def is_protected(self) -> bool:
        with self._lock:
            return self.protected

    def snapshot(self) -> Dict[str, Any]:
        """Build a full state snapshot for IPC STATE_UPDATE messages."""
        with self._lock:
            since = None
            if self.protected_since:
                since = datetime.fromtimestamp(self.protected_since).isoformat()

            return {
                "status": {
                    "protected": self.protected,
                    "relay": "online" if self.protected else "offline",
                    "version": AGENT_VERSION,
                    "since": since,
                },
                "stats": {
                    "inspected": self.inspected,
                    "dropped": self.dropped,
                    "passed": self.passed,
                    "blocked": self.blocked,
                    "cpu": round(self.cpu, 1),
                    "memory": self.memory,
                    "memoryMb": round(self.memory_mb, 1),
                    "scenario": self.scenario,
                    "bayanihan": {
                        "contributions": self.sig_contributions,
                    },
                    "lastThreat": self.last_threat,
                    "protected": self.protected,
                },
                "blacklist": list(self.blacklist_meta.values()),
                "identity": {
                    "hostname": self.hostname,
                    "ip": self.ip,
                    "mac": self.mac,
                },
                "events": list(self.events),
                "services": self._health_list(),
            }

    def _health_list(self) -> List[Dict[str, str]]:
        up = _fmt_uptime(time.time() - self.started_at)
        services = []
        for svc in DAEMON_SERVICES:
            s = dict(svc)
            if not self.protected and s["id"] in ("scapy", "arp"):
                s["status"] = "offline"
                s["detail"] = "Idle — protection disabled"
                s["uptime"] = "0s"
            else:
                s["uptime"] = up
            services.append(s)
        return services


# ── Engines (Phase 2: Capture & Telemetry) ────────────────────────────────────

class CaptureEngine(threading.Thread):
    """Background thread that captures network traffic using Scapy.
    
    Implements Tier-1 Fast-Filter: Drops packets instantly if the source MAC
    is in the in-memory blacklist.
    Tier-2 Detective: For unknown MACs, evaluates via MLEngine.
    """

    def __init__(self, state: DaemonState, ml_engine: MLEngine, bayanihan_client: BayanihanClient) -> None:
        super().__init__(daemon=True, name="capture-engine")
        self.state = state
        self.ml_engine = ml_engine
        self.bayanihan_client = bayanihan_client
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                # We filter for ARP since this is an ARP-spoofing IDPS proof-of-concept
                scapy.sniff(
                    filter="arp",
                    prn=self._process_packet,
                    store=False,
                    stop_filter=lambda _: self._stop.is_set()
                )
            except Exception as e:
                print(f"[CaptureEngine] Sniffing failed or interrupted: {e}")
                time.sleep(1) # Prevent tight crash loops if interface goes down

    def _process_packet(self, pkt) -> None:
        # If protection is off, we don't inspect.
        if not self.state.is_protected():
            return
            
        with self.state._lock:
            self.state.inspected += 1

        if scapy.Ether in pkt and scapy.ARP in pkt:
            src_mac = pkt[scapy.Ether].src
            op = pkt[scapy.ARP].op
            src_ip = pkt[scapy.ARP].psrc
            dst_ip = pkt[scapy.ARP].pdst
            
            # Tier 1: Fast-Filter O(1) lookup
            if self.state.is_blacklisted(src_mac):
                with self.state._lock:
                    self.state.blocked += 1
                    self.state.dropped += 1
                    # Ceasing processing simulates a block.

                # Surface this once per MAC — the visible proof that either this
                # agent's own earlier detection (Tier 1) or another agent's
                # report relayed through Bayanihan (Tier 3) is now protecting
                # this machine. Gated behind mark_blacklist_reported so a
                # sustained flood from one MAC produces one log line, not one
                # per dropped packet.
                if self.state.mark_blacklist_reported(src_mac):
                    meta = self.state.blacklist_meta.get(src_mac, {})
                    added_at = meta.get("addedAt", datetime.now().strftime('%H:%M:%S'))

                    if meta.get("origin") == "relay":
                        tier_label = "Tier 3"
                        reporter = meta.get("reportedBy") or "another agent"
                        detail = f"blocked via Bayanihan, reported by {reporter} at {added_at}"
                    else:
                        tier_label = "Tier 1"
                        detail = f"repeat block, first flagged locally at {added_at}"

                    event_id = len(self.state.events) + 1
                    threat_event = {
                        "id": event_id,
                        # Stable across retries/backfills — see bayanihan_client.py
                        # and admin-backend state.add_threat()'s dedupe on it.
                        "clientEventId": str(uuid.uuid4()),
                        "timestamp": datetime.now().strftime('%H:%M:%S'),
                        "sourceMac": src_mac,
                        "attackType": meta.get("attackType", "Unknown"),
                        "tier": tier_label,
                        "action": "Blocked",
                        "confidence": meta.get("confidence", "N/A"),
                        "detail": detail,
                    }

                    with self.state._lock:
                        self.state.events.appendleft(threat_event)
                        self.state.last_threat = threat_event

                    self.bayanihan_client.send_attack_report(threat_event)
                return
            
            # If not blacklisted, it passes Tier 1. Proceed to Tier 2 ML logic.
            with self.state._lock:
                self.state.passed += 1

            # Tier 2: Stateful ML Engine evaluation
            score = self.ml_engine.process_packet(src_mac, op, src_ip, dst_ip)
            
            if score >= 0.50:
                # t_detected in Chapter 3's Time-to-Block formula: the moment
                # Tier 2 first classifies this MAC as malicious. Taken before
                # anything else so logging and bookkeeping don't inflate it.
                detected_at_ms = int(time.time() * 1000)
                print(f"[Tier 2] THREAT DETECTED: {src_mac} (Score: {score:.2f})")
                # Generate Attack Report format
                event_id = len(self.state.events) + 1
                now = datetime.now()
                threat_event = {
                    "id": event_id,
                    "clientEventId": str(uuid.uuid4()),
                    "timestamp": now.strftime('%H:%M:%S'),
                    "sourceMac": src_mac,
                    "attackType": "ARP Spoofing" if score > 0.8 else "Anomalous ARP",
                    "tier": "Tier 2",
                    "action": "Blocked",
                    "confidence": f"{score*100:.1f}%",
                    "detectedAtMs": detected_at_ms,
                }

                self.state.add_to_blacklist(
                    src_mac,
                    origin="local",
                    attack_type=threat_event["attackType"],
                    confidence=threat_event["confidence"],
                )
                
                with self.state._lock:
                    self.state.events.appendleft(threat_event)
                    self.state.last_threat = threat_event
                    
                # Send to Relay Node via Bayanihan Layer. Count it: this is the
                # agent's contribution to the shared ledger, and the counter used
                # to be initialised to 0 and never incremented, so the dashboard
                # reported "0 signatures" no matter how many threats were shared.
                self.bayanihan_client.send_attack_report(threat_event)
                with self.state._lock:
                    self.state.sig_contributions += 1

class TelemetryEngine(threading.Thread):
    """
    Tracks this daemon's own CPU and memory consumption.

    Chapter 3 defines resource consumption as "CPU usage (%) and RAM consumption
    (MB)". Two corrections against what this used to do:

    * It measured psutil.cpu_percent() and virtual_memory().percent, which are
      machine-wide. The hypothesis is that SentiNet uses less CPU than a
      traditional IDPS, so the reading has to be attributable to SentiNet — a
      machine-wide figure also counts the browser, the dashboards and VM
      overhead. It now measures this process.
    * RAM was reported as a percentage. The paper specifies megabytes, so RSS in
      MB is now the primary figure; the system-wide percentage is kept alongside
      it purely for the existing gauge in the agent dashboard.
    """

    def __init__(self, state: DaemonState, bayanihan_client: BayanihanClient) -> None:
        super().__init__(daemon=True, name="telemetry-engine")
        self.state = state
        self.bayanihan_client = bayanihan_client
        self._stop = threading.Event()
        self._proc = psutil.Process()
        # psutil's first cpu_percent() call returns 0.0 because it has no earlier
        # sample to compare against. Prime it so the first real reading counts.
        self._proc.cpu_percent(None)
        # (time, blocked counter) samples spanning SCENARIO_WINDOW_SECONDS.
        self._blocked_samples: deque = deque()

    def stop(self) -> None:
        self._stop.set()

    def _classify_scenario(self) -> str:
        """
        Which of the paper's three traffic scenarios this agent is in right now.

        Judged from the rate at which Tier 1 is dropping attack packets, averaged
        over a short window so a single stray drop or a momentary gap in a flood
        doesn't flip the label back and forth.
        """
        now = time.time()
        with self.state._lock:
            blocked = self.state.blocked
        self._blocked_samples.append((now, blocked))
        while len(self._blocked_samples) > 2 and (now - self._blocked_samples[0][0]) > SCENARIO_WINDOW_SECONDS:
            self._blocked_samples.popleft()

        t0, b0 = self._blocked_samples[0]
        elapsed = now - t0
        if elapsed <= 0 or blocked <= b0:
            return "normal"
        pps = (blocked - b0) / elapsed
        return "flooding" if pps >= FLOOD_PPS_THRESHOLD else "poisoning"

    def _measure(self) -> tuple:
        """(cpu_percent, rss_mb, system_ram_percent, process_ram_percent) for this process."""
        with self._proc.oneshot():
            cpu = self._proc.cpu_percent(None)
            rss_mb = self._proc.memory_info().rss / (1024 * 1024)
            process_percent = self._proc.memory_percent()
        return (round(cpu, 2), round(rss_mb, 2),
                round(psutil.virtual_memory().percent, 2), round(process_percent, 2))

    def run(self) -> None:
        while not self._stop.is_set():
            time.sleep(SIM_TICK_SECONDS)

            is_protected = self.state.is_protected()
            cpu, ram_mb, ram_percent, ram_process_percent = self._measure()
            scenario = self._classify_scenario()

            # Protection OFF used to report a fabricated 0 for both. The relay now
            # records these readings as research data, so send the real numbers and
            # let the protection flag say whether capture was active — a zero that
            # means "dormant" is indistinguishable from a genuine zero in a dataset.
            with self.state._lock:
                self.state.cpu = cpu
                self.state.memory = ram_percent
                self.state.memory_mb = ram_mb
                self.state.scenario = scenario

            self.bayanihan_client.send_telemetry(
                cpu,
                ram_percent,
                "PROTECTED" if is_protected else "UNPROTECTED",
                ram_mb=ram_mb,
                protected=is_protected,
                scenario=scenario,
                ram_process_percent=ram_process_percent,
            )


# ── Main Daemon ────────────────────────────────────────────────────────────────

class SentiNetDaemon:
    """Orchestrates the daemon's subsystems: state, simulation/capture, IPC."""

    def __init__(self) -> None:
        import socket
        import uuid
        hostname = socket.gethostname()
        mac_addr = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0,8*6,8)][::-1])
        
        # Determine actual local network IP instead of 127.x.x.x
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't have to be reachable
            s.connect(('10.254.254.254', 1))
            ip_addr = s.getsockname()[0]
        except Exception:
            ip_addr = '127.0.0.1'
        finally:
            s.close()

        agent_info = {
            "name": hostname,
            "ip": ip_addr,
            "mac": mac_addr,
            "state": "UNPROTECTED",
        }
        
        self.state = DaemonState()
        self.state.hostname = hostname
        self.state.ip = ip_addr
        self.state.mac = mac_addr
        self.ml_engine = MLEngine()
        # SOP 2's confusion matrix, computed here and carried to the relay in
        # register_agent. Milliseconds of work, once per start-up.
        evaluation = self.ml_engine.evaluate()
        if evaluation:
            agent_info["evaluation"] = evaluation
            print(f"[MLEngine] Held-out test set: accuracy {evaluation['accuracy']:.2f}% over {evaluation['n']} windows")
        self.bayanihan_client = BayanihanClient(
            relay_url=RELAY_URL,
            on_blacklist_update=self.state.add_to_blacklist,
            agent_info=agent_info,
            recent_events_provider=lambda: self.state.events_tail(20),
        )
        self.capture = CaptureEngine(self.state, self.ml_engine, self.bayanihan_client)
        self.telemetry = TelemetryEngine(self.state, self.bayanihan_client)
        self.ipc = IpcServer(on_message=self._handle_tray_message)
        self._stop = threading.Event()

    def _snapshot_for_tray(self) -> Dict[str, Any]:
        """
        Full state snapshot, plus the Bayanihan pending-report count.

        That count lives on self.bayanihan_client, not self.state — DaemonState
        has no reference to it, by design (same separation as sig_contributions,
        which the capture engine increments directly instead). Merged in here so
        both the tray mirror and the agent dashboard can show "N reports not yet
        acknowledged by the relay" instead of that gap being invisible, which is
        exactly what let it go unnoticed before.
        """
        snapshot = self.state.snapshot()
        snapshot["stats"]["bayanihan"]["pending"] = self.bayanihan_client.pending_count()
        return snapshot

    def _handle_tray_message(self, msg_type: str, data: Dict[str, Any]) -> None:
        """Handle messages received from the unprivileged tray process."""
        if msg_type == MSG_TOGGLE_REQUEST:
            new_val = self.state.toggle()
            self.bayanihan_client.set_enabled(new_val)
            self.ipc.broadcast(MSG_TOGGLE_ACK, {"protected": new_val})
            # Also push a full state update so the tray mirrors immediately.
            self.ipc.broadcast(MSG_STATE_UPDATE, self._snapshot_for_tray())

    def _broadcast_loop(self) -> None:
        """Periodically push full state snapshots to all connected trays."""
        while not self._stop.is_set():
            self._stop.wait(SIM_TICK_SECONDS)
            if self._stop.is_set():
                break
            try:
                self.ipc.broadcast(MSG_STATE_UPDATE, self._snapshot_for_tray())
                print("[BroadcastLoop] Tick", flush=True)
            except Exception as e:
                print(f"[BroadcastLoop] Failed: {e}")

    def run(self) -> None:
        """Start all subsystems and block until interrupted."""
        self.ipc.start()
        self.telemetry.start()
        self.capture.start()

        broadcast_thread = threading.Thread(
            target=self._broadcast_loop, daemon=True, name="ipc-broadcast"
        )
        broadcast_thread.start()

        print(f"[SentiNet Daemon] IPC server ready")
        print(f"[SentiNet Daemon] Capture & Telemetry engines running (tick={SIM_TICK_SECONDS}s)")
        print(f"[SentiNet Daemon] Waiting for tray connections...")

        # Block until SIGINT / SIGTERM
        try:
            try:
                signal.signal(signal.SIGINT, lambda *_: self._stop.set())
                signal.signal(signal.SIGTERM, lambda *_: self._stop.set())
            except ValueError:
                # signal() only works from the main thread; if we're in a
                # background thread (e.g. test harness) just skip it.
                pass
            while not self._stop.is_set():
                self._stop.wait(1.0)
        except KeyboardInterrupt:
            pass
        finally:
            print("\n[SentiNet Daemon] Shutting down...")
            self.capture.stop()
            self.telemetry.stop()
            self.ipc.stop()
            self.bayanihan_client.set_enabled(False)
            print("[SentiNet Daemon] Stopped cleanly.", flush=True)
            # Exit for certain. SIGTERM is handled above, so if interpreter
            # shutdown then stalls on a background thread the process can no
            # longer be terminated short of SIGKILL — and a daemon that lingers
            # stays connected to the relay as a ghost agent.
            os._exit(0)


if __name__ == "__main__":
    daemon = SentiNetDaemon()
    daemon.run()
