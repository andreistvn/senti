"""
Admin backend state management using SQLite (via SQLAlchemy) and MultiChain JSON-RPC.
"""

import time
import uuid
import requests
from datetime import datetime
from typing import Optional, Dict, List, Any

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

from config import (
    DEFAULT_AGENTS, 
    SESSION_TIMEOUT_SECONDS,
    MULTICHAIN_RPC_URL,
    MULTICHAIN_RPC_USER,
    MULTICHAIN_RPC_PASSWORD,
    MULTICHAIN_STREAM_NAME
)

# Admin credentials (kept in memory for POC)
ADMIN_CREDENTIALS = {
    'ADM-7734-ALPHA': 'SentiNet@2049',
}

# In-memory stores for items that don't need persistence right now
policy_config = {
    'mlThreshold': 0.50,
    'arpFloodLimit': 1000,
    'autoBlacklist': False,
    'syncInterval': 4000,
    'logRetentionDays': 30,
}

telemetry_summary = {
    'cpu': 12,
    'ram': 44,
    'latency': 14,
    'blockHeight': 33912,
    'lastSyncTime': '14:30:05',
    'chainStatus': 'HEALTHY',
    'totalIncidents': 0,
}

threat_history = [
    {'time': f'{14 + i // 4:02d}:{(i * 15) % 60:02d}:00', 'pps': 40 + (i * 7) % 180, 'blocked': 30 + (i * 5) % 140}
    for i in range(20)
]

# ─── SQLAlchemy Setup ────────────────────────────────────────────────────────

