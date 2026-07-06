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
- GET /policy — get current policy config
- PUT /policy — update policy config
- GET /telemetry/summary — get telemetry + blockchain metrics
- GET /analytics/threat-volume — get threat volume history
"""

from fastapi import FastAPI, HTTPException, Cookie
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import config
import state

app = FastAPI(title='SentiNet Admin Backend', version='1.0.0')


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


class ThreatResponse(BaseModel):
    id: int
    timestamp: str
    sourceMac: str
    attackType: str
    tier: str
    action: str


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

@app.get('/threats', response_model=List[ThreatResponse])
async def list_threats(sentinet_admin_session: Optional[str] = Cookie(None)):
    """Get list of threat log entries."""
    if not sentinet_admin_session:
        raise HTTPException(status_code=401, detail='Not authenticated')
    
    digital_id = state.validate_session(sentinet_admin_session)
    if not digital_id:
        raise HTTPException(status_code=401, detail='Session expired')
    
    return state.get_threats()


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


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        app,
        host=config.ADMIN_API_HOST,
        port=config.ADMIN_API_PORT,
        log_level='info' if config.ADMIN_API_DEBUG else 'warning',
    )
