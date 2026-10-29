"""
Admin backend state management using SQLite (via SQLAlchemy) and MultiChain JSON-RPC.

The SQLite `ledger_entries` table is a *mirror* of the MultiChain threat stream, not
the ledger itself: the background worker in multichain.py writes confirmed
transactions into it and periodically reconciles it against what is on-chain, so the
dashboard can render the ledger without blocking on RPC round-trips.
"""

import hashlib
import platform
import secrets
import statistics
import threading
import time
import uuid
from datetime import datetime

import psutil
from typing import Optional, Dict, List, Any

from sqlalchemy import create_engine, inspect, text, or_, Column, Integer, String, Float, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

import multichain
from config import (
    DEFAULT_AGENTS,
    SESSION_TIMEOUT_SECONDS,
    SESSION_MAX_AGE_SECONDS,
    AGENT_STALE_SECONDS,
    MULTICHAIN_ENABLED,
    MULTICHAIN_STREAM_NAME,
    TELEMETRY_SAMPLE_INTERVAL,
    TELEMETRY_SCENARIO,
    TELEMETRY_RECORD,
    SOP_ATTACKER_MACS,
)


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
    detail = Column(String, nullable=True)  # e.g. "blocked via Bayanihan, reported by Agent A at 14:02:08"
    # The model's score as the agent sent it ("87.3%"), or "N/A" for a repeat
    # block that carries none. Shown per row in Detection Logs and Reports.
    confidence = Column(String, nullable=True)
    # Agent-generated uuid4, carried end-to-end from CaptureEngine. Lets add_threat()
    # dedupe: once agent-side reporting can retry (BayanihanClient's pending-report
    # queue) and backfill on reconnect (register_agent's recentEvents), the same
    # detection can legitimately arrive here more than once.
    client_event_id = Column(String, nullable=True, index=True)
    # When the relay received it. `timestamp` above is a clock time with no date,
    # so it cannot place a report on a day; this can (Analytics tab).
    created_ts = Column(Float, nullable=True, index=True)

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


class DBTtbDetection(Base):
    """
    One first-detection of an attacker, the start of a Time-to-Block measurement.

    Chapter 3 defines TTB = t_enforced - t_detected, where t_detected is when
    Tier 2 at the detecting node (Node A) first classified the MAC as malicious.
    That timestamp is taken on the agent and carried here in the attack report.
    `relay_received_ms` is the relay's own clock at ingest, kept so a TTB can
    still be derived on a single clock if the agents' clocks are not in sync.
    """
    __tablename__ = "ttb_detections"
    event_id = Column(String, primary_key=True)   # the report's clientEventId
    attacker_mac = Column(String, index=True)
    detected_by = Column(String)                  # detecting agent's name (or MAC)
    t_detected_ms = Column(Float)                 # agent clock, epoch ms
    relay_received_ms = Column(Float)             # relay clock, epoch ms
    agent_delay_ms = Column(Float, nullable=True) # detection -> hand-off, on the agent's clock
    created_ts = Column(Float, index=True)


class DBTtbEnforcement(Base):
    """
    One other node writing that attacker into its Tier-1 blacklist — t_enforced.

    A detection has one row here per node that enforced it, so a single trial on
    a three-agent testbed yields two TTB measurements.
    """
    __tablename__ = "ttb_enforcements"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, index=True)
    enforced_by = Column(String)                  # enforcing agent's name
    enforced_by_mac = Column(String, index=True)
    t_enforced_ms = Column(Float)                 # agent clock, epoch ms
    relay_acked_ms = Column(Float)                # relay clock, epoch ms
    agent_delay_ms = Column(Float, nullable=True) # enforcement -> hand-off, on the agent's clock


