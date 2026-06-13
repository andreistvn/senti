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

# Cosmetic.
AGENT_VERSION = "v2.4.9"

# How often (seconds) the simulation engine ticks while protection is ON.
SIM_TICK_SECONDS = float(os.environ.get("SENTINET_SIM_TICK", "1.0"))
