"""
Admin backend state management.

Stores current admin sessions, agents, incidents, policies, and telemetry.
In a production system, this would be backed by a database.
"""

import time
from datetime import datetime
from typing import Optional, Dict, List, Any
from config import DEFAULT_AGENTS, SESSION_TIMEOUT_SECONDS

# In-memory session store
sessions: Dict[str, dict] = {}

# Admin credentials
ADMIN_CREDENTIALS = {
    'ADM-7734-ALPHA': 'SentiNet@2049',
}

# Policy config
policy_config = {
    'mlThreshold': 0.50,
    'arpFloodLimit': 1000,
    'autoBlacklist': False,
    'syncInterval': 4000,
    'logRetentionDays': 30,
}

# Agents
agents = [dict(a) for a in DEFAULT_AGENTS]

# Threat logs
threats = [
    {'id': 1, 'timestamp': '14:32:18', 'sourceMac': 'A4:5E:60:E2:3B:1C', 'attackType': 'ARP Spoofing', 'tier': 'Tier 1', 'action': 'Blocked'},
    {'id': 2, 'timestamp': '14:31:45', 'sourceMac': 'B8:27:EB:4F:92:D3', 'attackType': 'ARP Spoofing', 'tier': 'Tier 2', 'action': 'Dropped'},
    {'id': 3, 'timestamp': '14:29:12', 'sourceMac': '00:1A:7D:DA:71:13', 'attackType': 'ARP Spoofing', 'tier': 'Tier 1', 'action': 'Blocked'},
]

# Ledger entries
ledger = [
    {'blockId': '0x8A12', 'timestamp': '14:28:11', 'macHash': 'FD:09:A1:XX', 'score': '98.2%'},
    {'blockId': '0x8A13', 'timestamp': '14:29:05', 'macHash': 'E2:11:4B:XX', 'score': '94.5%'},
]

# System metrics
telemetry_summary = {
    'cpu': 12,
    'ram': 44,
    'latency': 14,
    'blockHeight': 33912,
    'lastSyncTime': '14:30:05',
    'chainStatus': 'HEALTHY',
    'totalIncidents': 47,
}

# Threat volume history
threat_history = [
    {'time': f'{14 + i // 4:02d}:{(i * 15) % 60:02d}:00', 'pps': 40 + (i * 7) % 180, 'blocked': 30 + (i * 5) % 140}
    for i in range(20)
]


def create_session(digital_id: str) -> str:
    """Create a new session for the given digital ID."""
    session_token = f'{digital_id}_{int(time.time())}_{id(object())}'
    sessions[session_token] = {
        'digital_id': digital_id,
        'created_at': time.time(),
        'last_accessed': time.time(),
    }
    return session_token


def validate_session(session_token: str) -> Optional[str]:
    """Validate session and return digital_id if valid, else None."""
    if session_token not in sessions:
        return None

    session = sessions[session_token]
    elapsed = time.time() - session['created_at']

    if elapsed > SESSION_TIMEOUT_SECONDS:
        del sessions[session_token]
        return None

    session['last_accessed'] = time.time()
    return session['digital_id']


def destroy_session(session_token: str) -> None:
    """Destroy a session."""
    if session_token in sessions:
        del sessions[session_token]


def get_agents() -> List[Dict[str, Any]]:
    """Get list of all agents."""
    return [dict(a) for a in agents]


def get_threats() -> List[Dict[str, Any]]:
    """Get list of all threats."""
    return [dict(t) for t in threats]


def get_ledger() -> List[Dict[str, Any]]:
    """Get list of all ledger entries."""
    return [dict(l) for l in ledger]


def get_policy() -> Dict[str, Any]:
    """Get current policy config."""
    return dict(policy_config)


def set_policy(new_config: Dict[str, Any]) -> Dict[str, Any]:
    """Update policy config."""
    global policy_config
    policy_config.update(new_config)
    return dict(policy_config)


def get_telemetry_summary() -> Dict[str, Any]:
    """Get current telemetry and blockchain metrics."""
    return dict(telemetry_summary)


def get_threat_history() -> List[Dict[str, Any]]:
    """Get threat volume history."""
    return [dict(t) for t in threat_history]


def add_threat(source_mac: str, attack_type: str, tier: str, action: str) -> Dict[str, Any]:
    """Add a new threat log entry."""
    threat_id = max([t.get('id', 0) for t in threats], default=0) + 1
    now = datetime.now()
    threat = {
        'id': threat_id,
        'timestamp': now.strftime('%H:%M:%S'),
        'sourceMac': source_mac,
        'attackType': attack_type,
        'tier': tier,
        'action': action,
    }
    threats.insert(0, threat)
    return dict(threat)