class DBBlacklistEntry(Base):
    """
    The network-wide blacklist held by the relay.

    Previously the relay forwarded each MAC as it arrived and kept no record, so
    an agent connecting after a threat was reported started empty and never
    caught up. Persisting the list lets the relay replay it on connect, which is
    the "shared intelligence" half of the Bayanihan layer.
    """
    __tablename__ = "blacklist"
    mac = Column(String, primary_key=True)
    first_seen = Column(String)          # HH:MM:SS
    first_seen_ts = Column(Float, index=True)
    reported_by = Column(String)         # agent that detected it first
    attack_type = Column(String)
    confidence = Column(String)
    tier = Column(String)


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
    ram_process_percent = Column(Float, nullable=True)  # that RSS as a share of the agent machine's RAM
    connected_since = Column(String)
    packets_processed = Column(Integer)
    last_seen = Column(Float, nullable=True)  # unix time of the last register/telemetry; see get_agents()

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
        'agents': {'ram_mb': 'FLOAT', 'last_seen': 'FLOAT', 'ram_process_percent': 'FLOAT'},
        'threats': {'detail': 'VARCHAR', 'client_event_id': 'VARCHAR', 'created_ts': 'FLOAT', 'confidence': 'VARCHAR'},
        'ttb_detections': {'agent_delay_ms': 'FLOAT'},
        'ttb_enforcements': {'agent_delay_ms': 'FLOAT'},
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
            packets_processed=0,
            last_seen=time.time(),
        )
        db.add(db_agent)
    else:
        db_agent.ip = agent_data.get('ip', db_agent.ip)
        db_agent.state = agent_data.get('state', db_agent.state)
        db_agent.last_seen = time.time()

    db.commit()
    db.close()

