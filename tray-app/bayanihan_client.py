import re
import socketio
import threading
import time

class BayanihanClient:
    """
    Tier-3 Bayanihan Collaborative Layer Client.
    Connects to the Central Relay Node to share threat intelligence and receive blacklist updates.
    """
    def __init__(self, relay_url="http://localhost:8771", on_blacklist_update=None, agent_info=None):
        self.relay_url = relay_url
        self.on_blacklist_update = on_blacklist_update
        self.agent_info = agent_info or {}
        self.sio = socketio.Client()
        self.connected = False

        self.enabled = False

        # Connection diagnostics. Without these a wrong relay address or a
        # blocked port is completely silent: the agent simply never appears on
        # the admin dashboard and nothing anywhere says why.
        self._attempts = 0
        self._last_error = None

        self._setup_events()

        print(f"[BayanihanClient] Relay target: {self.relay_url}")
        print("[BayanihanClient] Waiting for protection to be toggled ON before connecting.")

        # Start connection in a background thread to avoid blocking the daemon
        self.thread = threading.Thread(target=self._connect_loop, daemon=True, name="bayanihan-client")
        self.thread.start()

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
                self.sio.emit("register_agent", self.agent_info)
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
                self.on_blacklist_update(mac)

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

    def send_attack_report(self, threat_event: dict):
        """
        Send a threat detection event to the Relay Node.
        """
        if self.connected:
            try:
                self.sio.emit("attack_report", threat_event)
                print(f"[BayanihanClient] Sent attack report for {threat_event.get('sourceMac')}")
            except Exception as e:
                print(f"[BayanihanClient] Failed to send attack report: {e}")
        else:
            print("[BayanihanClient] Cannot send attack report: Not connected to Relay Node")

    def send_telemetry(self, cpu: float, ram: float, state: str = None,
                       ram_mb: float = None, protected: bool = None):
        """
        Report resource consumption to the relay.

        ram is the system-wide percentage the dashboard gauge uses; ram_mb is this
        process's RSS in megabytes, which is what Chapter 3 specifies and what the
        relay records for analysis.
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
                self.sio.emit("telemetry_report", payload)
            except Exception as e:
                pass
