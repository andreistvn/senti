"""
SentiNet Admin Backend API Server.

Implements the contract endpoints for the admin dashboard:
- POST /auth/login — authenticate with digital ID
- POST /auth/logout — end session
- GET /auth/me — get current session
- GET /agents — list all agents
- GET /agents/:id — get single agent
- GET /threats — list threat log entries
- GET /ledger — list blockchain ledger entries
- GET /blacklist — network-wide blacklist shared with all agents
- GET /ledger/status — MultiChain node health and publish counters
- GET /policy — get current policy config
- PUT /policy — update policy config
- GET /telemetry/summary — get telemetry + blockchain metrics
- GET /telemetry/readings — recorded CPU/RAM samples for analysis
- GET /analytics/threat-volume — get threat volume history
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import config
import state
import socketio


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Bring the MultiChain ledger worker up with the server and down with it."""
    state.start_ledger_worker()
    state.start_telemetry_sampler()
    yield
    state.stop_telemetry_sampler()
    state.stop_ledger_worker()


app = FastAPI(title='SentiNet Admin Backend', version='1.0.0', lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ADMIN_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Socket.io Server
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio, app)


# ─── Request/Response Models ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    digitalId: str


class PolicyConfigRequest(BaseModel):
    mlThreshold: Optional[float] = None
    arpFloodLimit: Optional[int] = None
    autoBlacklist: Optional[bool] = None
    syncInterval: Optional[int] = None
    logRetentionDays: Optional[int] = None


class SessionResponse(BaseModel):
    authenticated: bool
    digitalId: Optional[str] = None


class AgentResponse(BaseModel):
    id: str
    name: str
    ip: str
    mac: str
    state: str
    syncProgress: int
    cpu: float
    ram: float                 # percent of system RAM — display gauge
    ramMb: Optional[float] = None   # RSS in MB — the figure Chapter 3 specifies
    connectedSince: str
    packetsProcessed: int


class ThreatLogResponse(BaseModel):
    id: int
    timestamp: str
    message: str


class LedgerResponse(BaseModel):
    blockId: str
    timestamp: str
    macHash: str
    score: str


class PolicyResponse(BaseModel):
    mlThreshold: float
    arpFloodLimit: int
    autoBlacklist: bool
    syncInterval: int
    logRetentionDays: int


class TelemetrySummaryResponse(BaseModel):
    # Real socket.io client count, so the dashboard header can stop claiming
    # "WebSocket: Listening" from a hardcoded string.
    connectedAgents: int = 0
    # Floats, not ints: truncating a CPU percentage loses real precision, and the
    # paper's variance calculation is computed over these readings.
    cpu: float          # host CPU percent on the relay machine
    ram: float          # host RAM percent
    ramMb: float = 0.0  # host RAM in use, MB
    ramTotalMb: float = 0.0
    latency: int
    blockHeight: int
    lastSyncTime: str
    chainStatus: str
    totalIncidents: int


class ThreatPointResponse(BaseModel):
    time: str
    pps: int
    blocked: int


# ─── Auth Endpoints ────────────────────────────────────────────────────────

@app.post('/auth/login', response_model=SessionResponse)
async def login(req: LoginRequest):
    """Authenticate with digital ID and password (MFA done client-side)."""
    digital_id = req.digitalId
    
    # Validate digital ID format
    if digital_id not in state.ADMIN_CREDENTIALS:
        raise HTTPException(status_code=401, detail='Invalid credentials')
    
    # Create session
    session_token = state.create_session(digital_id)
    
    # Return response with session cookie
    response = JSONResponse(
        content={'authenticated': True, 'digitalId': digital_id},
        status_code=200,
    )
    response.set_cookie(
        key='sentinet_admin_session',
        value=session_token,
        httponly=True,
        secure=False,  # set to True in production
        samesite='lax',
    )
    return response


@app.post('/auth/logout')
async def logout(sentinet_admin_session: Optional[str] = Cookie(None)):
    """End the current session."""
    if sentinet_admin_session:
        state.destroy_session(sentinet_admin_session)
    
    response = JSONResponse(status_code=204)
    response.delete_cookie('sentinet_admin_session')
    return response


@app.get('/auth/me', response_model=SessionResponse)
async def get_session(sentinet_admin_session: Optional[str] = Cookie(None)):
    """Get current session info."""
    if not sentinet_admin_session:
        return SessionResponse(authenticated=False, digitalId=None)
    
    digital_id = state.validate_session(sentinet_admin_session)
    if not digital_id:
        return SessionResponse(authenticated=False, digitalId=None)
    
    return SessionResponse(authenticated=True, digitalId=digital_id)


# ─── Agent Endpoints ────────────────────────────────────────────────────────

