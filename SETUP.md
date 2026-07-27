# SentiNet Development Setup

Complete setup and run instructions for the full stack: admin backend, admin dashboard, agent dashboard, and system tray daemon.

## Prerequisites

- **Node.js** 18+ (for dashboards)
- **Python** 3.9+ (for backends)
- **npm** or **pnpm** (for dashboards)

## Quick Start (macOS/Linux)

### Terminal 1: Admin Backend

```bash
cd admin-backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

Runs on `http://127.0.0.1:8771`.

### Terminal 2: Admin Dashboard

```bash
cd admin-dashboard
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

### Terminal 3: Agent Dashboard

```bash
cd agent-dashboard
npm install
npm run dev
```

Open `http://localhost:5174` (or next available port).

### Terminal 4: Tray Daemon (Agent Backend)

```bash
cd tray-app
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python sentinet_tray.py
```

Runs on `http://127.0.0.1:8770` (background process).

## Quick Start (Windows)

### Command Prompt 1: Admin Backend

```batch
cd admin-backend
if exist venv rmdir /s /q venv
python -m venv venv
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

### Command Prompt 2: Admin Dashboard

```batch
cd admin-dashboard
npm install
npm run dev
```

### Command Prompt 3: Agent Dashboard

```batch
cd agent-dashboard
npm install
npm run dev
```

### Command Prompt 4: Tray Daemon

```batch
cd tray-app
if exist venv rmdir /s /q venv
python -m venv venv
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python sentinet_tray.py
```

## After Initial Setup

Once all dependencies are installed, you only need to activate the venvs and run the services:

### macOS/Linux

```bash
# Terminal 1: Admin Backend
cd admin-backend && source venv/bin/activate && python main.py

# Terminal 2: Admin Dashboard
cd admin-dashboard && npm run dev

# Terminal 3: Agent Dashboard
cd agent-dashboard && npm run dev

# Terminal 4: Tray Daemon
cd tray-app && source venv/bin/activate && python sentinet_tray.py
```

### Windows

```batch
REM Command Prompt 1: Admin Backend
cd admin-backend && call venv\Scripts\activate && python main.py

REM Command Prompt 2: Admin Dashboard
cd admin-dashboard && npm run dev

REM Command Prompt 3: Agent Dashboard
cd agent-dashboard && npm run dev

REM Command Prompt 4: Tray Daemon
cd tray-app && call venv\Scripts\activate && python sentinet_tray.py
```

## Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Admin Dashboard | http://localhost:5173 | Web UI for system administration |
| Agent Dashboard | http://localhost:5174 | Web UI for agent protection status |
| Admin Backend | http://127.0.0.1:8771 | API for admin dashboard (localhost only) |
| Tray Daemon | http://127.0.0.1:8770 | API for agent dashboard (localhost only) |

## Credentials

**Admin Dashboard Login:**

- Digital ID: `ADM-7734-ALPHA`
- Password: `SentiNet@2049`
- MFA: `482910` (OTP), or use Fingerprint/Face ID (demo mode)

**Agent Dashboard:**

- Digital ID: `AGT-0001-ALPHA`
- Password: `ARP@Guardian`

## Troubleshooting

### Python venv issues

If you get errors activating the virtual environment, try:

```bash
# macOS/Linux
python3 -m venv venv --upgrade-deps

# Windows
python -m venv venv --upgrade-deps
```

### npm install fails

Clear cache and retry:

```bash
npm cache clean --force
npm install
```

### Port conflicts

If ports 5173/5174 are in use, Vite will use the next available port. Check the console output for the actual URL.

For the backend services, you can change ports via environment variables:

```bash
# Admin backend on port 8772
ADMIN_API_PORT=8772 python main.py

# Update admin dashboard .env.local accordingly
VITE_ADMIN_API_BASE_URL=http://127.0.0.1:8772
```

### Backend connection errors

If the dashboards show "Loading..." and then fallback to mock data, ensure both backend services are running and accessible on their respective ports.