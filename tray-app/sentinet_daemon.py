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
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import psutil
import scapy.all as scapy

from ml_engine import MLEngine
from bayanihan_client import BayanihanClient

from config import AGENT_VERSION, SIM_TICK_SECONDS
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
        self.memory: int = 84

        # Bayanihan
        self.sig_contributions: int = 0
        self.users_protected: int = 40

        # Detection log (most recent first)
        self.events: deque = deque(maxlen=50)
        self.last_threat: Optional[Dict[str, str]] = None

        # Blacklist (Phase 2+)
        self.blacklist: Set[str] = set()

        # Change listeners
        self._on_change: List = []

    def add_to_blacklist(self, mac: str) -> None:
        with self._lock:
            self.blacklist.add(mac)

    def remove_from_blacklist(self, mac: str) -> None:
        with self._lock:
            self.blacklist.discard(mac)

    def is_blacklisted(self, mac: str) -> bool:
        # thread-safe enough for check, but using lock for strictness
        with self._lock:
            return mac in self.blacklist

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
                    "bayanihan": {
                        "contributions": self.sig_contributions,
                        "usersProtected": self.users_protected,
                    },
                    "lastThreat": self.last_threat,
                    "protected": self.protected,
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
                return
            
            # If not blacklisted, it passes Tier 1. Proceed to Tier 2 ML logic.
            with self.state._lock:
                self.state.passed += 1

            # Tier 2: Stateful ML Engine evaluation
            score = self.ml_engine.process_packet(src_mac, op, src_ip, dst_ip)
            
            if score >= 0.50:
                print(f"[Tier 2] THREAT DETECTED: {src_mac} (Score: {score:.2f})")
                self.state.add_to_blacklist(src_mac)
                
                # Generate Attack Report format
                event_id = len(self.state.events) + 1
                now = datetime.now()
                threat_event = {
                    "id": event_id,
                    "timestamp": now.strftime('%H:%M:%S'),
                    "sourceMac": src_mac,
                    "attackType": "ARP Spoofing" if score > 0.8 else "Anomalous ARP",
                    "tier": "Tier 2",
                    "action": "Blocked",
                    "confidence": f"{score*100:.1f}%"
                }
                
                with self.state._lock:
                    self.state.events.appendleft(threat_event)
                    self.state.last_threat = threat_event
                    
                # Send to Relay Node via Bayanihan Layer
                self.bayanihan_client.send_attack_report(threat_event)

class TelemetryEngine(threading.Thread):
    """Background thread that tracks real CPU and memory usage."""

    def __init__(self, state: DaemonState, bayanihan_client: BayanihanClient) -> None:
        super().__init__(daemon=True, name="telemetry-engine")
        self.state = state
        self.bayanihan_client = bayanihan_client
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            time.sleep(SIM_TICK_SECONDS)
            
            is_protected = self.state.is_protected()
            
            if is_protected:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory().percent
            else:
                cpu = 0
                mem = 0
            
            with self.state._lock:
                self.state.cpu = cpu
                self.state.memory = mem
                
            if is_protected:
                self.bayanihan_client.send_telemetry(cpu, mem, "PROTECTED")


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
        self.ml_engine = MLEngine()
        self.bayanihan_client = BayanihanClient(
            relay_url="http://localhost:8771",
            on_blacklist_update=self.state.add_to_blacklist,
            agent_info=agent_info
        )
        self.capture = CaptureEngine(self.state, self.ml_engine, self.bayanihan_client)
        self.telemetry = TelemetryEngine(self.state, self.bayanihan_client)
        self.ipc = IpcServer(on_message=self._handle_tray_message)
        self._stop = threading.Event()

    def _handle_tray_message(self, msg_type: str, data: Dict[str, Any]) -> None:
        """Handle messages received from the unprivileged tray process."""
        if msg_type == MSG_TOGGLE_REQUEST:
            new_val = self.state.toggle()
            self.bayanihan_client.set_enabled(new_val)
            self.ipc.broadcast(MSG_TOGGLE_ACK, {"protected": new_val})
            # Also push a full state update so the tray mirrors immediately.
            self.ipc.broadcast(MSG_STATE_UPDATE, self.state.snapshot())

    def _broadcast_loop(self) -> None:
        """Periodically push full state snapshots to all connected trays."""
        while not self._stop.is_set():
            self._stop.wait(SIM_TICK_SECONDS)
            if self._stop.is_set():
                break
            try:
                self.ipc.broadcast(MSG_STATE_UPDATE, self.state.snapshot())
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
            print("[SentiNet Daemon] Stopped cleanly.")


if __name__ == "__main__":
    daemon = SentiNetDaemon()
    daemon.run()