@app.get('/agents', response_model=List[AgentResponse])
async def list_agents(sentinet_admin_session: Optional[str] = Cookie(None)):
    """Get list of all agents."""
    if not sentinet_admin_session:
        raise HTTPException(status_code=401, detail='Not authenticated')
    
    digital_id = state.validate_session(sentinet_admin_session)
    if not digital_id:
        raise HTTPException(status_code=401, detail='Session expired')
    
    return state.get_agents()


@app.get('/agents/{agent_id}', response_model=AgentResponse)
async def get_agent(agent_id: str, sentinet_admin_session: Optional[str] = Cookie(None)):
    """Get single agent by ID."""
    if not sentinet_admin_session:
        raise HTTPException(status_code=401, detail='Not authenticated')
    
    digital_id = state.validate_session(sentinet_admin_session)
    if not digital_id:
        raise HTTPException(status_code=401, detail='Session expired')
    
    for agent in state.get_agents():
        if agent['id'] == agent_id:
            return agent
    
    raise HTTPException(status_code=404, detail='Agent not found')


# ─── Threat/Incident Endpoints ────────────────────────────────────────────

@app.get('/threats', response_model=List[ThreatLogResponse])
async def list_threats(sentinet_admin_session: Optional[str] = Cookie(None)):
    """Get list of threat log entries."""
    if not sentinet_admin_session:
        raise HTTPException(status_code=401, detail='Not authenticated')
    
    digital_id = state.validate_session(sentinet_admin_session)
    if not digital_id:
        raise HTTPException(status_code=401, detail='Session expired')
    
    threats = state.get_threats()
    return [
        ThreatLogResponse(
            id=t['id'],
            timestamp=t['timestamp'],
            message=(
                f"[{t['tier']}] {t['attackType']} from {t['sourceMac']}. Action: {t['action']}"
                + (f" - {t['detail']}" if t.get('detail') else "")
            )
        )
        for t in threats
    ]


# ─── Ledger Endpoints ────────────────────────────────────────────────────────

@app.get('/ledger', response_model=List[LedgerResponse])
async def list_ledger(sentinet_admin_session: Optional[str] = Cookie(None)):
    """Get list of blockchain ledger entries."""
    if not sentinet_admin_session:
        raise HTTPException(status_code=401, detail='Not authenticated')
    
    digital_id = state.validate_session(sentinet_admin_session)
    if not digital_id:
        raise HTTPException(status_code=401, detail='Session expired')
    
    return state.get_ledger()


@app.get('/ledger/status')
async def ledger_status(sentinet_admin_session: Optional[str] = Cookie(None)):
    """
    MultiChain node health: reachability, stream readiness, block height, RPC
    latency, publish counters and the last error. Useful for diagnosing why the
    dashboard is showing DEGRADED without tailing the server log.
    """
    if not sentinet_admin_session:
        raise HTTPException(status_code=401, detail='Not authenticated')

    digital_id = state.validate_session(sentinet_admin_session)
    if not digital_id:
        raise HTTPException(status_code=401, detail='Session expired')

    return state.get_chain_status()


@app.get('/telemetry/readings')
async def telemetry_readings(
    scenario: Optional[str] = None,
    sentinet_admin_session: Optional[str] = Cookie(None),
):
    """
    Every recorded resource-consumption sample.

    This is the dataset Chapter 3's statistical treatment consumes — CPU usage (%)
    and RAM consumption (MB) per node, at the configured interval, labelled by
    scenario. Filter with ?scenario=arp_flood_1000pps to isolate one run.
    """
    if not sentinet_admin_session:
        raise HTTPException(status_code=401, detail='Not authenticated')

    digital_id = state.validate_session(sentinet_admin_session)
    if not digital_id:
        raise HTTPException(status_code=401, detail='Session expired')

    rows = state.get_readings(scenario)
    return {'count': len(rows), 'scenario': scenario, 'readings': rows}


@app.get('/blacklist')
async def list_blacklist(sentinet_admin_session: Optional[str] = Cookie(None)):
    """
    The network-wide blacklist the relay holds and replays to agents on connect.

    This is the shared intelligence of the Bayanihan layer: every MAC any agent
    has reported, with which agent reported it first.
    """
    if not sentinet_admin_session:
        raise HTTPException(status_code=401, detail='Not authenticated')

    digital_id = state.validate_session(sentinet_admin_session)
    if not digital_id:
        raise HTTPException(status_code=401, detail='Session expired')

    entries = state.get_blacklist()
    return {'count': len(entries), 'entries': entries}


# ─── Policy Endpoints ────────────────────────────────────────────────────────

@app.get('/policy', response_model=PolicyResponse)
async def get_policy(sentinet_admin_session: Optional[str] = Cookie(None)):
    """Get current policy config."""
    if not sentinet_admin_session:
        raise HTTPException(status_code=401, detail='Not authenticated')
    
    digital_id = state.validate_session(sentinet_admin_session)
    if not digital_id:
        raise HTTPException(status_code=401, detail='Session expired')
    
    return state.get_policy()


