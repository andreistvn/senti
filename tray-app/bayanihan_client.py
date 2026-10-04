import json
import re
import socketio
import sqlite3
import threading
import time
import uuid
from collections import OrderedDict
from typing import Callable, Optional

from config import (
    PENDING_REPORTS_DB_PATH,
    REPORT_QUEUE_MAX,
    REPORT_ACK_TIMEOUT,
    REPORT_RETRY_INTERVAL,
)


class _PendingReportStore:
    """
    Durable, append-only store for attack reports not yet acknowledged by the
    relay.

    Without this, a daemon restart during a relay outage would silently lose
    exactly the reports this class exists to protect — the in-memory queue
    alone only survives a dropped/slow connection, not a crash or an update.
    A plain SQLite file is enough: one small table, keyed by the client-
    generated event id so re-adding an already-stored row is a no-op.
    """

    def __init__(self, path: str):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS pending_reports (
                client_event_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            )"""
        )
        self._conn.commit()

    def add(self, event: dict) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO pending_reports "
                "(client_event_id, payload, attempts, created_at) VALUES (?, ?, 0, ?)",
                (event["clientEventId"], json.dumps(event), time.time()),
            )
            self._conn.commit()

    def bump_attempts(self, client_event_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE pending_reports SET attempts = attempts + 1 WHERE client_event_id = ?",
                (client_event_id,),
            )
            self._conn.commit()

    def remove(self, client_event_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM pending_reports WHERE client_event_id = ?", (client_event_id,)
            )
            self._conn.commit()

    def load_all(self) -> list:
        """Everything still unacknowledged, oldest first — called once at startup."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload, attempts FROM pending_reports ORDER BY created_at ASC"
            ).fetchall()
        items = []
        for payload, attempts in rows:
            try:
                event = json.loads(payload)
            except (TypeError, ValueError):
                continue
            items.append({"event": event, "attempts": attempts})
        return items