def update_agent_telemetry(
    mac: str,
    cpu: float,
    ram: float,
    agent_state: Optional[str] = None,
    ram_mb: Optional[float] = None,
    protected: Optional[bool] = None,
    scenario: Optional[str] = None,
    ram_process_percent: Optional[float] = None,
    attack_detected: Optional[float] = None,
    attack_blocked: Optional[float] = None,
    enforcement: Optional[str] = None,
    confusion: Optional[Dict[str, Any]] = None,
    detection_latency: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Store an agent's latest reading for the dashboard, and append a sample.

    `scenario` is the traffic scenario the agent says it is experiencing, which
    labels the appended sample (see record_reading) and the SOP 1 snapshot.

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
            if ram_process_percent is not None:
                db_agent.ram_process_percent = float(ram_process_percent)
            if agent_state:
                db_agent.state = agent_state
            db_agent.last_seen = time.time()
            node_name = db_agent.name
            db.commit()
    finally:
        db.close()

    # Only agents reporting MB give us a paper-compliant sample; an older agent
    # build sending percent only is recorded without one rather than guessed at.
    if node_name is not None:
        _take_sop_snapshot(mac, node_name, cpu, ram_mb, protected, scenario)
        _note_sop_packets(mac, node_name, attack_detected, attack_blocked, enforcement)
        _note_sop_confusion(mac, node_name, confusion, detection_latency)
        record_reading(
            source='agent',
            node=node_name,
            cpu_percent=cpu,
            ram_mb=ram_mb if ram_mb is not None else 0.0,
            ram_percent=ram,
            mac=mac,
            protected=protected,
            scenario=scenario,
        )


def remove_agent(mac: str) -> None:
    with _record_lock:
        _sop_agents.pop(mac, None)
    db = SessionLocal()
    db_agent = db.query(DBAgent).filter(DBAgent.mac == mac).first()
    if db_agent:
        db.delete(db_agent)
        db.commit()
    db.close()


# ─── Network blacklist ──────────────────────────────────────────────────────

def add_to_blacklist(
    mac: str,
    reported_by: str = 'unknown',
    attack_type: str = 'Unknown',
    confidence: str = 'N/A',
    tier: str = 'Tier 2',
) -> bool:
    """
    Record a MAC on the network-wide blacklist.

    Returns True if this is the first time it has been seen, so the caller can
    decide whether a broadcast is warranted.
    """
    if not mac:
        return False

    db = SessionLocal()
    try:
        existing = db.query(DBBlacklistEntry).filter(DBBlacklistEntry.mac == mac).first()
        if existing:
            return False

        now = time.time()
        db.add(DBBlacklistEntry(
            mac=mac,
            first_seen=datetime.fromtimestamp(now).strftime('%H:%M:%S'),
            first_seen_ts=now,
            reported_by=reported_by,
            attack_type=attack_type,
            confidence=confidence,
            tier=tier,
        ))
        db.commit()
        return True
    finally:
        db.close()


def get_blacklist() -> List[Dict[str, Any]]:
    """The whole blacklist, newest first."""
    db = SessionLocal()
    try:
        rows = db.query(DBBlacklistEntry).order_by(DBBlacklistEntry.first_seen_ts.desc()).all()
        return [
            {
                'mac': r.mac,
                'firstSeen': r.first_seen,
                'reportedBy': r.reported_by,
                'attackType': r.attack_type,
                'confidence': r.confidence,
                'tier': r.tier,
            } for r in rows
        ]
    finally:
        db.close()


def clear_blacklist() -> int:
    """Drop every entry. Used by flush_db between demo runs."""
    db = SessionLocal()
    try:
        n = db.query(DBBlacklistEntry).delete()
        db.commit()
        return n
    finally:
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
# CPU is derived from successive psutil.cpu_times() samples rather than
# psutil.cpu_percent(), which rounds to one decimal. Primed at import so the
# first real reading has something to measure against.
_RELAY_CPU_MIN_WINDOW = 0.5  # seconds; a shorter window is mostly timer noise
_relay_cpu_lock = threading.Lock()


def _relay_cpu_times() -> tuple:
    """(monotonic seconds, total CPU seconds, busy CPU seconds) for the host."""
    t = psutil.cpu_times()
    # Linux counts guest time inside user, and iowait is idle, not work.
    total = sum(t) - getattr(t, 'guest', 0.0) - getattr(t, 'guest_nice', 0.0)
    idle = t.idle + getattr(t, 'iowait', 0.0)
    return (time.monotonic(), total, total - idle)


_relay_cpu_sample = _relay_cpu_times()
_relay_cpu_last = 0.0


def _relay_cpu_percent() -> float:
    """Host CPU busy share since the previous sample, unrounded."""
    global _relay_cpu_sample, _relay_cpu_last
    with _relay_cpu_lock:
        now, total, busy = _relay_cpu_times()
        then, total_before, busy_before = _relay_cpu_sample
        # Two callers share this (the recorder and the summary endpoint); a
        # call landing right after another reuses that reading.
        if now - then < _RELAY_CPU_MIN_WINDOW or total <= total_before:
            return _relay_cpu_last
        _relay_cpu_sample = (now, total, busy)
        _relay_cpu_last = min(100.0, max(0.0, (busy - busy_before) / (total - total_before) * 100))
        return _relay_cpu_last

# When each source was last written to telemetry_readings, keyed by 'relay' or a
# MAC, plus the scenario label. Agents push telemetry roughly every second; only
# one sample per interval is persisted per scenario — keying on the scenario too
# means an agent that goes from normal traffic to under attack gets a reading
# for the new scenario straight away rather than up to a minute later.
_last_recorded: Dict[str, float] = {}
_record_lock = threading.Lock()

# The connected agents, keyed by MAC in the order they connected. The SOP tab
# reports on one agent only — the first in this dict — since several would give
# several competing sets of figures; when it disconnects the next in line takes
# over. Only that agent accumulates anything: a CPU/RAM snapshot of its telemetry
# every TELEMETRY_SAMPLE_INTERVAL per traffic scenario (SOP 1), and a count of
# its detections (SOP 2). So an agent that takes over starts from fresh readings.
# In memory only, so the tab also starts empty whenever the relay is restarted.
_sop_agents: Dict[str, Dict[str, Any]] = {}


def _sop_entry_locked(mac: str, name: str) -> Dict[str, Any]:
    """This agent's entry, created at the back of the line if new. Hold _record_lock."""
    entry = _sop_agents.get(mac)
    if entry is None:
        entry = _sop_agents[mac] = {
            'evaluation': None,
            'scenario': None,
            'snapshots': {s: {'cpu': [], 'ram': []} for s in SOP_SCENARIOS},
            'last_snapshot': {},
            # The agent's running attack-packet counts, and what they stood at
            # when it became the reporting agent — SOP 2 shows the difference.
            'packets': None,
            'packets_base': None,
            'enforcement': None,
            # Live confusion matrix tallies (tp, fp, tn, fn), with the same kind
            # of baseline, and the agent's most recent detection latency.
            'confusion': None,
            'confusion_base': None,
            'latency': None,
        }
    entry['name'] = name
    entry['last_seen'] = time.time()
    return entry


def _sop_head_locked() -> Optional[str]:
    """
    MAC of the agent the SOP tab reports on. Hold _record_lock.

    An agent whose heartbeat has gone stale without a disconnect event is
    dropped here, so a ghost cannot hold the front of the line.
    """
    cutoff = time.time() - AGENT_STALE_SECONDS
    for mac in [m for m, e in _sop_agents.items() if e['last_seen'] < cutoff]:
        del _sop_agents[mac]
    return next(iter(_sop_agents), None)


def register_sop_agent(mac: str, name: str, evaluation: Optional[Dict[str, Any]]) -> None:
    """
    Put a newly registered agent in line, with the held-out test set figures it
    computed for its own model at start-up (SOP 2's confusion matrix).
    """
    with _record_lock:
        entry = _sop_entry_locked(mac, name)
        if isinstance(evaluation, dict):
            entry['evaluation'] = evaluation


def _note_sop_packets(
    mac: str,
    name: str,
    detected: Optional[float],
    blocked: Optional[float],
    enforcement: Optional[str],
) -> None:
    """
    Keep the reporting agent's latest attack-packet counts for SOP 2's
    prevention rate (Chapter 3, Equation 4).

    The agent counts since it started; the baseline taken when it becomes the
    reporting agent makes the SOP tab count from that moment, like its CPU/RAM
    snapshots. An agent that restarts counts from zero again, so the baseline
    is retaken if its figures go backwards.
    """
    if not isinstance(detected, (int, float)) or not isinstance(blocked, (int, float)):
        return
    with _record_lock:
        entry = _sop_entry_locked(mac, name)
        entry['enforcement'] = enforcement
        if mac != _sop_head_locked():
            return
        base = entry['packets_base']
        if base is None or detected < base[0] or blocked < base[1]:
            entry['packets_base'] = (detected, blocked)
        entry['packets'] = (detected, blocked)


_CONFUSION_KEYS = ('tp', 'fp', 'tn', 'fn')


def _note_sop_confusion(
    mac: str,
    name: str,
    confusion: Optional[Dict[str, Any]],
    latency: Optional[Dict[str, Any]],
) -> None:
    """
    Keep the reporting agent's live confusion-matrix tallies, relative to what
    they stood at when it became the reporting agent (as with its packet counts).
    """
    with _record_lock:
        entry = _sop_entry_locked(mac, name)
        if mac != _sop_head_locked():
            return
        if isinstance(latency, dict):
            entry['latency'] = latency
        if not isinstance(confusion, dict):
            # The agent is not scoring: no attacker declared, or an older build.
            entry['confusion'] = entry['confusion_base'] = None
            return
        try:
            counts = tuple(int(confusion.get(k, 0)) for k in _CONFUSION_KEYS)
        except (TypeError, ValueError):
            return
        base = entry['confusion_base']
        if base is None or any(c < b for c, b in zip(counts, base)):
            entry['confusion_base'] = counts
        entry['confusion'] = counts


def _take_sop_snapshot(
    mac: str,
    name: str,
    cpu: float,
    ram_mb: Optional[float],
    protected: Optional[bool],
    scenario: Optional[str],
) -> None:
    """Note an agent's current scenario, and keep one snapshot per interval."""
    now = time.time()
    label = _canonical_scenario(TELEMETRY_SCENARIO or scenario)
    with _record_lock:
        entry = _sop_entry_locked(mac, name)
        entry['scenario'] = label
        if mac != _sop_head_locked():
            return

        # Only an agent reporting MB gives a paper-compliant figure, and only
        # while protection is on is it SentiNet's working footprint.
        if label is None or ram_mb is None or protected is False:
            return
        # Per scenario, so an agent that comes under attack gets a snapshot for
        # the new scenario straight away rather than up to a minute later.
        last = entry['last_snapshot'].get(label)
        if last is not None and (now - last) < TELEMETRY_SAMPLE_INTERVAL:
            return
        entry['last_snapshot'][label] = now
        entry['snapshots'][label]['cpu'].append(float(cpu))
        entry['snapshots'][label]['ram'].append(float(ram_mb))


def _current_sop_agent() -> Optional[Dict[str, Any]]:
    """A copy of what has accumulated for the agent the SOP tab reports on."""
    with _record_lock:
        mac = _sop_head_locked()
        if mac is None:
            return None
        entry = _sop_agents[mac]
        return {
            'name': entry['name'],
            'scenario': entry['scenario'],
            'evaluation': entry['evaluation'],
            'packets': entry['packets'],
            'packets_base': entry['packets_base'],
            'enforcement': entry['enforcement'],
            'confusion': entry['confusion'],
            'confusion_base': entry['confusion_base'],
            'latency': entry['latency'],
            'snapshots': {s: {k: list(v) for k, v in entry['snapshots'][s].items()} for s in SOP_SCENARIOS},
        }


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
    scenario: Optional[str] = None,
) -> None:
    """
    Append one resource-consumption sample. Call freely; rate limiting is here.

    The label is TELEMETRY_SCENARIO when that is set — a manual override for a
    formal run — and otherwise the scenario the agent reported for itself.
    """
    now = time.time()
    label = TELEMETRY_SCENARIO or scenario or None
    if not _should_record(f"{mac or source}|{label or ''}", now):
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
            scenario=label,
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

    # In-use is total - available, NOT mem.used. psutil's `percent` is defined as
    # (total - available) / total, while `used` excludes cached and inactive
    # pages — on macOS the two differ enormously (6.0 GB vs 12.4 GB on a 16 GB
    # machine). Reporting `used` next to a bar driven by `percent` made the
    # number and the bar disagree, and made the relay tile contradict the agent
    # dashboard's gauge, which was already using `percent`.
    in_use = mem.total - mem.available

    return {
        'cpu_percent': round(_relay_cpu_percent(), 5),
        'ram_mb': round(in_use / (1024 * 1024), 2),
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


# ─── Time-to-Block (SOP 3) ─────────────────────────────────────────────────

def agent_name_for(mac: Optional[str]) -> Optional[str]:
    """The registered name of the agent with this MAC, if it is known."""
    if not mac:
        return None
    db = SessionLocal()
    try:
        row = db.query(DBAgent).filter(DBAgent.mac == mac).first()
        return row.name if row else None
    finally:
        db.close()


def record_ttb_detection(
    event_id: str,
    attacker_mac: str,
    detected_by: str,
    t_detected_ms: float,
    relay_received_ms: float,
    agent_delay_ms: Optional[float] = None,
) -> None:
    """Record t_detected for a first detection. Idempotent on the event id."""
    db = SessionLocal()
    try:
        if db.query(DBTtbDetection).filter(DBTtbDetection.event_id == event_id).first():
            return
        db.add(DBTtbDetection(
            event_id=event_id,
            attacker_mac=attacker_mac,
            detected_by=detected_by,
            t_detected_ms=float(t_detected_ms),
            relay_received_ms=float(relay_received_ms),
            agent_delay_ms=agent_delay_ms,
            created_ts=time.time(),
        ))
        db.commit()
    finally:
        db.close()


def record_ttb_enforcement(
    event_id: str,
    enforced_by: str,
    enforced_by_mac: str,
    t_enforced_ms: float,
    relay_acked_ms: float,
    agent_delay_ms: Optional[float] = None,
) -> bool:
    """
    Record t_enforced for one node. Returns False if the detection is unknown or
    this node has already been recorded for it.
    """
    db = SessionLocal()
    try:
        if not db.query(DBTtbDetection).filter(DBTtbDetection.event_id == event_id).first():
            return False
        duplicate = db.query(DBTtbEnforcement).filter(
            DBTtbEnforcement.event_id == event_id,
            DBTtbEnforcement.enforced_by_mac == enforced_by_mac,
        ).first()
        if duplicate:
            return False
        db.add(DBTtbEnforcement(
            event_id=event_id,
            enforced_by=enforced_by,
            enforced_by_mac=enforced_by_mac,
            t_enforced_ms=float(t_enforced_ms),
            relay_acked_ms=float(relay_acked_ms),
            agent_delay_ms=agent_delay_ms,
        ))
        db.commit()
        return True
    finally:
        db.close()


# ─── SOP summary ───────────────────────────────────────────────────────────

SOP_SCENARIOS = ('normal', 'poisoning', 'flooding')


def _canonical_scenario(label: Optional[str]) -> Optional[str]:
    """
    Map a stored scenario label onto one of the paper's three.

    Agents report the canonical names. A TELEMETRY_SCENARIO override is free
    text ("baseline", "arp_flood_1000pps", ...), so match on what it contains.
    """
    text_label = (label or '').lower()
    if 'flood' in text_label:
        return 'flooding'
    if 'poison' in text_label or 'spoof' in text_label or 'mitm' in text_label:
        return 'poisoning'
    if 'normal' in text_label or 'baseline' in text_label or 'benign' in text_label:
        return 'normal'
    return None


def _mean_and_variance(values: List[float]) -> Dict[str, Optional[float]]:
    """Arithmetic mean and sample variance (n-1), per Chapter 3's Equations 9-10."""
    if not values:
        return {'mean': None, 'variance': None}
    return {
        'mean': statistics.fmean(values),
        'variance': statistics.variance(values) if len(values) > 1 else None,
    }


def get_sop_summary() -> Dict[str, Any]:
    """
    The SentiNet half of each Statement-of-the-Problem answer, from recorded data.

    SOP 1: mean CPU (%) and RAM (MB) per traffic scenario, over the snapshots
    taken of one agent's telemetry since it connected (see _current_sop_agent).

    SOP 2: the live confusion matrix, when an attacker was declared for the run
    (the agent's per-packet verdicts against that ground truth); the confusion
    matrix that agent computed on the held-out test set; and the prevention rate (Chapter 3, Equation 4) over the attack
    packets it has detected and blocked since it became the reporting agent.

    SOP 3: Time-to-Block per (detection, enforcing node) pair, with the latest
    trial's two timestamps and the mean and sample variance across all of them.
    """
    db = SessionLocal()
    try:
        detections = db.query(DBTtbDetection).order_by(DBTtbDetection.created_ts.asc()).all()
        enforcements = db.query(DBTtbEnforcement).order_by(DBTtbEnforcement.id.asc()).all()
    finally:
        db.close()

    sop_agent = _current_sop_agent()

    # ── SOP 2 ──
    # Counted in packets, by the agent: every packet it attributed to an
    # attacker, and how many of those the kernel actually dropped. None until
    # the reporting agent has sent its counts (an older agent build never does).
    total_detected = blocked_attacks = None
    if sop_agent and sop_agent['packets'] and sop_agent['packets_base']:
        total_detected = int(sop_agent['packets'][0] - sop_agent['packets_base'][0])
        blocked_attacks = int(sop_agent['packets'][1] - sop_agent['packets_base'][1])
        # A blocked packet is by definition a detected one. Current agents send
        # the two as a consistent pair; this guards against one that does not.
        blocked_attacks = min(blocked_attacks, total_detected)

    # The live confusion matrix: each packet the reporting agent saw, by what it
    # decided about it against what the declared attacker list says it was.
    live = None
    if SOP_ATTACKER_MACS and sop_agent and sop_agent['confusion'] and sop_agent['confusion_base']:
        tp, fp, tn, fn = (c - b for c, b in zip(sop_agent['confusion'], sop_agent['confusion_base']))
        n = tp + fp + tn + fn
        live = {
            'truePositives': tp,
            'falsePositives': fp,
            'trueNegatives': tn,
            'falseNegatives': fn,
            'n': n,
            # Chapter 3, Equations 1-3.
            'accuracy': (tp + tn) / n * 100 if n else None,
            'detectionRate': tp / (tp + fn) * 100 if (tp + fn) else None,
            'falsePositiveRate': fp / (fp + tn) * 100 if (fp + tn) else None,
        }

    # ── SOP 1 ──
    grouped: Dict[str, Dict[str, List[float]]] = (
        sop_agent['snapshots'] if sop_agent else {s: {'cpu': [], 'ram': []} for s in SOP_SCENARIOS}
    )

    efficiency = {}
    for scenario in SOP_SCENARIOS:
        cpu = _mean_and_variance(grouped[scenario]['cpu'])
        ram = _mean_and_variance(grouped[scenario]['ram'])
        efficiency[scenario] = {
            'n': len(grouped[scenario]['cpu']),
            'meanCpu': cpu['mean'],
            'varianceCpu': cpu['variance'],
            'meanRamMb': ram['mean'],
            'varianceRamMb': ram['variance'],
            'live': bool(sop_agent) and sop_agent['scenario'] == scenario,
        }

    # ── SOP 3 ──
    by_event = {d.event_id: d for d in detections}
    trials = []
    for e in enforcements:
        d = by_event.get(e.event_id)
        if d is None:
            continue
        # t_detected and t_enforced are stamped by two different machines, and
        # their clocks are never exactly in sync — a few hundred milliseconds of
        # drift is enough to make the raw difference negative. So both are
        # placed on the relay's clock first: the moment the relay heard from
        # each agent, minus how long that agent had held the event (a duration
        # on its own clock, which drift does not affect). What remains
        # unaccounted for is B's network trip back to the relay, a millisecond
        # or so on a LAN, which makes the figure very slightly high.
        t_detected = d.relay_received_ms - (d.agent_delay_ms or 0.0)
        t_enforced = e.relay_acked_ms - (e.agent_delay_ms or 0.0)
        trials.append({
            'attackerMac': d.attacker_mac,
            'detectedBy': d.detected_by,
            'enforcedBy': e.enforced_by,
            'tDetectedMs': t_detected,
            'tEnforcedMs': t_enforced,
            'ttbMs': t_enforced - t_detected,
            # The raw difference of the two agents' own clocks, for reference:
            # how far it sits from ttbMs is how far apart those clocks are.
            'agentClockTtbMs': e.t_enforced_ms - d.t_detected_ms,
        })

    latest = trials[-1] if trials else None
    if latest is None and detections:
        # Detected, but no other node has enforced it yet (or none is connected).
        d = detections[-1]
        latest = {
            'attackerMac': d.attacker_mac,
            'detectedBy': d.detected_by,
            'enforcedBy': None,
            'tDetectedMs': d.relay_received_ms - (d.agent_delay_ms or 0.0),
            'tEnforcedMs': None,
            'ttbMs': None,
            'agentClockTtbMs': None,
        }

    ttb_stats = _mean_and_variance([t['ttbMs'] for t in trials])

    return {
        'efficiency': {
            'agent': sop_agent['name'] if sop_agent else None,
            'scenarios': efficiency,
            'sampleIntervalSeconds': TELEMETRY_SAMPLE_INTERVAL,
        },
        'detection': {
            'evaluation': sop_agent['evaluation'] if sop_agent else None,
            # The attacker MAC(s) declared for this run (empty: no live matrix),
            # the live matrix scored against them, and how long the reporting
            # agent's most recent detection took.
            'attackerMacs': SOP_ATTACKER_MACS,
            'live': live,
            'latency': sop_agent['latency'] if sop_agent else None,
            'blockedAttacks': blocked_attacks,
            'totalDetectedAttacks': total_detected,
            'preventionRate': (blocked_attacks / total_detected * 100) if total_detected else None,
            # "kernel": blocked packets are really dropped. "simulated": the
            # agent's platform cannot drop, so blocked stays at zero.
            'enforcement': sop_agent['enforcement'] if sop_agent else None,
        },
        'timeToBlock': {
            'latest': latest,
            'n': len(trials),
            'meanTtbMs': ttb_stats['mean'],
            'varianceTtbMs': ttb_stats['variance'],
        },
    }


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

def _token_key(session_token: str) -> str:
    """
    What is stored for a session: a hash of its token, not the token itself, so
    a copy of the database does not hand out working session cookies.
    """
    return hashlib.sha256(session_token.encode("utf-8")).hexdigest()


def create_session(digital_id: str) -> str:
    """Start a session and return its token (for the cookie). 256 random bits."""
    session_token = secrets.token_urlsafe(32)
    now = time.time()
    db = SessionLocal()
    try:
        db.add(DBSession(token=_token_key(session_token), digital_id=digital_id,
                         created_at=now, last_accessed=now))
        db.commit()
    finally:
        db.close()
    return session_token


def validate_session(session_token: str) -> Optional[str]:
    """The digital ID a live session belongs to, or None. Refreshes its idle timer."""
    if not session_token:
        return None
    db = SessionLocal()
    try:
        db_session = db.query(DBSession).filter(DBSession.token == _token_key(session_token)).first()
        if not db_session:
            return None
        now = time.time()
        idle = now - (db_session.last_accessed or db_session.created_at)
        age = now - db_session.created_at
        if idle > SESSION_TIMEOUT_SECONDS or age > SESSION_MAX_AGE_SECONDS:
            db.delete(db_session)
            db.commit()
            return None
        db_session.last_accessed = now
        db.commit()
        return db_session.digital_id
    finally:
        db.close()


def destroy_session(session_token: str) -> None:
    if not session_token:
        return
    db = SessionLocal()
    try:
        db.query(DBSession).filter(DBSession.token == _token_key(session_token)).delete()
        db.commit()
    finally:
        db.close()


def get_agents() -> List[Dict[str, Any]]:
    """
    All agents, pruning any whose last heartbeat (register_agent or
    telemetry_report) has gone stale.

    remove_agent() — called from the Socket.IO `disconnect` handler — is not
    enough on its own: that event can only fire for a connection *this* relay
    process is itself holding. A hard-killed agent (stop_all.bat's
    taskkill /F skips any graceful sio.disconnect()) or, especially, a relay
    restart (in-memory connection state always resets, but the persisted
    agents table never did) can both leave a row with no live socket left
    anywhere to ever disconnect — a ghost with no automatic expiry. Pruning by
    last_seen here means staleness self-heals on the very next poll instead of
    depending on an event that may never come.
    """
    db = SessionLocal()
    cutoff = time.time() - AGENT_STALE_SECONDS
    stale = db.query(DBAgent).filter(
        or_(DBAgent.last_seen.is_(None), DBAgent.last_seen < cutoff)
    ).all()
    if stale:
        for a in stale:
            db.delete(a)
        db.commit()

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
            'ramProcessPercent': a.ram_process_percent,
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
            'action': t.action,
            'detail': t.detail,
            'confidence': t.confidence,
            'createdTs': t.created_ts,
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


def add_threat(source_mac: str, attack_type: str, tier: str, action: str, confidence: str = "99.9%",
                detail: Optional[str] = None, client_event_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Insert one threat record. Idempotent when `client_event_id` is given: a
    second call with the same id (an agent-side retry, or a register_agent
    backfill of an already-delivered report) returns the existing row instead
    of inserting a duplicate. Callers can check the returned `isNew` flag to
    decide whether to also touch the blacklist / broadcast.
    """
    db = SessionLocal()

    if client_event_id:
        existing = db.query(DBThreat).filter(DBThreat.client_event_id == client_event_id).first()
        if existing:
            threat_dict = {
                'id': existing.id,
                'timestamp': existing.timestamp,
                'sourceMac': existing.source_mac,
                'attackType': existing.attack_type,
                'tier': existing.tier,
                'action': existing.action,
                'confidence': confidence,
                'detail': existing.detail,
                'isNew': False,
            }
            db.close()
            return threat_dict

    now = datetime.now().strftime('%H:%M:%S')
    db_threat = DBThreat(
        timestamp=now,
        source_mac=source_mac,
        attack_type=attack_type,
        tier=tier,
        action=action,
        detail=detail,
        confidence=confidence,
        client_event_id=client_event_id,
        created_ts=time.time(),
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
        'confidence': confidence,
        'detail': db_threat.detail,
        'isNew': True,
    }
    db.close()

    # Try publishing to MultiChain
    write_to_multichain(threat_dict)

    return threat_dict