@app.put('/policy', response_model=PolicyResponse)
async def update_policy(
    req: PolicyConfigRequest,
    sentinet_admin_session: Optional[str] = Cookie(None)
):
    """Update policy config."""
    if not sentinet_admin_session:
        raise HTTPException(status_code=401, detail='Not authenticated')
    
    digital_id = state.validate_session(sentinet_admin_session)
    if not digital_id:
        raise HTTPException(status_code=401, detail='Session expired')
    
    # Build update dict (only include non-None fields)
    updates = {k: v for k, v in req.dict().items() if v is not None}
    return state.set_policy(updates)


# ─── Telemetry Endpoints ────────────────────────────────────────────────────

@app.get('/telemetry/summary', response_model=TelemetrySummaryResponse)
async def get_telemetry_summary(sentinet_admin_session: Optional[str] = Cookie(None)):
    """Get current telemetry and blockchain metrics."""
    if not sentinet_admin_session:
        raise HTTPException(status_code=401, detail='Not authenticated')
    
    digital_id = state.validate_session(sentinet_admin_session)
    if not digital_id:
        raise HTTPException(status_code=401, detail='Session expired')
    
    summary = state.get_telemetry_summary()
    # sid_to_mac lives here rather than in state.py, so it is merged in at the
    # edge instead of being threaded through the data layer.
    summary['connectedAgents'] = len(mac_to_sid)
    return summary


# ─── Analytics Endpoints ────────────────────────────────────────────────────

@app.get('/analytics/threat-volume', response_model=List[ThreatPointResponse])
async def get_threat_volume(sentinet_admin_session: Optional[str] = Cookie(None)):
    """Get threat volume history for analytics."""
    if not sentinet_admin_session:
        raise HTTPException(status_code=401, detail='Not authenticated')
    
    digital_id = state.validate_session(sentinet_admin_session)
    if not digital_id:
        raise HTTPException(status_code=401, detail='Session expired')
    
    return state.get_threat_history()


# ─── Health Check ────────────────────────────────────────────────────────────

@app.get('/health')
async def health():
    """Health check endpoint."""
    return {'status': 'ok'}


# ─── Socket.io Events ────────────────────────────────────────────────────────

sid_to_mac = {}
# Which socket currently owns each MAC. An agent that loses its connection
# reconnects with a *new* sid and re-registers; the old socket's disconnect can
# arrive after that, and removing purely by MAC would then delete the agent that
# had just come back — leaving it invisible on the dashboard while it believes
# it is connected.
mac_to_sid = {}

def _peer_address(environ) -> str:
    """
    Best-effort remote address for a socket.io client.

    Logged so the relay's own console answers the question "did that machine
    reach me at all?" — which separates a network problem from an application
    one without having to go and read logs on the agent.
    """
    try:
        client = environ.get('asgi.scope', {}).get('client')
        if client:
            return f"{client[0]}:{client[1]}"
    except Exception:
        pass
    return environ.get('REMOTE_ADDR') or 'unknown'


@sio.event
async def connect(sid, environ):
    print(f"[WebSocket] Client connected: {sid} from {_peer_address(environ)}")

@sio.event
async def disconnect(sid):
    print(f"[WebSocket] Client disconnected: {sid}")
    mac = sid_to_mac.pop(sid, None)
    if not mac:
        return

    if mac_to_sid.get(mac) != sid:
        # A newer socket already owns this MAC — this is a stale disconnect for
        # a connection that has since been replaced. Leave the agent in place.
        print(f"[WebSocket] Stale disconnect for {mac}; a newer session is active.")
        return

    mac_to_sid.pop(mac, None)
    state.remove_agent(mac)

