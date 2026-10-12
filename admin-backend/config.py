import os
from dotenv import load_dotenv

load_dotenv()

ADMIN_API_HOST = os.getenv('ADMIN_API_HOST', '127.0.0.1')
ADMIN_API_PORT = int(os.getenv('ADMIN_API_PORT', '8771'))
ADMIN_API_DEBUG = os.getenv('ADMIN_API_DEBUG', 'true').lower() == 'true'

# Browser origins allowed to call the API. The defaults cover a dashboard opened on
# the relay machine itself; on a multi-machine testbed add the relay's LAN origin
# (e.g. http://192.168.10.10:5175) — launch_scripts/start_relay_node.sh does this.
ADMIN_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        'ADMIN_CORS_ORIGINS',
        'http://localhost:5175,http://127.0.0.1:5175,http://localhost:5173,http://127.0.0.1:5173',
    ).split(',')
    if origin.strip()
]

# Session/auth
# The administrator account the relay keeps in place (see auth.ensure_account).
# Both empty means accounts are managed by hand with `python auth.py set`.
ADMIN_DIGITAL_ID = os.getenv('ADMIN_DIGITAL_ID', '').strip()
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')

# A session ends after this long without a request (the dashboard polls every
# few seconds, so an open dashboard stays signed in)...
SESSION_TIMEOUT_SECONDS = int(os.getenv('SESSION_TIMEOUT_SECONDS', '3600'))
# ...and after this long regardless, so a stolen session cookie does not last forever.
SESSION_MAX_AGE_SECONDS = int(os.getenv('SESSION_MAX_AGE_SECONDS', str(12 * 3600)))

# Agents list (GET /agents, the "Protected Devices" panel). An agent's row is
# refreshed on every register_agent/telemetry_report it sends (roughly once a
# second while connected — see tray-app TelemetryEngine's SIM_TICK_SECONDS).
# get_agents() prunes any row whose last heartbeat is older than this before
# returning, rather than relying solely on the Socket.IO `disconnect` event to
# remove it: that event can only fire for a connection *this* relay process
# itself is holding, so a hard-killed agent (stop_all.bat's taskkill /F) or —
# especially — a relay restart (which always clears in-memory connection state
# but never touched the persisted agents table) can otherwise leave a ghost
# row with no automatic expiry at all.
AGENT_STALE_SECONDS = float(os.getenv('AGENT_STALE_SECONDS', '12'))

# ─── Resource telemetry (Chapter 3: "Resource Consumption") ─────────────────
# The paper defines resource consumption as "CPU usage (%) and RAM consumption
# (MB) tracked at one-minute intervals". The dashboards refresh far faster than
# that for live display, so the recorded dataset is sampled separately from what
# the UI shows: readings land in the telemetry_readings table at this interval.
TELEMETRY_SAMPLE_INTERVAL = float(os.getenv('TELEMETRY_SAMPLE_INTERVAL', '60'))

# Set this during a measurement run to label the rows, e.g. "baseline",
# "arp_poison_100pps", "arp_flood_1000pps" — the paper's three traffic
# scenarios. Exported with every reading so runs can be told apart.
TELEMETRY_SCENARIO = os.getenv('TELEMETRY_SCENARIO', '')

# Record readings at all. Off means the dashboards still work, nothing is stored.
TELEMETRY_RECORD = os.getenv('TELEMETRY_RECORD', 'true').lower() == 'true'

# ─── Live confusion matrix (SOP 2) ──────────────────────────────────────────
# The MAC address(es) of the attacker for this run, declared up front:
#     ./launch_scripts/start_relay_node.sh --attacker ce:d6:36:4d:0a:9f
# A confusion matrix needs to know what each packet really was, independently
# of what the agent decided about it. On a controlled testbed that is known —
# the attack generator is the attacker, everything else is benign — so it is
# stated here and handed to the agents to score against. Comma-separated for
# more than one. Empty means no live matrix; the SOP tab then shows the model's
# held-out test set figures only.
def _parse_macs(raw: str) -> list:
    macs = []
    for part in raw.replace(';', ',').split(','):
        mac = part.strip().lower().replace('-', ':')
        if len(mac) == 17 and mac.count(':') == 5 and mac not in macs:
            macs.append(mac)
    return macs


