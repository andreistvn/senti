# SentiNet Agent — System Tray Controller (Python / pystray)

This is the **native** tray controller for SentiNet. It runs on your machine —
**not** inside Figma Make — and gives you an OS tray/menu-bar icon to toggle
protection and open the dashboard. While running, it serves a small local API
that the web dashboard reads for **live** state.

> Traffic and threats are **simulated** (no real packet capture). It needs no
> root and no Scapy — the goal is a fully working, demoable agent ↔ dashboard
> link, not a production sniffer.

## What's inside

| File | Role |
|------|------|
| `sentinet_tray.py` | Entry point. Builds the tray icon + menu, starts the API and simulator. |
| `api_server.py`    | Loopback JSON API on `127.0.0.1:8770` (stdlib only, CORS enabled). |
| `state.py`         | Thread-safe agent state + the traffic/threat simulator. |
| `config.py`        | Host/port + dashboard URL (override via env vars). |
| `requirements.txt` | `pystray`, `pillow`. |

## Run it

```bash
cd tray-app
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python sentinet_tray.py
```

A shield icon appears in your tray (grey = unprotected, green = protected).
Right-click for: **Protection Active** (toggle), **Open Dashboard**, **Quit**.

### Connect it to the dashboard

1. Get the web dashboard running locally first. **First-time setup (installing
   Node/Python, the one manual `index.html` step, etc.) is in
   [`../SETUP.md`](../SETUP.md).** Once scaffolded, it's just:
   ```bash
   npm install
   npm run dev          # serves on http://localhost:5173 by default
   ```
2. With the tray app running, open the dashboard (or use tray → **Open Dashboard**).
   The header badge turns green **"TRAY CONNECTED"** and the Protection card,
   counters, telemetry, Bayanihan tracker, detection log and diagnostics all show
   live data from the tray. Toggling from either side updates the other.
3. If the tray isn't running, the dashboard automatically falls back to its own
   mock data and shows an amber **"MOCK MODE"** badge — nothing breaks.

## Configuration (environment variables)

| Variable | Default | Meaning |
|----------|---------|---------|
| `SENTINET_API_HOST` | `127.0.0.1` | API bind host |
| `SENTINET_API_PORT` | `8770` | API port (must match the dashboard client) |
| `SENTINET_DASHBOARD_URL` | `http://localhost:5173` | where "Open Dashboard" navigates |
| `SENTINET_SIM_TICK` | `1.0` | simulator tick in seconds |

If you change the port, also update `BASE_URL` in
`src/app/lib/trayClient.ts` so the dashboard polls the right place.

## API reference

| Method | Path | Returns |
|--------|------|---------|
| GET  | `/api/status` | `{ protected, relay, version, since }` |
| POST | `/api/toggle` | flips protection → new status |
| GET  | `/api/stats`  | `{ inspected, dropped, passed, blocked, cpu, memory, bayanihan:{contributions,usersProtected}, lastThreat, protected }` |
| GET  | `/api/events` | `{ events: [{ id, timestamp, sourceMac, attackType, tier, action }] }` |
| GET  | `/api/health` | `{ services: [{ id, name, status, detail, uptime }] }` |

Quick check:
```bash
curl http://127.0.0.1:8770/api/status
curl -X POST http://127.0.0.1:8770/api/toggle
```

## Platform notes

- **Linux:** `pystray` needs a system tray backend. On GNOME install the
  AppIndicator extension; the GTK backend also needs `gir1.2-appindicator3` (or
  `libayatana-appindicator`). On a headless box there is no tray — run on a desktop session.
- **macOS / Windows:** work out of the box with the `pip` install above.

## Making it real later

Swap the `SimulationEngine` in `state.py` for actual capture (e.g. Scapy on a
privileged process) and have the toggle start/stop your real protection logic.
The dashboard contract (the endpoints above) stays the same.