async def _ingest_attack_report(data: Dict[str, Any], reporter_sid: Optional[str], reporter_name: str) -> Dict[str, Any]:
    """
    Record one attack report and fan it out to the rest of the mesh.

    Shared by the live `attack_report` handler and `register_agent`'s backfill
    of an agent's recent events on (re)connect, so a report an agent could only
    deliver late still gets the exact same treatment — threat log, ledger
    mirror (via state.add_threat), blacklist entry, and a broadcast to every
    other connected agent — as one delivered on time.

    Returns an ack dict. python-socketio sends an async handler's return value
    back as the ack to the client's `sio.call(...)`, which is what lets the
    agent-side queue in bayanihan_client.py know a report actually landed here
    (not just that the socket write didn't throw).
    """
    source_mac = data.get("sourceMac")
    if not source_mac:
        return {"status": "error", "detail": "missing sourceMac"}

    attack_type = data.get("attackType", "Anomalous ARP")
    tier = data.get("tier", "Tier 2")
    action = data.get("action", "Blocked")
    confidence = data.get("confidence", "99.9%")
    detail = data.get("detail")
    client_event_id = data.get("clientEventId")

    try:
        threat_dict = state.add_threat(
            source_mac, attack_type, tier, action, confidence,
            detail=detail, client_event_id=client_event_id,
        )
    except Exception as exc:
        print(f"[WebSocket] Failed to record attack report from {reporter_name}: {exc}")
        return {"status": "error", "detail": str(exc)}

    if not threat_dict.get('isNew', True):
        # Already have this exact report (agent retry, or a backfill re-offering
        # something that was in fact delivered live). Nothing further to do —
        # the blacklist entry and broadcast already happened the first time.
        return {"status": "ok", "id": threat_dict["id"], "duplicate": True}

    # Record it on the network-wide blacklist so late-joining agents can be
    # caught up later. Returns False if another agent already reported it.
    is_new_blacklist = state.add_to_blacklist(
        source_mac,
        reported_by=reporter_name,
        attack_type=attack_type,
        confidence=confidence,
        tier=tier,
    )

    # Broadcast to all other connected agents so they update their blacklists.
    # skip_sid is None for a backfilled event (there is no "sid that just sent
    # this" — it arrived bundled in register_agent), which broadcasts to
    # everyone including the reconnecting agent; harmless, it already has it.
    print(f"[WebSocket] Broadcasting blacklist_update for {source_mac}"
          f"{'' if is_new_blacklist else ' (already known)'}")
    await sio.emit(
        "blacklist_update",
        {
            "mac": source_mac,
            "attackType": attack_type,
            "confidence": confidence,
            "tier": tier,
            "reportedBy": reporter_name,
        },
        skip_sid=reporter_sid,
    )

    return {"status": "ok", "id": threat_dict["id"], "duplicate": False}


@sio.event
async def register_agent(sid, data):
    print(f"[WebSocket] Agent registered: {data.get('name')} from {sid}")
    mac = data.get("mac")
    if mac:
        sid_to_mac[sid] = mac
        mac_to_sid[mac] = sid
    state.upsert_agent(data)

    # Replay the network-wide blacklist to this agent. Without this an agent that
    # joins (or reconnects) after a threat was reported starts with an empty
    # Tier-1 filter and never catches up — it would only ever learn about threats
    # detected while it happened to be connected.
    entries = state.get_blacklist()
    if entries:
        await sio.emit("blacklist_sync", {"entries": entries}, to=sid)
        print(f"[WebSocket] Sent {len(entries)} blacklist entries to {data.get('name')}")

    # Catch up on anything this agent detected but couldn't deliver earlier —
    # e.g. the relay was down or restarting at the moment of detection. The
    # agent's own BayanihanClient queue (tray-app/bayanihan_client.py) already
    # retries every report until acknowledged, so in the common case this is a
    # no-op; it's the second, independent path for the cases that queue itself
    # might have missed (bug, or a report logged before this fix existed).
    reporter = data.get("name") or mac or "unknown"
    recent_events = data.get("recentEvents") or []
    backfilled = 0
    for event in recent_events:
        result = await _ingest_attack_report(event, reporter_sid=None, reporter_name=reporter)
        if result.get("status") == "ok" and not result.get("duplicate"):
            backfilled += 1
    if backfilled:
        print(f"[WebSocket] Backfilled {backfilled} missed threat report(s) from {data.get('name')}")

@sio.event
async def telemetry_report(sid, data):
    mac = data.get("mac")
    cpu = data.get("cpu", 0)
    ram = data.get("ram", 0)                 # system-wide percent, for the gauge
    ram_mb = data.get("ramMb")               # this agent's RSS in MB — the paper's figure
    protected = data.get("protected")
    agent_state = data.get("state")
    if mac:
        state.update_agent_telemetry(
            mac, cpu, ram, agent_state, ram_mb=ram_mb, protected=protected
        )

@sio.event
async def attack_report(sid, data):
    """
    Handle incoming Attack Report from a SentiNet agent.
    Expected data: {"sourceMac": "...", "attackType": "...", "tier": "...", "action": "...",
                     "confidence": "...", "clientEventId": "..."}

    Returns an ack dict — the agent's BayanihanClient uses `sio.call(...)` and
    only considers the report delivered once this comes back with status "ok".
    """
    print(f"[WebSocket] Received attack report from {sid}: {data}")
    reporter = data.get("name") or sid_to_mac.get(sid) or "unknown"
    return await _ingest_attack_report(data, reporter_sid=sid, reporter_name=reporter)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        socket_app,
        host=config.ADMIN_API_HOST,
        port=config.ADMIN_API_PORT,
        log_level='info' if config.ADMIN_API_DEBUG else 'warning',
    )