SOP_ATTACKER_MACS = _parse_macs(os.getenv('SOP_ATTACKER_MACS', ''))

# MultiChain JSON-RPC
MULTICHAIN_ENABLED = os.getenv('MULTICHAIN_ENABLED', 'true').lower() == 'true'
MULTICHAIN_RPC_URL = os.getenv('MULTICHAIN_RPC_URL', 'http://127.0.0.1:4365')
MULTICHAIN_RPC_USER = os.getenv('MULTICHAIN_RPC_USER', 'multichainrpc')
MULTICHAIN_RPC_PASSWORD = os.getenv('MULTICHAIN_RPC_PASSWORD', 'secret')
MULTICHAIN_STREAM_NAME = os.getenv('MULTICHAIN_STREAM_NAME', 'threat_logs')

# Seconds to wait on a single JSON-RPC call before treating the node as unreachable.
MULTICHAIN_RPC_TIMEOUT = float(os.getenv('MULTICHAIN_RPC_TIMEOUT', '5.0'))
# Create + subscribe to the threat stream automatically if the node doesn't have it.
MULTICHAIN_AUTO_CREATE_STREAM = os.getenv('MULTICHAIN_AUTO_CREATE_STREAM', 'true').lower() == 'true'
# How often the background worker refreshes chain health and resyncs the ledger mirror.
MULTICHAIN_SYNC_INTERVAL = float(os.getenv('MULTICHAIN_SYNC_INTERVAL', '10.0'))
# Threat records buffered while the node is unreachable before we start dropping.
MULTICHAIN_QUEUE_SIZE = int(os.getenv('MULTICHAIN_QUEUE_SIZE', '1000'))
MULTICHAIN_MAX_PUBLISH_ATTEMPTS = int(os.getenv('MULTICHAIN_MAX_PUBLISH_ATTEMPTS', '5'))
# Number of recent stream items pulled back on each reconciliation pass.
MULTICHAIN_LEDGER_FETCH_COUNT = int(os.getenv('MULTICHAIN_LEDGER_FETCH_COUNT', '200'))


# Agent seed data
DEFAULT_AGENTS = [
    {
        'id': 'A',
        'name': 'Agent Alpha',
        'ip': '192.168.10.101',
        'mac': 'AA:BB:CC:DD:EE:01',
        'state': 'PROTECTED',
        'syncProgress': 0,
        'cpu': 18,
        'ram': 42,
        'connectedSince': '08:14:02',
        'packetsProcessed': 142830,
    },
    {
        'id': 'B',
        'name': 'Agent Bravo',
        'ip': '192.168.10.102',
        'mac': 'AA:BB:CC:DD:EE:02',
        'state': 'PROTECTED',
        'syncProgress': 0,
        'cpu': 22,
        'ram': 51,
        'connectedSince': '08:14:07',
        'packetsProcessed': 138420,
    },
    {
        'id': 'C',
        'name': 'Agent Charlie',
        'ip': '192.168.10.103',
        'mac': 'AA:BB:CC:DD:EE:03',
        'state': 'PROTECTED',
        'syncProgress': 0,
        'cpu': 15,
        'ram': 37,
        'connectedSince': '08:15:11',
        'packetsProcessed': 159012,
    },
    {
        'id': 'D',
        'name': 'Agent Delta',
        'ip': '192.168.10.104',
        'mac': 'AA:BB:CC:DD:EE:04',
        'state': 'PROTECTED',
        'syncProgress': 0,
        'cpu': 31,
        'ram': 58,
        'connectedSince': '08:15:33',
        'packetsProcessed': 121765,
    },
]
