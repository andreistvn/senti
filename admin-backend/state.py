"""
Admin backend state management using SQLite (via SQLAlchemy) and MultiChain JSON-RPC.

The SQLite `ledger_entries` table is a *mirror* of the MultiChain threat stream, not
the ledger itself: the background worker in multichain.py writes confirmed
transactions into it and periodically reconciles it against what is on-chain, so the
dashboard can render the ledger without blocking on RPC round-trips.
"""

import platform
import threading
import time
import uuid
from datetime import datetime

import psutil
from typing import Optional, Dict, List, Any

from sqlalchemy import create_engine, inspect, text, Column, Integer, String, Float, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

import multichain
from config import (
    DEFAULT_AGENTS,
    SESSION_TIMEOUT_SECONDS,
    MULTICHAIN_ENABLED,
    MULTICHAIN_STREAM_NAME,
    TELEMETRY_SAMPLE_INTERVAL,
    TELEMETRY_SCENARIO,
    TELEMETRY_RECORD,
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
    block_id = Column(String, primary_key=True)   # txid prefix, shown in the dashboard
    txid = Column(String, index=True)             # full MultiChain transaction id
    timestamp = Column(String)
    mac_hash = Column(String)
    score = Column(String)
    created_at = Column(Float)                    # local insert time, for stable ordering

class DBTelemetryReading(Base):
    """
    One resource-consumption sample, kept so the dataset can be analysed later.

    Chapter 3 defines resource consumption as "CPU usage (%) and RAM consumption
    (MB) tracked at one-minute intervals", and the statistical treatment calls for
    the mean, sample variance and an independent-samples t-test over those
    readings. Overwriting a single current value on the agent row — which is what
    used to happen — makes all three impossible, so every sample is appended here.

    `scenario` labels the run (the paper's three traffic scenarios) and `system`
    distinguishes SentiNet from a traditional-IDPS baseline measured the same way,
    which is the comparison the t-test is for.
    """
    __tablename__ = "telemetry_readings"
    id = Column(Integer, primary_key=True, index=True)
    ts = Column(Float, index=True)       # unix time of the sample
    timestamp = Column(String)           # HH:MM:SS, for eyeballing
    source = Column(String, index=True)  # 'relay' or 'agent'
    node = Column(String, index=True)    # hostname or agent name
    mac = Column(String, index=True)     # agents only
    cpu_percent = Column(Float)
    ram_mb = Column(Float)
    ram_percent = Column(Float)          # system-wide, for context
    protected = Column(Boolean)          # agent protection state at sample time
    scenario = Column(String, index=True)
    system = Column(String, index=True)  # 'sentinet' | whatever a baseline is named


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
    cpu = Column(Float)              # percent, of the agent's SentiNet process
    ram = Column(Float)              # percent of system RAM — display only
    ram_mb = Column(Float)           # RSS in MB — the figure the paper specifies
    connected_since = Column(String)
    packets_processed = Column(Integer)

Base.metadata.create_all(bind=engine)


def _migrate_schema():
    """
    Add columns introduced after a database was first created.

    `create_all` only creates missing *tables*, so an existing sentinet.db would
    otherwise keep the old ledger_entries shape and blow up on the new columns.
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    # SQLite types are advisory, so widening cpu/ram from Integer to Float needs
    # no ALTER — only genuinely new columns do.
    additions = {
        'ledger_entries': {'txid': 'VARCHAR', 'created_at': 'FLOAT'},
        'agents': {'ram_mb': 'FLOAT'},
    }

    with engine.begin() as conn:
        for table, columns in additions.items():
            if table not in tables:
                continue
            existing = {col['name'] for col in inspector.get_columns(table)}
            for name, sql_type in columns.items():
                if name not in existing:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {sql_type}'))
                    print(f'[DB] Migrated {table}: added column {name}.')


_migrate_schema()


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

def update_agent_telemetry(
    mac: str,
    cpu: float,
    ram: float,
    agent_state: Optional[str] = None,
    ram_mb: Optional[float] = None,
    protected: Optional[bool] = None,
) -> None:
    """
    Store an agent's latest reading for the dashboard, and append a sample.

    cpu and ram are no longer truncated with int(): a t-test over percentages
    loses real precision if 12.9 is recorded as 12.
    """
    db = SessionLocal()
    node_name = None
    try:
        db_agent = db.query(DBAgent).filter(DBAgent.mac == mac).first()
        if db_agent:
            db_agent.cpu = float(cpu)
            db_agent.ram = float(ram)
            if ram_mb is not None:
                db_agent.ram_mb = float(ram_mb)
            if agent_state:
                db_agent.state = agent_state
            node_name = db_agent.name
            db.commit()
    finally:
        db.close()

    # Only agents reporting MB give us a paper-compliant sample; an older agent
    # build sending percent only is recorded without one rather than guessed at.
    if node_name is not None:
        record_reading(
            source='agent',
            node=node_name,
            cpu_percent=cpu,
            ram_mb=ram_mb if ram_mb is not None else 0.0,
            ram_percent=ram,
            mac=mac,
            protected=protected,
        )


def remove_agent(mac: str) -> None:
    db = SessionLocal()
    db_agent = db.query(DBAgent).filter(DBAgent.mac == mac).first()
    if db_agent:
        db.delete(db_agent)
        db.commit()
    db.close()


# ─── Resource telemetry ────────────────────────────────────────────────────
#
# Chapter 3 wants CPU usage (%) and RAM consumption (MB) at one-minute intervals,
# retained so the mean, sample variance and an independent-samples t-test can be
# computed later. The dashboards refresh every few seconds, so the recorded
# dataset is deliberately sampled on its own slower cadence: live display and the
# paper's dataset are different requirements and shouldn't share a rate.

# The relay is measured HOST-wide, unlike the agents. The agent figure feeds the
# comparison against a traditional IDPS, so it has to isolate SentiNet from
# whatever else the user runs on their own laptop. The relay's figure is not
# research data — it is operational monitoring for an administrator, on a node
# dedicated to hosting the relay. "Is this box coping?" is a host-level question,
# and a host-level answer also captures multichaind and the dashboard server
# without having to enumerate them.
#
# psutil's first cpu_percent() call always returns 0.0 — it needs a prior call to
# measure against. Prime it at import so the first real reading is meaningful.
psutil.cpu_percent(None)

# When each source was last written to telemetry_readings, keyed by 'relay' or a
# MAC. Agents push telemetry roughly every second; only one sample per interval
# is persisted.
_last_recorded: Dict[str, float] = {}
_record_lock = threading.Lock()


def _should_record(key: str, now: float) -> bool:
    """True at most once per TELEMETRY_SAMPLE_INTERVAL per source."""
    if not TELEMETRY_RECORD:
        return False
    with _record_lock:
        last = _last_recorded.get(key)
        if last is not None and (now - last) < TELEMETRY_SAMPLE_INTERVAL:
            return False
        _last_recorded[key] = now
        return True


def record_reading(
    source: str,
    node: str,
    cpu_percent: float,
    ram_mb: float,
    ram_percent: Optional[float] = None,
    mac: Optional[str] = None,
    protected: Optional[bool] = None,
    system: str = 'sentinet',
) -> None:
    """Append one resource-consumption sample. Call freely; rate limiting is here."""
    now = time.time()
    if not _should_record(mac or source, now):
        return

    db = SessionLocal()
    try:
        db.add(DBTelemetryReading(
            ts=now,
            timestamp=datetime.fromtimestamp(now).strftime('%H:%M:%S'),
            source=source,
            node=node,
            mac=mac,
            cpu_percent=float(cpu_percent),
            ram_mb=float(ram_mb),
            ram_percent=float(ram_percent) if ram_percent is not None else None,
            protected=protected,
            scenario=TELEMETRY_SCENARIO or None,
            system=system,
        ))
        db.commit()
    finally:
        db.close()


def measure_relay() -> Dict[str, float]:
    """
    The relay host's CPU and memory.

    Host-wide on purpose — see the note above. ram_mb is memory in use on the
    machine, not one process's RSS, so it is directly comparable to what an
    administrator would see in Task Manager or top.
    """
    mem = psutil.virtual_memory()
    return {
        'cpu_percent': round(psutil.cpu_percent(None), 2),
        'ram_mb': round(mem.used / (1024 * 1024), 2),
        'ram_percent': round(mem.percent, 2),
        'ram_total_mb': round(mem.total / (1024 * 1024), 2),
    }


class RelayTelemetrySampler(threading.Thread):
    """Records the relay's own resource consumption on the paper's interval."""

    def __init__(self) -> None:
        super().__init__(daemon=True, name='relay-telemetry')
        self._stop = threading.Event()
        self.node = platform.node() or 'relay'

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        # Sample more often than we record so a stopped relay exits promptly;
        # record_reading() enforces the real interval.
        while not self._stop.wait(5.0):
            try:
                m = measure_relay()
                record_reading(
                    source='relay',
                    node=self.node,
                    cpu_percent=m['cpu_percent'],
                    ram_mb=m['ram_mb'],
                    ram_percent=m['ram_percent'],
                )
            except Exception as exc:
                print(f'[Telemetry] Relay sample failed: {exc}')


_relay_sampler = RelayTelemetrySampler()


def start_telemetry_sampler() -> None:
    if not TELEMETRY_RECORD:
        print('[Telemetry] Recording disabled (TELEMETRY_RECORD=false).')
        return
    if not _relay_sampler.is_alive():
        _relay_sampler.start()
        label = TELEMETRY_SCENARIO or 'unlabelled'
        print(
            f'[Telemetry] Recording every {TELEMETRY_SAMPLE_INTERVAL:.0f}s '
            f'(scenario: {label}).'
        )


def stop_telemetry_sampler() -> None:
    _relay_sampler.stop()


def get_readings(scenario: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every recorded sample, oldest first — the dataset for the statistics."""
    db = SessionLocal()
    try:
        q = db.query(DBTelemetryReading)
        if scenario:
            q = q.filter(DBTelemetryReading.scenario == scenario)
        rows = q.order_by(DBTelemetryReading.ts.asc()).all()
        return [
            {
                'ts': r.ts,
                'timestamp': r.timestamp,
                'source': r.source,
                'node': r.node,
                'mac': r.mac,
                'cpuPercent': r.cpu_percent,
                'ramMb': r.ram_mb,
                'ramPercent': r.ram_percent,
                'protected': r.protected,
                'scenario': r.scenario,
                'system': r.system,
            } for r in rows
        ]
    finally:
        db.close()


# ─── MultiChain Integration ────────────────────────────────────────────────

def _mirror_ledger_entry(entry: Dict[str, Any]) -> None:
    """
    Persist one confirmed on-chain publication into the local mirror.

    Called from the ledger worker thread once MultiChain has accepted the
    transaction, so a row here always corresponds to a real txid.
    """
    db = SessionLocal()
    try:
        existing = db.query(DBLedgerEntry).filter(DBLedgerEntry.block_id == entry['blockId']).first()
        if existing:
            existing.txid = entry.get('txid', existing.txid)
            existing.timestamp = entry['timestamp']
            existing.mac_hash = entry['macHash']
            existing.score = entry['score']
        else:
            db.add(DBLedgerEntry(
                block_id=entry['blockId'],
                txid=entry.get('txid'),
                timestamp=entry['timestamp'],
                mac_hash=entry['macHash'],
                score=entry['score'],
                created_at=time.time(),
            ))
        db.commit()
    finally:
        db.close()


def _reconcile_ledger(entries: List[Dict[str, Any]]) -> None:
    """
    Fold the stream items read back from the chain into the local mirror.

    Anything published by a *peer* relay node arrives through here, which is what
    keeps the Bayanihan ledger view consistent across the federation rather than
    showing only this node's own writes.
    """
    if not entries:
        return

    db = SessionLocal()
    try:
        known = {row.block_id for row in db.query(DBLedgerEntry.block_id).all()}
        now = time.time()
        added = 0

        for entry in entries:
            if entry['blockId'] in known:
                continue
            db.add(DBLedgerEntry(
                block_id=entry['blockId'],
                txid=entry.get('txid'),
                timestamp=entry['timestamp'],
                mac_hash=entry['macHash'],
                score=entry['score'],
                created_at=now,
            ))
            known.add(entry['blockId'])
            added += 1

        if added:
            db.commit()
            print(f'[MultiChain] Reconciled {added} ledger entr{"y" if added == 1 else "ies"} from the chain.')
    finally:
        db.close()


# The client and worker own every blocking RPC call; nothing on the request path
# talks to the node directly.
_client = multichain.MultiChainClient()
_ledger_worker = multichain.LedgerWorker(
    _client,
    on_published=_mirror_ledger_entry,
    on_reconciled=_reconcile_ledger,
)


def start_ledger_worker() -> None:
    """Start the MultiChain publisher/sync thread. Called from the FastAPI lifespan."""
    if not MULTICHAIN_ENABLED:
        print('[MultiChain] Disabled via MULTICHAIN_ENABLED=false — ledger writes will be skipped.')
        return
    _ledger_worker.start()


def stop_ledger_worker() -> None:
    """Stop the worker and release the HTTP session on shutdown."""
    if not MULTICHAIN_ENABLED:
        return
    _ledger_worker.stop()


def get_chain_status() -> Dict[str, Any]:
    """Cached MultiChain health, refreshed by the worker's heartbeat."""
    snapshot = _ledger_worker.snapshot()
    snapshot['enabled'] = MULTICHAIN_ENABLED
    snapshot['stream'] = MULTICHAIN_STREAM_NAME
    snapshot['rpcUrl'] = _client.url
    return snapshot


def write_to_multichain(threat_dict: dict) -> bool:
    """
    Queue threat metadata for publication to the permissioned MultiChain stream.

    Returns immediately — the actual JSON-RPC `publish` happens on the worker
    thread. This is deliberate: add_threat() runs inside the Socket.io event loop,
    and a synchronous RPC there would stall blacklist broadcasts to every other
    agent for the duration of the call (and for the full timeout if the node is
    down), which is exactly when Tier 1 propagation matters most.
    """
    if not MULTICHAIN_ENABLED:
        return False

    return _ledger_worker.submit({
        'timestamp': threat_dict['timestamp'],
        'sourceMac': threat_dict['sourceMac'],
        'attackType': threat_dict.get('attackType', 'Unknown'),
        'tier': threat_dict.get('tier', 'Tier 3'),
        'action': threat_dict.get('action', 'Blocked'),
        'confidence': threat_dict.get('confidence', '99.9%'),
    })


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
            'ramMb': a.ram_mb,
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
    """
    Read the ledger mirror, newest first.

    Served from SQLite rather than a live `liststreamitems` call so the dashboard's
    polling never blocks on the chain; the worker keeps this table in step with the
    stream on every sync interval.
    """
    db = SessionLocal()
    db_ledger = db.query(DBLedgerEntry).order_by(
        DBLedgerEntry.created_at.desc(),
        DBLedgerEntry.timestamp.desc(),
    ).all()
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
    mirror_count = db.query(DBLedgerEntry).count()
    newest = db.query(DBLedgerEntry).order_by(
        DBLedgerEntry.created_at.desc(),
        DBLedgerEntry.timestamp.desc(),
    ).first()
    db.close()

    # The dashboard tile is labelled "Relay Node CPU", so report the relay's own
    # process usage. This used to be the mean across all connected agents, which
    # was both mislabelled and redundant — per-agent figures are already in the
    # agent list, and Chapter 3 asks for each node's own footprint.
    relay = measure_relay()

    chain = get_chain_status()
    chain_live = chain['enabled'] and chain['online'] and chain['streamReady']

    # Real block height when we're talking to the node; fall back to the mirror's
    # row count so the POC still shows something meaningful while DEGRADED.
    block_height = chain['blockHeight'] if chain_live else mirror_count

    if chain_live and chain['lastSyncAt']:
        last_sync = datetime.fromtimestamp(chain['lastSyncAt']).strftime('%H:%M:%S')
    elif newest:
        last_sync = newest.timestamp
    else:
        last_sync = "--:--:--"

    return {
        'cpu': relay['cpu_percent'],
        'ram': relay['ram_percent'],
        'ramMb': relay['ram_mb'],
        'ramTotalMb': relay['ram_total_mb'],
        'latency': chain['latencyMs'] if chain_live else 0,
        'blockHeight': block_height,
        'lastSyncTime': last_sync,
        'chainStatus': 'HEALTHY' if chain_live else 'DEGRADED',
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
