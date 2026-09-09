# SentiNet Local Testbed Guide (Single Machine)

This guide walks you through running the entire SentiNet 3-Tier Architecture (Relay Node, Agent Dashboards, Daemon, Tray App, and Attack Generator) entirely on your local machine (e.g., your Mac). 

This is the fastest way to test the codebase and verify the ML models without setting up virtual machines.

---

## 1. The Relay Node (Admin Backend)
This acts as your centralized blockchain server that receives and broadcasts threats.

**Terminal 1:**
```bash
cd admin-backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```
*API runs on `http://localhost:8000`*

---

## 2. The Relay Dashboard (Admin UI)
The web interface for the central server.

**Terminal 2:**
```bash
cd admin-dashboard
npm install
npm run dev
```
*UI runs on `http://localhost:5173`*

---

## 3. The Agent Daemon (Requires Root)
This is the Tier-1 and Tier-2 engine. It runs `scapy` to sniff packets and the ML engine to score them.

**Terminal 3:**
```bash
cd tray-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# We must run this as root so Scapy can inject/sniff raw frames
sudo venv/bin/python3 sentinet_daemon.py
```

---

## 4. The Agent UI & API (Standard User)
This runs the unprivileged tray icon (the shield in your menu bar) and the API server that powers the local dashboard.

**Terminal 4:**
```bash
cd tray-app
source venv/bin/activate
python3 sentinet_tray.py
```
*(You should now see the Shield Icon in your menu bar. Right-click works here!)*

---

## 5. The Agent Dashboard (Web UI)
The web interface for the local endpoint agent.

**Terminal 5:**
```bash
cd agent-dashboard
npm install
npm run dev
```
*UI runs on `http://localhost:5174`*

**Verification Step:** 
Go to `http://localhost:5174`. Ensure it says "Connected". Toggle the protection to **ON**. The menu bar icon should turn Green.

---

## 6. The Attack Generator
Simulate a Gratuitous ARP flood to trigger the ML Engine.

**Terminal 6:**
```bash
cd traffic-gen
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the attack against a dummy IP to prevent breaking your real network
sudo python3 attack_generator.py flood --target 192.168.1.99
```

### Expected Results:
1. **Agent Dashboard (`:5174`):** The "Traffic Throughput" graphs will instantly spike. Within seconds, a new Threat will appear in the "Detection Log" indicating an ARP Spoofing attack was blocked.
2. **Admin Dashboard (`:5173`):** The exact same threat will appear in the Global Threat Log, proving the Bayanihan Collaborative layer successfully relayed the intelligence.
