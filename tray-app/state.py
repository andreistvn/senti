"""
SentiNet Tray — Agent state (read-only IPC mirror).

In the privilege-separated architecture the daemon owns the authoritative
state.  This module provides ``AgentState``, a **read-only mirror** that is
populated by ``STATE_UPDATE`` messages received from the daemon over IPC.

The HTTP API server (``api_server.py``) and the tray icon read from this
mirror exactly as before — no changes needed in those layers.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from config import AGENT_VERSION
from ipc_protocol import (
    IpcClient,
    MSG_EVENT_NEW,
    MSG_HEALTH_UPDATE,
    MSG_STATE_UPDATE,
    MSG_TOGGLE_ACK,
    MSG_TOGGLE_REQUEST,
)


class AgentState:
    """Thread-safe, read-only mirror of daemon state.

    The tray and API server read from here; mutations happen only via IPC
    messages from the daemon (see ``_apply_snapshot``), or by requesting a
    toggle through the daemon.
    """

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
        self.memory: int = 84          # system-wide percent, gauge only
        self.memory_mb: float = 0.0    # daemon RSS in MB (Chapter 3's figure)

        # Bayanihan
        self.sig_contributions: int = 0

        # Detection log
        # This node's own identity, pushed by the daemon.
        self.identity: Dict[str, str] = {"hostname": "", "ip": "", "mac": ""}
        self.blacklist: list = []

        self.events: list = []
        self.last_threat: Optional[Dict[str, str]] = None

        # Health / services
        self.services: list = []

        # IPC client (set after construction via ``connect_daemon``)
        self._ipc: Optional[IpcClient] = None

        # Change listeners (tray icon refresh)
        self._on_change: List[Callable] = []

    # ── IPC connection ─────────────────────────────────────────────

    def connect_daemon(self) -> IpcClient:
        """Create and start the IPC client that populates this mirror."""
        self._ipc = IpcClient(on_message=self._handle_daemon_message)
        self._ipc.start()
        return self._ipc

    def daemon_connected(self) -> bool:
        """True if the IPC client has an active connection to the daemon."""
        return self._ipc is not None and self._ipc.connected

    def _handle_daemon_message(self, msg_type: str, data: Dict[str, Any]) -> None:
        """Dispatch incoming daemon messages."""
        if msg_type == MSG_STATE_UPDATE:
            self._apply_snapshot(data)
        elif msg_type == MSG_TOGGLE_ACK:
            new_val = data.get("protected", self.protected)
            with self._lock:
                self.protected = new_val
                self.protected_since = time.time() if new_val else None
            self._notify()
        elif msg_type == MSG_EVENT_NEW:
            with self._lock:
                self.events.insert(0, data)
                self.events = self.events[:50]
        elif msg_type == MSG_HEALTH_UPDATE:
            with self._lock:
                self.services = data if isinstance(data, list) else []

    def _apply_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Apply a full STATE_UPDATE snapshot from the daemon."""
        status = snapshot.get("status", {})
        stats = snapshot.get("stats", {})
        events = snapshot.get("events", [])
        services = snapshot.get("services", [])
        bayanihan = stats.get("bayanihan", {})

        with self._lock:
            self.protected = status.get("protected", self.protected)
            since_str = status.get("since")
            if since_str:
                try:
                    self.protected_since = datetime.fromisoformat(since_str).timestamp()
                except (ValueError, TypeError):
                    pass
            else:
                self.protected_since = None

            self.inspected = stats.get("inspected", self.inspected)
            self.dropped = stats.get("dropped", self.dropped)
            self.passed = stats.get("passed", self.passed)
            self.blocked = stats.get("blocked", self.blocked)
            self.cpu = stats.get("cpu", self.cpu)
            self.memory = stats.get("memory", self.memory)
            self.memory_mb = stats.get("memoryMb", self.memory_mb)
            self.identity = snapshot.get("identity", self.identity)
            self.blacklist = snapshot.get("blacklist", self.blacklist)
            self.sig_contributions = bayanihan.get("contributions", self.sig_contributions)
            self.last_threat = stats.get("lastThreat", self.last_threat)
            self.events = list(events)
            self.services = list(services)

        self._notify()

    # ── Subscription ───────────────────────────────────────────────

    def on_change(self, callback: Callable) -> None:
        self._on_change.append(callback)

    def _notify(self) -> None:
        for cb in list(self._on_change):
            try:
                cb()
            except Exception:
                pass

    # ── Mutations (send requests to daemon) ────────────────────────

    def toggle(self) -> None:
        """Request the daemon to toggle protection."""
        if self._ipc and self._ipc.connected:
            self._ipc.send(MSG_TOGGLE_REQUEST)

    def set_protected(self, value: bool) -> None:
        """Request protection change from the daemon.

        Unlike the old implementation this does **not** mutate state directly;
        it asks the daemon, which will reply with a ``TOGGLE_ACK``.
        """
        if self.protected != value:
            self.toggle()

    def is_protected(self) -> bool:
        with self._lock:
            return self.protected

    # ── Snapshots for the API ──────────────────────────────────────

    def status_dict(self) -> Dict[str, Any]:
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

    def stats_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "inspected": self.inspected,
                "dropped": self.dropped,
                "passed": self.passed,
                "blocked": self.blocked,
                "cpu": round(self.cpu, 1),
                "memory": self.memory,
                "memoryMb": round(self.memory_mb, 1),
                "bayanihan": {
                    "contributions": self.sig_contributions,
                },
                "lastThreat": self.last_threat,
                "protected": self.protected,
                "identity": self.identity,
                "blacklist": self.blacklist,
            }

    def events_list(self) -> list:
        with self._lock:
            return list(self.events)

    def health_list(self) -> list:
        with self._lock:
            return list(self.services)
