import os
from dotenv import load_dotenv

load_dotenv()

ADMIN_API_HOST = os.getenv('ADMIN_API_HOST', '127.0.0.1')
ADMIN_API_PORT = int(os.getenv('ADMIN_API_PORT', '8771'))
ADMIN_API_DEBUG = os.getenv('ADMIN_API_DEBUG', 'true').lower() == 'true'

# Session/auth
SESSION_TIMEOUT_SECONDS = 3600

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
