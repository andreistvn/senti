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
- GET /ledger/status — MultiChain node health and publish counters
- GET /policy — get current policy config
- PUT /policy — update policy config
- GET /telemetry/summary — get telemetry + blockchain metrics
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
    yield
    state.stop_ledger_worker()


app = FastAPI(title='SentiNet Admin Backend', version='1.0.0', lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175", "http://127.0.0.1:5175", "http://localhost:5173", "http://127.0.0.1:5173"],
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
    cpu: int
    ram: int
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
    cpu: int
    ram: int
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
            message=f"[{t['tier']}] {t['attackType']} from {t['sourceMac']}. Action: {t['action']}"
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
    
    return state.get_telemetry_summary()


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

@sio.event
async def connect(sid, environ):
    print(f"[WebSocket] Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"[WebSocket] Client disconnected: {sid}")
    mac = sid_to_mac.pop(sid, None)
    if mac:
        state.remove_agent(mac)

@sio.event
async def register_agent(sid, data):
    print(f"[WebSocket] Agent registered: {data.get('name')} from {sid}")
    mac = data.get("mac")
    if mac:
        sid_to_mac[sid] = mac
    state.upsert_agent(data)

@sio.event
async def telemetry_report(sid, data):
    mac = data.get("mac")
    cpu = data.get("cpu", 0)
    ram = data.get("ram", 0)
    agent_state = data.get("state")
    if mac:
        state.update_agent_telemetry(mac, cpu, ram, agent_state)

@sio.event
async def attack_report(sid, data):
    """
    Handle incoming Attack Report from a SentiNet agent.
    Expected data: {"sourceMac": "...", "attackType": "...", "tier": "...", "action": "...", "confidence": "..."}
    """
    print(f"[WebSocket] Received attack report from {sid}: {data}")
    
    source_mac = data.get("sourceMac")
    attack_type = data.get("attackType", "Anomalous ARP")
    tier = data.get("tier", "Tier 2")
    action = data.get("action", "Blocked")
    confidence = data.get("confidence", "99.9%")
    
    if source_mac:
        # Save to threat log
        state.add_threat(source_mac, attack_type, tier, action, confidence)
        
        # Broadcast to all other connected agents so they update their blacklists
        print(f"[WebSocket] Broadcasting blacklist_update for {source_mac}")
        await sio.emit("blacklist_update", {"mac": source_mac}, skip_sid=sid)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        socket_app,
        host=config.ADMIN_API_HOST,
        port=config.ADMIN_API_PORT,
        log_level='info' if config.ADMIN_API_DEBUG else 'warning',
    )
