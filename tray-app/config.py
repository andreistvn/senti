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

# IPC: Unix domain socket path (macOS/Linux) for daemon ↔ tray communication.
IPC_SOCKET_PATH = os.environ.get("SENTINET_IPC_SOCKET", "/tmp/sentinet.sock")

# IPC: TCP fallback port for Windows (where Unix sockets are unavailable).
IPC_TCP_FALLBACK_PORT = int(os.environ.get("SENTINET_IPC_PORT", "8769"))

# Bayanihan attack-report delivery. Reports are queued durably (SQLite) and
# retried with an ack until the relay confirms it stored them — see
# bayanihan_client.py. PENDING_REPORTS_DB_PATH is where that queue survives a
# daemon restart; REPORT_QUEUE_MAX caps it so a relay outage can't grow it
# without bound (oldest unsent report is dropped first); REPORT_ACK_TIMEOUT is
# how long one delivery attempt waits for the relay's ack before retrying.
PENDING_REPORTS_DB_PATH = os.environ.get(
    "SENTINET_PENDING_REPORTS_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "pending_reports.db"),
)
REPORT_QUEUE_MAX = int(os.environ.get("SENTINET_REPORT_QUEUE_MAX", "2000"))
REPORT_ACK_TIMEOUT = float(os.environ.get("SENTINET_REPORT_ACK_TIMEOUT", "8.0"))
REPORT_RETRY_INTERVAL = float(os.environ.get("SENTINET_REPORT_RETRY_INTERVAL", "2.0"))