class BayanihanClient:
    """
    Tier-3 Bayanihan Collaborative Layer Client.
    Connects to the Central Relay Node to share threat intelligence and receive blacklist updates.

    Attack-report delivery is queued and acknowledged, not fire-and-forget: a
    report submitted via send_attack_report() is durably recorded immediately
    and only cleared once the relay's `attack_report` handler actually returns
    an "ok" ack (see admin-backend/main.py). Until then it is retried on a
    dedicated thread independent of whatever the Socket.IO connection is doing,
    which is what lets a report survive a relay outage, a slow reconnect, or
    the race of a threat being detected the instant protection is toggled on
    (before the socket has finished connecting) — previously all three of
    these silently dropped the report with no record anywhere but the agent's
    own local dashboard.
    """
    def __init__(self, relay_url="http://localhost:8771", on_blacklist_update=None, agent_info=None,
                 recent_events_provider: Optional[Callable[[], list]] = None,
                 pending_store_path: str = PENDING_REPORTS_DB_PATH):
        self.relay_url = relay_url
        self.on_blacklist_update = on_blacklist_update
        self.agent_info = agent_info or {}
        # Called at connect time to attach a short tail of this agent's own
        # recent detections to register_agent, so the relay can backfill any
        # whose report never made it into the pending queue below (a second,
        # independent safety net — see _ingest_attack_report on the server).
        self.recent_events_provider = recent_events_provider
        self.sio = socketio.Client()
        self.connected = False

        self.enabled = False

        # Connection diagnostics. Without these a wrong relay address or a
        # blocked port is completely silent: the agent simply never appears on
        # the admin dashboard and nothing anywhere says why.
        self._attempts = 0
        self._last_error = None

        # ── Durable, retried, acknowledged attack-report queue ──────────────
        self._store = _PendingReportStore(pending_store_path)
        self._pending_lock = threading.Lock()
        self._pending: "OrderedDict[str, dict]" = OrderedDict()
        for item in self._store.load_all():
            client_event_id = item["event"].get("clientEventId")
            if client_event_id:
                self._pending[client_event_id] = item
        # Set when a report is queued, so _report_loop delivers it at once
        # instead of on its next retry tick. That tick is REPORT_RETRY_INTERVAL
        # (2s) — fine for retries, but as the delay on a first delivery it would
        # dominate the Time-to-Block every other agent sees.
        self._report_wake = threading.Event()
        if self._pending:
            print(f"[BayanihanClient] Recovered {len(self._pending)} unsent report(s) from a previous run.")

        self._setup_events()

        print(f"[BayanihanClient] Relay target: {self.relay_url}")
        print("[BayanihanClient] Waiting for protection to be toggled ON before connecting.")

        # Start connection in a background thread to avoid blocking the daemon
        self.thread = threading.Thread(target=self._connect_loop, daemon=True, name="bayanihan-client")
        self.thread.start()

        # Separate thread for report delivery: the connect-loop thread blocks
        # on sio.wait() while connected, so it cannot also drain the queue.
        self.report_thread = threading.Thread(target=self._report_loop, daemon=True, name="bayanihan-reports")
        self.report_thread.start()

    def set_enabled(self, enabled: bool):
        if enabled != self.enabled:
            if enabled:
                print(f"[BayanihanClient] Protection ON — connecting to {self.relay_url}")
            else:
                print("[BayanihanClient] Protection OFF — disconnecting from the relay.")
            # A fresh toggle deserves a fresh report if it fails again.
            self._attempts = 0
            self._last_error = None

        self.enabled = enabled
        if not enabled and self.connected:
            try:
                self.sio.disconnect()
            except Exception:
                pass

    def _setup_events(self):
        @self.sio.event
        def connect():
            print("[BayanihanClient] Connected to Relay Node")
            self.connected = True
            if self.agent_info:
                payload = dict(self.agent_info)
                if self.recent_events_provider:
                    try:
                        payload["recentEvents"] = self.recent_events_provider()
                    except Exception as exc:
                        print(f"[BayanihanClient] Failed to collect recent events for backfill: {exc}")
                self.sio.emit("register_agent", payload)
                print(f"[BayanihanClient] Registered agent {self.agent_info.get('name')}")

        @self.sio.event
        def disconnect():
            print("[BayanihanClient] Disconnected from Relay Node")
            self.connected = False

        @self.sio.event
        def blacklist_update(data):
            print(f"[BayanihanClient] Received blacklist update: {data}")
            mac = data.get("mac")
            if mac and self.on_blacklist_update:
                is_new = self.on_blacklist_update(
                    mac,
                    origin="relay",
                    attack_type=data.get("attackType", "Unknown"),
                    confidence=data.get("confidence", "N/A"),
                    reported_by=data.get("reportedBy"),
                )
                # t_enforced in Chapter 3's Time-to-Block formula: the moment
                # this node wrote the attacker's MAC into its Tier-1 blacklist.
                enforced_at_ms = int(time.time() * 1000)

                # Tell the relay, so it can pair this with the detecting node's
                # t_detected. Only for a first-detection broadcast (it carries an
                # eventId) and only if the MAC was genuinely new here — a node
                # that already had it was protected earlier, not just now.
                event_id = data.get("eventId")
                if event_id and is_new:
                    try:
                        self.sio.emit("blacklist_enforced", {
                            "eventId": event_id,
                            "mac": mac,
                            "agentMac": self.agent_info.get("mac"),
                            "agentName": self.agent_info.get("name"),
                            "enforcedAtMs": enforced_at_ms,
                        })
                    except Exception as exc:
                        print(f"[BayanihanClient] Could not report enforcement of {mac}: {exc}")

        @self.sio.event
        def blacklist_sync(data):
            """
            Full blacklist replayed by the relay on connect.

            Without this an agent joining after a threat was reported would never
            learn about it — the live broadcast only reaches agents that happen to
            be connected at the moment of detection.
            """
            entries = data.get("entries", [])
            print(f"[BayanihanClient] Syncing {len(entries)} blacklist entries from relay")
            if not self.on_blacklist_update:
                return
            for e in entries:
                mac = e.get("mac")
                if mac:
                    self.on_blacklist_update(
                        mac,
                        origin="relay",
                        attack_type=e.get("attackType", "Unknown"),
                        confidence=e.get("confidence", "N/A"),
                        reported_by=e.get("reportedBy"),
                    )

    def _connect_loop(self):
        while True:
            try:
                if self.enabled and not self.connected:
                    self._attempts += 1
                    self.sio.connect(self.relay_url)
                    # Connected: the connect handler logs and registers us.
                    self._attempts = 0
                    self._last_error = None
                    self.sio.wait()
            except Exception as exc:
                self._report_failure(exc)
            time.sleep(5)

    def _report_failure(self, exc: Exception) -> None:
        """
        Surface a failed connection without flooding the log.

        This used to be a bare `pass`, which meant a wrong relay address, a
        firewall drop or an unreachable host all looked identical to a healthy
        agent that simply hadn't been toggled on yet.
        """
        message = f"{type(exc).__name__}: {exc}"

        # socket.io puts a cache-busting timestamp in the URL, so the raw text
        # differs on every retry. Normalise long digit runs before comparing,
        # otherwise "same error as last time" is never true and we reprint the
        # whole explanation every five seconds.
        fingerprint = re.sub(r'\d{5,}(\.\d+)?', 'N', message)

        if fingerprint != self._last_error:
            # First time we've seen this particular failure — explain it.
            self._last_error = fingerprint
            print(f"[BayanihanClient] Cannot reach the relay at {self.relay_url}")
            print(f"[BayanihanClient]   {message}")
            print("[BayanihanClient]   Check: is the relay running, is the address right,")
            print(f"[BayanihanClient]   and does 'curl {self.relay_url}/health' work from this machine?")
            print("[BayanihanClient]   Retrying every 5s; this agent will not appear on the")
            print("[BayanihanClient]   admin dashboard until it connects.")
        elif self._attempts % 12 == 0:
            # Same error still: remind roughly once a minute rather than per retry.
            print(
                f"[BayanihanClient] Still cannot reach {self.relay_url} "
                f"after {self._attempts} attempts — {message}"
            )

    # ── Attack-report queue ─────────────────────────────────────────────────

    def send_attack_report(self, threat_event: dict):
        """
        Queue a threat detection event for delivery to the Relay Node.

        Returns immediately — this never blocks the capture thread on network
        I/O, and never silently drops the event just because the socket isn't
        connected *right now*. Delivery (with retry until acknowledged) is
        handled by `_report_loop` on its own thread.
        """
        event = dict(threat_event)
        event.setdefault("clientEventId", str(uuid.uuid4()))
        client_event_id = event["clientEventId"]

        with self._pending_lock:
            if client_event_id in self._pending:
                return  # already queued (e.g. a caller retried the same dict)
            if len(self._pending) >= REPORT_QUEUE_MAX:
                oldest_id, _ = next(iter(self._pending.items()))
                print(
                    f"[BayanihanClient] Pending-report queue full ({REPORT_QUEUE_MAX}) — "
                    f"dropping oldest unsent report ({oldest_id[:8]}…)."
                )
                self._pending.pop(oldest_id, None)
                self._store.remove(oldest_id)
            self._pending[client_event_id] = {"event": event, "attempts": 0}
        self._store.add(event)
        self._report_wake.set()

        print(
            f"[BayanihanClient] Queued attack report for {event.get('sourceMac')} "
            f"({client_event_id[:8]}…); {self.pending_count()} pending delivery."
        )

    def pending_count(self) -> int:
        """Reports accepted but not yet acknowledged by the relay. For dashboards/telemetry."""
        with self._pending_lock:
            return len(self._pending)

    def _report_loop(self) -> None:
        """Drain the pending-report queue whenever connected. Runs for the agent's lifetime."""
        while True:
            # Wakes early when a report is queued; otherwise this is the retry
            # tick. Cleared before flushing so a report queued mid-flush still
            # triggers the next pass immediately.
            self._report_wake.wait(REPORT_RETRY_INTERVAL)
            self._report_wake.clear()
            if self.connected:
                self._flush_pending()

    def _flush_pending(self) -> None:
        with self._pending_lock:
            items = list(self._pending.items())

        for client_event_id, item in items:
            if not self.connected:
                return

            try:
                ack = self.sio.call("attack_report", item["event"], timeout=REPORT_ACK_TIMEOUT)
            except Exception as exc:
                item["attempts"] += 1
                self._store.bump_attempts(client_event_id)
                if item["attempts"] == 1 or item["attempts"] % 15 == 0:
                    print(
                        f"[BayanihanClient] Report {client_event_id[:8]}… for "
                        f"{item['event'].get('sourceMac')} not yet acknowledged "
                        f"(attempt {item['attempts']}): {exc}"
                    )
                continue

            if not isinstance(ack, dict) or ack.get("status") != "ok":
                item["attempts"] += 1
                self._store.bump_attempts(client_event_id)
                print(
                    f"[BayanihanClient] Relay rejected report {client_event_id[:8]}…: "
                    f"{ack.get('detail') if isinstance(ack, dict) else ack!r}"
                )
                continue

            with self._pending_lock:
                self._pending.pop(client_event_id, None)
            self._store.remove(client_event_id)
            note = " (relay already had it)" if ack.get("duplicate") else ""
            print(
                f"[BayanihanClient] Report for {item['event'].get('sourceMac')} "
                f"acknowledged by relay ({client_event_id[:8]}…){note}."
            )

    def send_telemetry(self, cpu: float, ram: float, state: str = None,
                       ram_mb: float = None, protected: bool = None,
                       scenario: str = None):
        """
        Report resource consumption to the relay.

        ram is the system-wide percentage the dashboard gauge uses; ram_mb is this
        process's RSS in megabytes, which is what Chapter 3 specifies and what the
        relay records for analysis. scenario is the traffic scenario this agent is
        currently experiencing, which the relay stores alongside the reading.
        """
        if self.connected and self.agent_info:
            try:
                payload = {
                    "mac": self.agent_info.get("mac"),
                    "cpu": cpu,
                    "ram": ram
                }
                if ram_mb is not None:
                    payload["ramMb"] = ram_mb
                if protected is not None:
                    payload["protected"] = protected
                if state:
                    payload["state"] = state
                if scenario:
                    payload["scenario"] = scenario
                self.sio.emit("telemetry_report", payload)
            except Exception as e:
                pass
