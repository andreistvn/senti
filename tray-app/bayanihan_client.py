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
        
        self._setup_events()
        
        # Start connection in a background thread to avoid blocking the daemon
        self.thread = threading.Thread(target=self._connect_loop, daemon=True, name="bayanihan-client")
        self.thread.start()

    def set_enabled(self, enabled: bool):
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
                    # Attempt connection
                    self.sio.connect(self.relay_url)
                    self.sio.wait()
            except Exception as e:
                # Connection failed, retry later
                pass
            time.sleep(5)

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

    def send_telemetry(self, cpu: float, ram: float, state: str = None):
        if self.connected and self.agent_info:
            try:
                payload = {
                    "mac": self.agent_info.get("mac"),
                    "cpu": cpu,
                    "ram": ram
                }
                if state:
                    payload["state"] = state
                self.sio.emit("telemetry_report", payload)
            except Exception as e:
                pass
