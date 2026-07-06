# SentiNet Admin Backend

FastAPI-based backend server for the admin dashboard. Implements the contract endpoints for authentication, agent management, threat analytics, policy configuration, and blockchain ledger access.

## Setup

```bash
cd admin-backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

The server will start on `http://127.0.0.1:8771` by default.

## Environment Variables

Create a `.env` file (copy from `.env.example`):

- `ADMIN_API_HOST` — Bind address (default: `127.0.0.1`)
- `ADMIN_API_PORT` — Port number (default: `8771`)
- `ADMIN_API_DEBUG` — Debug mode (default: `true`)

## Endpoints

All endpoints except health check require valid session authentication.

### Auth
- `POST /auth/login` — Create session
- `POST /auth/logout` — Destroy session
- `GET /auth/me` — Get current session

### Agents
- `GET /agents` — List all agents
- `GET /agents/{id}` — Get single agent

### Threats
- `GET /threats` — List threat log entries

### Ledger
- `GET /ledger` — List blockchain ledger entries

### Policy
- `GET /policy` — Get current policy config
- `PUT /policy` — Update policy config

### Telemetry
- `GET /telemetry/summary` — Get system metrics and blockchain status

### Analytics
- `GET /analytics/threat-volume` — Get threat volume history

### Health
- `GET /health` — Health check

## Configuration

Credentials and default data are hardcoded in `state.py`. In production, back this with a real database.

Session timeouts default to 1 hour. Adjust `SESSION_TIMEOUT_SECONDS` in `config.py`.
