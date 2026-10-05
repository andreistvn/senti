"""
SentiNet Tray — configuration.

All values can be overridden with environment variables so you don't have to
edit code to point the tray at a different dashboard or port.
"""
import os

# Loopback API the tray exposes for the dashboard to read.
API_HOST = os.environ.get("SENTINET_API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("SENTINET_API_PORT", "8770"))

# Where "Open Dashboard" sends the browser. This is the exported web app's
# dev server (Vite defaults to 5173). Change if you serve it elsewhere.
DASHBOARD_URL = os.environ.get("SENTINET_DASHBOARD_URL", "http://localhost:5173")

# Bayanihan (Tier 3) relay node the daemon reports threats to. On a multi-machine
# testbed this must point at the relay machine's LAN address, not loopback.
RELAY_URL = os.environ.get("SENTINET_RELAY_URL", "http://localhost:8771")

# Cosmetic.
AGENT_VERSION = "v2.4.9"

# How often (seconds) the simulation engine ticks while protection is ON.
SIM_TICK_SECONDS = float(os.environ.get("SENTINET_SIM_TICK", "1.0"))

# Quiet gap (seconds) after which a Tier-1 block on an already-blacklisted MAC
# is logged again. A sustained flood keeps resetting this timer so it stays at
# one log line, but a genuinely new burst — e.g. re-running the attack generator
# — reports afresh. Lower it to see new records sooner while testing.
TIER1_REPORT_COOLDOWN_SECONDS = float(os.environ.get("SENTINET_TIER1_COOLDOWN", "30.0"))

# IPC: Unix domain socket path (macOS/Linux) for daemon ↔ tray communication.
IPC_SOCKET_PATH = os.environ.get("SENTINET_IPC_SOCKET", "/tmp/sentinet.sock")

# IPC: TCP fallback port for Windows (where Unix sockets are unavailable).
IPC_TCP_FALLBACK_PORT = int(os.environ.get("SENTINET_IPC_PORT", "8769"))
