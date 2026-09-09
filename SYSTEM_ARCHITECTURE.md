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
    *   `state.py`: Manages the SQLite database (`sentinet.db`) via SQLAlchemy and handles the (currently mocked) MultiChain integration.

### 3. The Dashboards (`agent-dashboard/` & `admin-dashboard/`)
*   **Role:** Next.js / React frontends for visualizing the system state.
*   **Agent Dashboard:** Runs locally on the endpoint machine, connecting to the daemon's local API server (`api_server.py`) to show local telemetry and throughput.
*   **Admin Dashboard:** Connects to the Relay Node to show a global view of all agents, network-wide telemetry, and the blockchain ledger.

---

## ⚠️ DANGER AREAS: Mocks & Incomplete Features

This system is currently a **Proof-of-Concept (POC)**. Several complex distributed features are structurally present in the code but are functionally mocked. **Do not attempt to debug these as if they are fully functional distributed systems.**

### 1. The MultiChain Blockchain is NOT Real
*   **The Code:** In `admin-backend/state.py`, the `write_to_multichain()` function attempts to make a JSON-RPC call to a local MultiChain node. 
*   **The Reality:** There is no MultiChain node running. The function is designed to catch the `requests.exceptions.ConnectionError`, log a warning, and silently skip writing to the blockchain. 
*   **Impact:** The system gracefully falls back to just logging the threat in the local SQLite database (`DBLedgerEntry`). The blockchain ledger shown in the Admin Dashboard is simply reading from this SQLite table, using a truncated UUID/TxID snippet as the `blockId`. 

### 2. Network Traffic Sniffing is Limited to ARP
*   **The Code:** In `tray-app/sentinet_daemon.py`, the `CaptureEngine` uses `scapy.sniff(filter="arp", ...)`
*   **The Reality:** The system *only* inspects ARP packets. If you are testing the system on a quiet network without ARP spoofing/broadcasts, the "Traffic Throughput (PPS)" metrics (Inspected, Passed, Dropped) will remain frozen at 0. 
*   **Impact:** To see the traffic counters move, you must use the `traffic-gen/attack_generator.py` script to simulate ARP attacks.

### 3. Agent "Toggle" State
*   **The Code:** The `tray-app` allows toggling the agent's protection ON and OFF.
*   **The Reality:** When toggled OFF, the `TelemetryEngine` in the daemon artificially forces reported CPU and RAM metrics to `0` to reflect a "dormant" state on the dashboard. The agent also disconnects its WebSocket from the Relay Node, removing it from the Admin Dashboard's active list.

### 4. Admin Dashboard UI Mocks
*   The **Export CSV** button in the Admin Dashboard generates a mock "Manual Blacklist" ledger entry when testing features.

---

## 🛠️ How to Operate

### Starting the System

**Mac / Linux:**
To start the entire system (Backend, Daemon, and Dashboards) simultaneously, run:
```bash
./start_all.sh
```
*(Note: You will be prompted for your `sudo` password to allow the daemon to sniff network packets).*

**Windows:**
To start the entire system on Windows, run the provided batch file from an Administrator Command Prompt:
```cmd
start_all.bat
```

### Stopping the System & Troubleshooting

If you need to shut down the system, or if it fails to start due to port conflicts (`Address already in use`), it's usually because the background Python daemon or Node servers became "zombie" processes. **Do not just close the terminal windows.**

**Mac / Linux:**
Use the provided stop script to safely and forcefully kill all associated processes:
```bash
./stop_all.sh
```
*(If you are completely stuck, the script internally uses `sudo pkill -9 -f sentinet_daemon.py` to ensure the ports are freed).*

**Windows:**
Use the provided stop batch file from an Administrator Command Prompt:
```cmd
stop_all.bat
```
