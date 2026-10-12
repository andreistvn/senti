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

MultiChain (Tier 3 ledger) — see `.env.example` for the full list:

- `MULTICHAIN_ENABLED` — Set to `false` to run without a chain node (default: `true`)
- `MULTICHAIN_RPC_URL` — Node JSON-RPC endpoint (default: `http://127.0.0.1:4365`)
- `MULTICHAIN_RPC_USER` / `MULTICHAIN_RPC_PASSWORD` — From `~/.multichain/<chain>/multichain.conf`
- `MULTICHAIN_STREAM_NAME` — Threat stream (default: `threat_logs`)

Resource telemetry:

- `TELEMETRY_SAMPLE_INTERVAL` — Seconds between recorded readings (default: `60`)
- `TELEMETRY_SCENARIO` — Label for the current measurement run (default: blank)
- `TELEMETRY_RECORD` — Set `false` to stop recording (default: `true`)

## MultiChain Ledger

Threat reports are published to a permissioned MultiChain stream over JSON-RPC. All
RPC I/O runs on a background worker thread (`multichain.py`), so a slow or offline
node never blocks the Socket.io event loop that propagates blacklist updates.

On startup the worker verifies the node is reachable, creates the stream if it is
missing, and subscribes to it. Each threat is published with the source MAC as the
stream key. Records queue in memory while the node is down and republish when it
returns.

`ledger_entries` in SQLite is a **mirror** of the stream, not the ledger: the worker
writes confirmed transactions into it and re-reads the stream every
`MULTICHAIN_SYNC_INTERVAL` seconds, so threats published by peer relay nodes show up
in the dashboard too. `GET /ledger/status` reports node health, block height, RPC
latency and publish counters.

### Bringing up a node

```bash
multichain-util create sentinet
multichaind sentinet -daemon
# Credentials + rpcport land in ~/.multichain/sentinet/; copy them into .env
```

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
- `GET /ledger` — List blockchain ledger entries (newest first)
- `GET /ledger/status` — MultiChain node health, block height and publish counters

### Telemetry

- `GET /telemetry/summary` — The relay's own CPU (%) / RAM (MB), chain metrics
- `GET /telemetry/readings` — Every recorded resource sample; `?scenario=` filters

## Resource Telemetry

Chapter 3 defines resource consumption as **CPU usage (%) and RAM consumption
(MB) tracked at one-minute intervals**, then analyses it with the mean, sample
variance and an independent-samples t-test against a traditional-IDPS baseline.

**Agents measure their own process**, not the whole machine. The agent figure is
what the traditional-IDPS comparison rests on, and an endpoint also runs the
user's own software — a machine-wide reading would count the browser and VM
overhead, so a difference could not be attributed to SentiNet. RAM is reported as
RSS in megabytes; the system-wide percentage is kept alongside it only to drive
the dashboard gauge.

**The relay is measured host-wide**, deliberately. Its numbers are not research
data — the benchmarking in Chapter 3 is about agent performance, and the relay
exists to bridge Client Isolation rather than to be evaluated. What the admin
dashboard needs is operational: "is this box coping?", on a node dedicated to
hosting the relay. A host-level reading also captures `multichaind` and the
dashboard server without enumerating them.

Readings accumulate in the `telemetry_readings` table rather than overwriting a
current value, because the mean, variance and t-test all need every sample.
Recording is rate-limited per source, so the dashboards can keep refreshing every
second while the dataset stays on the paper's one-minute cadence.

### Running a measurement run

```bash
TELEMETRY_SCENARIO=arp_flood_1000pps ./launch_scripts/start_relay_node.sh
```

Then export the dataset:

```bash
python experiments/export_telemetry.py --scenario arp_flood_1000pps
```

That writes a CSV and prints per-group **n, mean and sample variance (n-1)** —
the inputs to the t-test. It does not perform the test; the inferential step is
left to SPSS, Excel or scipy.

Each row carries a `system` column (default `sentinet`) so a traditional-IDPS
baseline measured the same way can sit in the same table for comparison, and a
`protected` flag recording whether the agent was capturing at the time.

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
