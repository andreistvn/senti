# SentiNet System Architecture & AI Handoff Guide

**To any AI or human reading this:** This document provides a high-level overview of the SentiNet architecture, how the components interact, and **CRITICAL danger areas** (e.g., proof-of-concept mocks and incomplete features) to be aware of before modifying the code.

---

## 🏗️ Architecture Overview

The SentiNet system is a distributed Intrusion Detection and Prevention System (IDPS) built in Python and React. It consists of three primary components:

### 1. The Agent Daemon (`tray-app/`)
*   **Role:** Runs on endpoint machines (requires `sudo` for packet sniffing). It captures network traffic and evaluates it against threats.
*   **Key Files:** 
    *   `sentinet_daemon.py`: The core process. Uses `scapy` to sniff ARP packets and implements the Tier-1 (Fast-Filter O(1) in-memory blacklist) and Tier-2 (Machine Learning Random Forest) detection engines. It also tracks system telemetry (CPU/RAM).
    *   `bayanihan_client.py`: The WebSocket client that connects to the Relay Node (Admin Backend) to send threat reports and receive global blacklist updates.
    *   `state.py`: The thread-safe state manager for the daemon.
*   **IPC:** The daemon communicates with the system tray UI via a Unix socket.

### 2. The Relay Node / Admin Backend (`admin-backend/`)
*   **Role:** The centralized aggregator (Tier-3) that receives threat intelligence from all connected agents, logs them into an SQLite database, and broadcasts updates back to the network.
*   **Key Files:**
    *   `main.py`: FastAPI server serving HTTP endpoints (for the dashboard) and Socket.io WebSockets (for the agents).
    *   `state.py`: Manages the SQLite database (`sentinet.db`) via SQLAlchemy and bridges threat events onto the MultiChain ledger.
    *   `multichain.py`: JSON-RPC client for the MultiChain node plus the background worker that publishes threats, retries them while the node is down, and resyncs the local ledger mirror with the chain.

### 3. The Dashboards (`agent-dashboard/` & `admin-dashboard/`)
*   **Role:** Next.js / React frontends for visualizing the system state.
*   **Agent Dashboard:** Runs locally on the endpoint machine, connecting to the daemon's local API server (`api_server.py`) to show local telemetry and throughput.
*   **Admin Dashboard:** Connects to the Relay Node to show a global view of all agents, network-wide telemetry, and the blockchain ledger.

---

## ⚠️ DANGER AREAS: Mocks & Incomplete Features

This system is currently a **Proof-of-Concept (POC)**. Several complex distributed features are structurally present in the code but are functionally mocked. **Do not attempt to debug these as if they are fully functional distributed systems.**

### 1. The MultiChain Blockchain Needs a Running Node
*   **The Code:** `admin-backend/multichain.py` is a real JSON-RPC client. On startup it runs `getinfo`, creates and subscribes to the `threat_logs` stream if the node doesn't have it, then `publish`es one item per threat (source MAC as the stream key).
*   **The Reality:** The integration is live, but it needs an actual `multichaind` node — see `admin-backend/README.md` for the two commands that create one. Without a node the relay reports `chainStatus: DEGRADED`, queues threat records in memory (up to `MULTICHAIN_QUEUE_SIZE`), and republishes them when the node comes back. Detection and blacklist broadcast are unaffected.
*   **Impact:** The ledger table in the Admin Dashboard reads from SQLite `ledger_entries`, but that table is now a *mirror* of the chain: rows are written only after MultiChain confirms a transaction (`blockId` is the real txid prefix), and the worker re-reads the stream every `MULTICHAIN_SYNC_INTERVAL` seconds so items published by peer relay nodes appear too. Check `GET /ledger/status` to see node health, block height and publish counters.

### 2. Network Traffic Sniffing is Limited to ARP
*   **The Code:** In `tray-app/sentinet_daemon.py`, the `CaptureEngine` uses `scapy.sniff(filter="arp", ...)`
*   **The Reality:** The system *only* inspects ARP packets. If you are testing the system on a quiet network without ARP spoofing/broadcasts, the "Traffic Throughput (PPS)" metrics (Inspected, Passed, Dropped) will remain frozen at 0. 
*   **Impact:** To see the traffic counters move, you must use the `traffic-gen/attack_generator.py` script to simulate ARP attacks.

### 3. Agent "Toggle" State
*   **The Code:** The `tray-app` allows toggling the agent's protection ON and OFF.
*   **The Reality:** When toggled OFF the agent stops capturing, and its Bayanihan client disconnects from the Relay Node, removing it from the Admin Dashboard's active list. Telemetry keeps reporting real measurements either way — it used to force CPU and RAM to `0` to look "dormant", but those readings are now recorded as research data and a fabricated zero is indistinguishable from a genuine one in a dataset. Each reading carries a `protected` flag instead, so analysis can filter on capture state.

### 4. Admin Dashboard UI Mocks
*   The **Export CSV** button in the Admin Dashboard generates a mock "Manual Blacklist" ledger entry when testing features.

---

## 🛠️ How to Operate

### Starting the System

All launchers live in [`launch_scripts/`](launch_scripts/). Which one you want depends
on whether you are demonstrating the distributed architecture or just developing:

| Script | Starts | Use when |
|---|---|---|
| `start_relay_node.sh` / `.bat` | MultiChain node, `admin-backend`, Admin Dashboard | Machine 1 of the POC demo |
| `start_agent_node.sh <RELAY_IP>` / `.bat` | Capture daemon, tray app, Agent Dashboard | Machines 2 & 3 of the POC demo |
| `start_all.sh` / `.bat` | Both of the above, on one machine | Local development |

**Mac / Linux:**
To start everything on a single machine, run:
```bash
./launch_scripts/start_all.sh
```
*(Note: You will be prompted for your `sudo` password to allow the daemon to sniff network packets).*

**Windows:**
Run the batch file from an Administrator Command Prompt:
```cmd
launch_scripts\start_all.bat
```

> For the three-machine demonstration (Relay Node, two Agents, Attacker), follow
> [`POC_DEMO_GUIDE.md`](POC_DEMO_GUIDE.md). `start_all` runs a single agent, so no peer
> exists to receive a `blacklist_update` — it cannot show the collaborative defense.

### Stopping the System & Troubleshooting

If you need to shut down the system, or if it fails to start due to port conflicts (`Address already in use`), it's usually because the background Python daemon or Node servers became "zombie" processes. **Do not just close the terminal windows.**

**Mac / Linux:**
Use the provided stop script to safely and forcefully kill all associated processes:
```bash
./launch_scripts/stop_all.sh
```
*(If you are completely stuck, the script internally uses `sudo pkill -f sentinet_daemon.py` to ensure the ports are freed. It also stops the MultiChain node — pass `KEEP_CHAIN=1` to leave it running.)*

**Windows:**
Use the provided stop batch file from an Administrator Command Prompt:
```cmd
launch_scripts\stop_all.bat
```