engine = create_engine('sqlite:///sentinet.db', connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DBSession(Base):
    __tablename__ = "sessions"
    token = Column(String, primary_key=True, index=True)
    digital_id = Column(String, index=True)
    created_at = Column(Float)
    last_accessed = Column(Float)

class DBThreat(Base):
    __tablename__ = "threats"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(String)
    source_mac = Column(String, index=True)
    attack_type = Column(String)
    tier = Column(String)
    action = Column(String)

class DBLedgerEntry(Base):
    __tablename__ = "ledger_entries"
    block_id = Column(String, primary_key=True)
    timestamp = Column(String)
    mac_hash = Column(String)
    score = Column(String)

class DBPolicy(Base):
    __tablename__ = "policy"
    id = Column(Integer, primary_key=True)
    ml_threshold = Column(Float)
    arp_flood_limit = Column(Integer)
    auto_blacklist = Column(Boolean)
    sync_interval = Column(Integer)
    log_retention_days = Column(Integer)

class DBAgent(Base):
    __tablename__ = "agents"
    id = Column(String, primary_key=True)
    name = Column(String)
    ip = Column(String)
    mac = Column(String)
    state = Column(String)
    sync_progress = Column(Integer)
    cpu = Column(Integer)
    ram = Column(Integer)
    connected_since = Column(String)
    packets_processed = Column(Integer)

Base.metadata.create_all(bind=engine)

def _seed_db():
    db = SessionLocal()
    if db.query(DBPolicy).count() == 0:
        db.add(DBPolicy(
            id=1,
            ml_threshold=0.50,
            arp_flood_limit=1000,
            auto_blacklist=False,
            sync_interval=4000,
            log_retention_days=30
        ))
    db.commit()
    db.close()

_seed_db()

def upsert_agent(agent_data: Dict[str, Any]) -> None:
    db = SessionLocal()
    mac = agent_data.get('mac')
    if not mac:
        db.close()
        return
        
    db_agent = db.query(DBAgent).filter(DBAgent.mac == mac).first()
    if not db_agent:
        now = datetime.now().strftime('%H:%M:%S')
        db_agent = DBAgent(
            id=str(uuid.uuid4())[:8].upper(),
            name=agent_data.get('name', 'Unknown Agent'),
            ip=agent_data.get('ip', 'Unknown IP'),
            mac=mac,
            state=agent_data.get('state', 'PROTECTED'),
            sync_progress=0,
            cpu=0,
            ram=0,
            connected_since=now,
            packets_processed=0
        )
        db.add(db_agent)
    else:
        db_agent.ip = agent_data.get('ip', db_agent.ip)
        db_agent.state = agent_data.get('state', db_agent.state)
        
    db.commit()
    db.close()

def update_agent_telemetry(mac: str, cpu: float, ram: float, agent_state: Optional[str] = None) -> None:
    db = SessionLocal()
    db_agent = db.query(DBAgent).filter(DBAgent.mac == mac).first()
    if db_agent:
        db_agent.cpu = int(cpu)
        db_agent.ram = int(ram)
        if agent_state:
            db_agent.state = agent_state
        db.commit()
    db.close()


def remove_agent(mac: str) -> None:
    db = SessionLocal()
    db_agent = db.query(DBAgent).filter(DBAgent.mac == mac).first()
    if db_agent:
        db.delete(db_agent)
        db.commit()
    db.close()


# ─── MultiChain Integration ────────────────────────────────────────────────

def write_to_multichain(threat_dict: dict):
    """
    Write threat metadata to the permissioned MultiChain stream via JSON-RPC.
    """
    payload = {
        "method": "publish",
        "params": [
            MULTICHAIN_STREAM_NAME,
            threat_dict["sourceMac"], # Key
            {
                "json": {
                    "timestamp": threat_dict["timestamp"],
                    "attackType": threat_dict["attackType"],
                    "score": threat_dict.get("confidence", "99.9%")
                }
            }
        ],
        "id": str(uuid.uuid4())
    }
    
    try:
        response = requests.post(
            MULTICHAIN_RPC_URL,
            json=payload,
            auth=(MULTICHAIN_RPC_USER, MULTICHAIN_RPC_PASSWORD),
            timeout=2.0
        )
        if response.status_code == 200:
            result = response.json().get("result")
            print(f"[MultiChain] Successfully published threat to stream: {result}")
            
            # Log the ledger entry in our SQLite DB for the dashboard
            db = SessionLocal()
            db_ledger = DBLedgerEntry(
                block_id=result[:8] if result else "0xNEW", # Use txid snippet as blockId for POC
                timestamp=threat_dict["timestamp"],
                mac_hash=threat_dict["sourceMac"],
                score=threat_dict.get("confidence", "99.9%")
            )
            db.add(db_ledger)
            db.commit()
            db.close()
        else:
            print(f"[MultiChain] RPC Error ({response.status_code}): {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"[MultiChain] Connection Error: {e}")
        print("[MultiChain] Warning: Is your MultiChain node running? Skipping ledger write for now.")


# ─── Data Access Methods ───────────────────────────────────────────────────

def create_session(digital_id: str) -> str:
    db = SessionLocal()
    session_token = f'{digital_id}_{int(time.time())}_{id(object())}'
    now = time.time()
    db_session = DBSession(token=session_token, digital_id=digital_id, created_at=now, last_accessed=now)
    db.add(db_session)
    db.commit()
    db.close()
    return session_token


def validate_session(session_token: str) -> Optional[str]:
    db = SessionLocal()
    db_session = db.query(DBSession).filter(DBSession.token == session_token).first()
    
    if not db_session:
        db.close()
        return None

    elapsed = time.time() - db_session.created_at
    if elapsed > SESSION_TIMEOUT_SECONDS:
        db.delete(db_session)
        db.commit()
        db.close()
        return None

    db_session.last_accessed = time.time()
    db.commit()
    digital_id = db_session.digital_id
    db.close()
    return digital_id


def destroy_session(session_token: str) -> None:
    db = SessionLocal()
    db_session = db.query(DBSession).filter(DBSession.token == session_token).first()
    if db_session:
        db.delete(db_session)
        db.commit()
    db.close()


def get_agents() -> List[Dict[str, Any]]:
    db = SessionLocal()
    db_agents = db.query(DBAgent).all()
    results = [
        {
            'id': a.id,
            'name': a.name,
            'ip': a.ip,
            'mac': a.mac,
            'state': a.state,
            'syncProgress': a.sync_progress,
            'cpu': a.cpu,
            'ram': a.ram,
            'connectedSince': a.connected_since,
            'packetsProcessed': a.packets_processed
        } for a in db_agents
    ]
    db.close()
    return results


def get_threats() -> List[Dict[str, Any]]:
    db = SessionLocal()
    db_threats = db.query(DBThreat).order_by(DBThreat.id.desc()).all()
    results = [
        {
            'id': t.id,
            'timestamp': t.timestamp,
            'sourceMac': t.source_mac,
            'attackType': t.attack_type,
            'tier': t.tier,
            'action': t.action
        } for t in db_threats
    ]
    db.close()
    return results


def get_ledger() -> List[Dict[str, Any]]:
    db = SessionLocal()
    db_ledger = db.query(DBLedgerEntry).all()
    results = [
        {
            'blockId': l.block_id,
            'timestamp': l.timestamp,
            'macHash': l.mac_hash,
            'score': l.score
        } for l in db_ledger
    ]
    db.close()
    return results


def get_policy() -> Dict[str, Any]:
    db = SessionLocal()
    db_policy = db.query(DBPolicy).first()
    result = {}
    if db_policy:
        result = {
            'mlThreshold': db_policy.ml_threshold,
            'arpFloodLimit': db_policy.arp_flood_limit,
            'autoBlacklist': db_policy.auto_blacklist,
            'syncInterval': db_policy.sync_interval,
            'logRetentionDays': db_policy.log_retention_days,
        }
    db.close()
    return result


def set_policy(new_config: Dict[str, Any]) -> Dict[str, Any]:
    db = SessionLocal()
    db_policy = db.query(DBPolicy).first()
    if db_policy:
        if 'mlThreshold' in new_config:
            db_policy.ml_threshold = new_config['mlThreshold']
        if 'arpFloodLimit' in new_config:
            db_policy.arp_flood_limit = new_config['arpFloodLimit']
        if 'autoBlacklist' in new_config:
            db_policy.auto_blacklist = new_config['autoBlacklist']
        if 'syncInterval' in new_config:
            db_policy.sync_interval = new_config['syncInterval']
        if 'logRetentionDays' in new_config:
            db_policy.log_retention_days = new_config['logRetentionDays']
        db.commit()
    db.close()
    return get_policy()


def get_telemetry_summary() -> Dict[str, Any]:
    db = SessionLocal()
    count = db.query(DBThreat).count()
    agents = db.query(DBAgent).all()
    ledger_entries = db.query(DBLedgerEntry).order_by(DBLedgerEntry.timestamp.desc()).all()
    db.close()
    
    avg_cpu = int(sum(a.cpu for a in agents) / len(agents)) if agents else 0
    avg_ram = int(sum(a.ram for a in agents) / len(agents)) if agents else 0
    
    block_height = len(ledger_entries)
    last_sync = ledger_entries[0].timestamp if ledger_entries else "--:--:--"
    
    return {
        'cpu': avg_cpu,
        'ram': avg_ram,
        'latency': 5 if block_height > 0 else 0,
        'blockHeight': block_height,
        'lastSyncTime': last_sync,
        'chainStatus': 'HEALTHY',
        'totalIncidents': count
    }


def get_threat_history() -> List[Dict[str, Any]]:
    db = SessionLocal()
    db_threats = db.query(DBThreat).order_by(DBThreat.id.asc()).all()
    db.close()
    
    grouped = {}
    for t in db_threats:
        # group by minute for the chart
        minute = t.timestamp[:5] + ":00"
        grouped[minute] = grouped.get(minute, 0) + 1
        
    history = []
    for time_str, count in grouped.items():
        history.append({
            'time': time_str,
            'pps': count * 10,
            'blocked': count
        })
    return history


def add_threat(source_mac: str, attack_type: str, tier: str, action: str, confidence: str = "99.9%") -> Dict[str, Any]:
    db = SessionLocal()
    now = datetime.now().strftime('%H:%M:%S')
    db_threat = DBThreat(
        timestamp=now,
        source_mac=source_mac,
        attack_type=attack_type,
        tier=tier,
        action=action
    )
    db.add(db_threat)
    db.commit()
    db.refresh(db_threat)
    
    threat_dict = {
        'id': db_threat.id,
        'timestamp': db_threat.timestamp,
        'sourceMac': db_threat.source_mac,
        'attackType': db_threat.attack_type,
        'tier': db_threat.tier,
        'action': db_threat.action,
        'confidence': confidence
    }
    db.close()
    
    # Try publishing to MultiChain
    write_to_multichain(threat_dict)
    
    return threat_dict
