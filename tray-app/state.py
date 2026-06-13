"""
SentiNet Tray — shared agent state + traffic/threat simulator.

There is no real packet capture here. The SimulationEngine mirrors the mock
logic the React dashboard used to run client-side (see Dashboard.tsx and the
old AgentToggle.tsx), so the numbers look and feel identical — just sourced
from one authoritative place now.

Everything is guarded by a single lock; the HTTP server, the tray menu, and
the simulation thread all touch this concurrently.
"""
import random
import threading
import time
from collections import deque
from datetime import datetime

from config import AGENT_VERSION, SIM_TICK_SECONDS

THREAT_LABELS = [
    "ARP Spoofing",
    "MITM Attempt",
    "Malicious ARP Reply",
    "Rogue Gateway Probe",
    "ARP Cache Poisoning",
]

# Mirrors INITIAL_DAEMONS in Dashboard.tsx.
DAEMON_SERVICES = [
    {"id": "scapy",     "name": "Scapy Sniffer",    "status": "active",    "detail": "Capturing ARP frames on wlan0",      "uptime": "0m 0s"},
    {"id": "ml",        "name": "Tier-2 ML Engine",  "status": "loaded",    "detail": "RandomForest model v3.1 in memory",  "uptime": "0m 0s"},
    {"id": "ws",        "name": "WebSocket Relay",   "status": "connected", "detail": "relay.dict.gov.ph:8443 · 12ms ping", "uptime": "0m 0s"},
    {"id": "chain",     "name": "Blockchain Sync",   "status": "active",    "detail": "Block #49,812 · 94% synced",         "uptime": "0m 0s"},
    {"id": "arp",       "name": "ARP Guard Module",  "status": "active",    "detail": "Monitoring 34 active hosts",         "uptime": "0m 0s"},
    {"id": "bayanihan", "name": "Bayanihan Agent",   "status": "connected", "detail": "Peer mesh: 40 nodes reachable",      "uptime": "0m 0s"},
]


def _random_mac():
    return ":".join(f"{random.randint(0, 255):02X}" for _ in range(6))


def _fmt_uptime(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


class AgentState:
    """Thread-safe container for everything the dashboard reads."""

    def __init__(self):
        self._lock = threading.Lock()
        self.protected = False
        self.started_at = time.time()
        self.protected_since = None

        # traffic counters
        self.inspected = 0
        self.dropped = 0
        self.passed = 0
        self.blocked = 0

        # telemetry
        self.cpu = 4.0
        self.memory = 84  # MB out of 256

        # bayanihan
        self.sig_contributions = 0
        self.users_protected = 40

        # rolling detection log (most recent first)
        self.events = deque(maxlen=50)
        self.last_threat = None

        # listeners notified when `protected` changes (e.g. tray icon refresh)
        self._on_change = []

    # ── subscription ──────────────────────────────────────────────
    def on_change(self, callback):
        self._on_change.append(callback)

    def _notify(self):
        for cb in list(self._on_change):
            try:
                cb()
            except Exception:
                pass

    # ── mutations ─────────────────────────────────────────────────
    def set_protected(self, value):
        with self._lock:
            value = bool(value)
            if value == self.protected:
                return self.protected
            self.protected = value
            self.protected_since = time.time() if value else None
        self._notify()
        return value

    def toggle(self):
        return self.set_protected(not self.protected)

    def is_protected(self):
        with self._lock:
            return self.protected

    # ── snapshots for the API ─────────────────────────────────────
    def status_dict(self):
        with self._lock:
            since = None
            if self.protected_since:
                since = datetime.fromtimestamp(self.protected_since).isoformat()
            return {
                "protected": self.protected,
                "relay": "online" if self.protected else "offline",
                "version": AGENT_VERSION,
                "since": since,
            }

    def stats_dict(self):
        with self._lock:
            return {
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
            }

    def events_list(self):
        with self._lock:
            return list(self.events)

    def health_list(self):
        with self._lock:
            up = _fmt_uptime(time.time() - self.started_at)
            services = []
            for svc in DAEMON_SERVICES:
                s = dict(svc)
                # while protected everything runs; while off, sniffer/guard idle
                if not self.protected and s["id"] in ("scapy", "arp"):
                    s["status"] = "offline"
                    s["detail"] = "Idle — protection disabled"
                    s["uptime"] = "0s"
                else:
                    s["uptime"] = up
                services.append(s)
            return services


class SimulationEngine(threading.Thread):
    """Background thread that advances counters while protection is ON."""

    def __init__(self, state: AgentState):
        super().__init__(daemon=True)
        self.state = state
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            time.sleep(SIM_TICK_SECONDS)
            st = self.state
            with st._lock:
                if not st.protected:
                    # decay cpu toward idle when off
                    st.cpu = max(2.0, st.cpu * 0.8)
                    continue

                # traffic throughput (ported from Dashboard.tsx interval)
                st.inspected += random.randint(2, 12)
                st.passed += random.randint(2, 11)
                if random.random() > 0.7:
                    st.dropped += 1

                # telemetry
                st.cpu = random.uniform(2.0, 17.0)
                st.memory = random.randint(70, 100)

                # bayanihan (rare)
                if random.random() > 0.92:
                    st.sig_contributions += 1
                    st.users_protected += random.randint(0, 3)

                # threat event (mirrors AgentToggle's ~15% chance per tick)
                if random.random() > 0.85:
                    st.blocked += 1
                    tier = 1 if random.random() > 0.5 else 2
                    action = "Blocked" if tier == 1 else "Dropped"
                    label = THREAT_LABELS[st.blocked % len(THREAT_LABELS)]
                    event = {
                        "id": st.blocked,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "sourceMac": _random_mac(),
                        "attackType": label,
                        "tier": f"Tier {tier}",
                        "action": action,
                    }
                    st.events.appendleft(event)
                    st.last_threat = {
                        "attackType": label,
                        "sourceMac": event["sourceMac"],
                        "timestamp": event["timestamp"],
                    }
