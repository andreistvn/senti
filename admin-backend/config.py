import os
from dotenv import load_dotenv

load_dotenv()

ADMIN_API_HOST = os.getenv('ADMIN_API_HOST', '127.0.0.1')
ADMIN_API_PORT = int(os.getenv('ADMIN_API_PORT', '8771'))
ADMIN_API_DEBUG = os.getenv('ADMIN_API_DEBUG', 'true').lower() == 'true'

# Session/auth
SESSION_TIMEOUT_SECONDS = 3600

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
