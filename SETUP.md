# SentiNet Development Setup

Complete setup and run instructions for the full stack: admin backend, admin dashboard, agent dashboard, system tray daemon, and the newly added machine learning & experiment pipelines.

## Repository Structure

- `admin-backend/`: The Relay Node FastAPI server & SQLite DB
- `admin-dashboard/`: The Relay Node Next.js/Vite frontend
- `agent-dashboard/`: The Agent local frontend
- `tray-app/`: The Agent Daemon (runs as root, handles packet sniffing & detection)
- `traffic-gen/`: Scripts to simulate benign traffic, ARP floods, and MITM poison attacks
- `model-training/`: Pipeline for extracting datasets and training the Random Forest models
- `experiments/`: Scripts and notebooks for running evaluations (Chapter 4 methodology)

## Prerequisites

- **Node.js** 18+ (for dashboards)
- **Python** 3.9+ (for backends, daemons, and ML)
- **npm** or **pnpm** (for dashboards)

## Initial Setup (Run Once)

Before you can run the system, you must install the dependencies for each component.

In case of incompatible commands due to OS differences, just look up the equivalent commands for your operating system.

### 1. Admin Backend

```bash
cd admin-backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..
```

### 2. Admin Dashboard

```bash
cd admin-dashboard
npm install
cd ..
```

### 3. Agent Dashboard

```bash
cd agent-dashboard
npm install
cd ..
```

### 4. Tray Daemon

```bash
cd tray-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..
```

**Windows**

### 1. Admin Backend

```bash
cd admin-backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

### 2. Admin Dashboard

```bash
cd admin-dashboard
npm install
cd ..
```

### 3. Agent Dashboard

```bash
cd agent-dashboard
npm install
cd ..
```

### 4. Tray Daemon

```bash
cd tray-app
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

---

## Starting the System (Quick Start)

Once dependencies are installed, the easiest way to boot everything up on a single
machine is the all-in-one launcher:

```bash
./launch_scripts/start_all.sh
```

_(Note: You will be prompted for your `sudo` password to allow the daemon to sniff network packets. It may take a minute for the Node servers to compile)._

> This runs the relay node and one agent on the same machine — convenient for
> development, but it does not exercise the decentralized architecture. To run the
> three-machine demo (Relay Node + two Agents + Attacker), follow
> [`POC_DEMO_GUIDE.md`](POC_DEMO_GUIDE.md), which uses
> `launch_scripts/start_relay_node.sh` and `launch_scripts/start_agent_node.sh`.

> **macOS note:** MultiChain ships no Mac binary (Windows/Linux x86-64 only), so on a
> Mac the relay starts with the ledger disabled — it warns, sets
> `MULTICHAIN_ENABLED=false`, and everything except the blockchain ledger works
> normally. To get the ledger, host the relay on a Windows PC:
> [`WINDOWS_RELAY_SETUP.md`](WINDOWS_RELAY_SETUP.md) is the full walkthrough.

## Quick Start (Windows)

To start the entire system on Windows, open an **Administrator Command Prompt** and run the batch script:

```cmd
launch_scripts\start_all.bat
```

---

## Manual Component Setup

If you prefer to run components manually (or need to see specific terminal outputs for debugging), follow these steps (assuming you have already run the Initial Setup):

### Terminal 1: Admin Backend

```bash
cd admin-backend
source venv/bin/activate
python3 main.py
```

Runs on `http://127.0.0.1:8771`.

### Terminal 2: Admin Dashboard

```bash
cd admin-dashboard
npm run dev
```

Open `http://localhost:5175` in your browser.
_(Note: Configuration like the Backend URL is pre-configured in `.env.local`, which is deliberately tracked in version control for this POC)._

### Terminal 3: Agent Dashboard

```bash
cd agent-dashboard
npm run dev
```

Open `http://localhost:5173` (or next available port).

### Terminal 4: Tray Daemon (Agent Backend)

```bash
cd tray-app
source venv/bin/activate
python3 sentinet_tray.py
```

Runs on `http://127.0.0.1:8770` (background process).

### Terminal 5: Traffic Generation Testbed (Experimental)

To perform the T-Test evaluations described in the methodology, run these scripts on the Kali Linux testbed:

```bash
cd traffic-gen
# Simulate normal network background noise:
python3 benign_traffic.py

# Simulate a high-volume ARP flood attack (~1,000 PPS):
python3 attack_generator.py flood --target <TARGET_IP>

# Simulate a targeted Man-in-the-Middle (MITM) ARP poisoning attack:
python3 attack_generator.py poison --target <TARGET_IP> --gateway <GATEWAY_IP>
```

## Service URLs

| Service         | URL                   | Purpose                                  |
| --------------- | --------------------- | ---------------------------------------- |
| Admin Dashboard | http://localhost:5175 | Web UI for system administration         |
| Agent Dashboard | http://localhost:5173 | Web UI for agent protection status       |
| Admin Backend   | http://127.0.0.1:8771 | API for admin dashboard (localhost only) |
| Tray Daemon     | http://127.0.0.1:8770 | API for agent dashboard (localhost only) |

## Credentials

**Admin Dashboard Login:**

- Digital ID: `ADM-7734-ALPHA`
- Password: `SentiNet@2049`
- MFA Code: `482910`

**Agent Dashboard:**

- Digital ID: _(Any value)_
- Password: _(Any value)_
- _(The agent dashboard currently accepts any mock credentials during this POC phase)._

## Troubleshooting

### Clean Shutdown / Zombie Processes

If the system fails to start due to port conflicts (`Address already in use`), or if you need to shut down the system after using `start_all`, **do not just close the terminal windows.**

The stop script also shuts the MultiChain node down (`multichain-cli sentinet stop`); pass `KEEP_CHAIN=1` to leave it running.

**Mac / Linux:**
Run the stop script to safely and forcefully kill all Python and Node processes related to the system:

```bash
./launch_scripts/stop_all.sh
```

**Windows:**
Run the stop batch script from an Administrator Command Prompt:

```cmd
launch_scripts\stop_all.bat
```

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

### Backend connection errors

If the dashboards show "Loading..." and then fallback to mock data, ensure both backend services are running and accessible on their respective ports. Verify that the URL in `.env.local` matches the port your backend is actually running on.
