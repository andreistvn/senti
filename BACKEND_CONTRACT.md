# SentiNet Backend Contract

This repository currently has two dashboard runtimes, one tray daemon, and one admin backend:

- `agent-dashboard/` reads live state from the local tray daemon when it is available.
- `admin-dashboard/` reads from the admin backend server at `http://127.0.0.1:8771`.
- `tray-app/` exposes a local HTTP API at `http://127.0.0.1:8770` for agent-side data.
- `admin-backend/` implements all admin dashboard endpoints and session management.
Agent Dashboard (Tray) API

Base URL:

- `http://127.0.0.1:8770`

This API is exposed by the tray daemon and serves the agent dashboard with real protection state, event logs, and service health.
- `http://127.0.0.1:8770`

Endpoints:

- `GET /api/status`
- `POST /api/toggle`
- `GET /api/stats`
- `GET /api/events`
- `GET /api/health`

Response shapes:

- `GET /api/status`
  - `protected: boolean`
  - `relay: 'online' | 'offline'`
  - `version: string`
  - `since: string | null`

- `GET /api/toggle`
  - same shape as `/api/status`

- `GET /api/stats`
  - `inspected: number`
  - `dropped: number`
  - `passed: number`
  - `blocked: number`
  - `cpu: number`
  - `memory: number`
  - `bayanihan: { contributions: number; usersProtected: number }`
  - `lastThreat: { attackType: string; sourceMac: string; timestamp: string } | null`
  - `protected: boolean`

- `GET /api/events`
  - `{ events: Array<{ id: number; timestamp: string; sourceMac: string; attackType: string; tier: string; action: string }> }`

- `GET /api/health`
  - `{ services: Array<{ id: string; name: string; status: 'active' | 'loaded' | 'connected' | 'degraded' | 'offline'; detail: string; uptime: string }> }`

Current client:

- [agent-dashboard/src/app/lib/trayClient.ts](agent-dashboard/src/app/lib/trayClient.ts)
- [tray-app/api_server.py](tray-app/api_server.py)
- [traydmin Dashboard API

Base URL:

- `http://127.0.0.1:8771`

This API is implemented by the admin backend and serves the admin dashboard with agent lists, threat logs, policy configuration, and system telemetry.

Current implementation:

- [admin-backend/main.py](admin-backend/main.py) — FastAPI server with all endpoints
- [admin-backend/state.py](admin-backend/state.py) — In-memory session and data store
- [admin-backend/config.py](admin-backend/config.py) — Configuration and defaults

## 3. Agent Dashboard Integration

The agent dashboard already has a clean integration seam:

- It polls the tray API every few seconds.
- It falls back to mock data when the tray is not running.
- It treats the tray daemon as the source of truth for protection state, stats, events, and daemon health.

## 4. Admin Dashboard Integration

The admin dashboard now reads from the real admin backend:

- It requests all dashboard data (agents, threats, ledger, policy, telemetry) on mount.
- It falls back to client-side seed data if the backend is unreachable.
- Session cookies manage authentication

The admin dashboard still needs a real backend. Right now its auth, telemetry, policy, and incident data are all generated in the browser.

Suggested backend resources:

- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `GET /agents`
- `GET /agents/:id`
- `POST /agents/:id/restart`
- `GET /policy`
- `PUT /policy`
- `GET /threats`
- `GET /analytics/threat-volume`
- `GET /ledger`
- `GET /telemetry/summary`
5. Running Both Backends

### Tray Daemon (Agent Dashboard Backend)

```bash
cd tray-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

Runs on `http://127.0.0.1:8770`.

### Admin Backend

```bash
cd admin-backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

Runs on `http://127.0.0.1:8771`.

### Admin Dashboard (Dev Mode)

```bash
cd admin-dashboard
npm install
VITE_ADMIN_API_BASE_URL=http://127.0.0.1:8771 npm run dev
```

### Agent Dashboard (Dev Mode)

```bash
cd agent-dashboard
npm install
npm run dev
```

## 6. Next Steps

- Add database persistence (replace in-memory state in `admin-backend/state.py`)
- Implement real authentication (replace hardcoded credentials)
- Add agent sync API so agents can push telemetry and threat logs
- Add real threat detection and ML scoring
- Implement blockchain ledger recording
- Ledger rows
  - `blockId`, `timestamp`, `macHash`, `score`

- Policy
  - `mlThreshold`, `arpFloodLimit`, `autoBlacklist`, `syncInterval`, `logRetentionDays`

- Telemetry summary
  - `cpu`, `ram`, `latency`, `blockHeight`, `lastSyncTime`, `chainStatus`, `totalIncidents`

## 4. Refactor Target

The clean next step is to keep the current UI composition and move all data-fetching and simulation behind adapters:

- view components stay responsible for layout and styling
- hooks/services own polling, timers, and API calls
- mock generation only exists in one place per dashboard

That preserves the design while making a real backend swap much easier.