# SentiNet Team Handoff Guide: Chapter 4 Experiments

**Objective:** Execute the experimental methodology defined in Chapter 4 (the Experiment Paper), collect the resulting data, and write up the findings. 

To ensure the integrity of the codebase, **please do not modify the core system files** (`tray-app`, `admin-backend`, etc.) unless you are fixing a critical bug. All of your custom data collection, log parsing, and analysis scripts should be created inside this `experiments/` directory.

---

## 🗺️ Repository Navigation: Where is everything?

The project is broken down into independent modules to simulate a real distributed network. Here is where you look when you need to observe specific behaviors:

### 1. The Core Agent (Tier 1 & Tier 2)
**Directory:** `tray-app/`
- **`sentinet_daemon.py`**: The heart of the system. Runs as `root`. Handles packet capture (Scapy), Tier-1 Fast-Filter (in-memory blacklist), and generates telemetry data (CPU/RAM). **Watch the terminal output of this script for exact detection timestamps.**
- **`ml_engine.py`**: The Tier-2 Detective. Houses the Random Forest logic and the 5-second sliding window feature extraction. 
- **`bayanihan_client.py`**: Handles sending and receiving threat intelligence to/from the Relay Node.

### 2. The Relay Node (Tier 3)
**Directory:** `admin-backend/`
- **`main.py`**: The FastAPI server. This acts as the centralized server that receives Attack Reports and broadcasts them via WebSockets (`Socket.io`). **Watch the terminal output of this script for Broadcast Latency timestamps.**
- **`sentinet.db`**: The SQLite database where threats are logged. You can query this directly for your data analysis.

### 3. The Hacker (Traffic Simulation)
**Directory:** `traffic-gen/`
- **`attack_generator.py`**: You will use this script heavily. It allows you to simulate targeted MITM/Poisoning attacks (~100 PPS) and high-volume ARP Flooding (~1000 PPS).

### 4. The User Interfaces
**Directories:** `admin-dashboard/` and `agent-dashboard/`
- These React/Tailwind frontends visualize the telemetry. While great for monitoring, for your formal Chapter 4 tables, you will likely want to rely on the terminal logs and the SQLite database for exact millisecond timestamps.

---

## 🔬 How to Accomplish Chapter 4

Your experiment paper requires you to fill out several specific tables. Here is how you extract the data for them:

### Phase 1: System Efficiency (Tables 5 - 8)
- **What you need:** CPU (%) and RAM (MB) usage every minute during Normal, Poisoning, and Flooding scenarios.
- **How to get it:** The `sentinet_daemon.py` has a `TelemetryEngine` thread that calculates this. You can read it directly from the local Agent Dashboard, or write a script in this `experiments/` folder that queries the `admin-backend` API (`GET /telemetry/summary`) every 60 seconds and saves it to a CSV.

### Phase 2: Detection Performance (Tables 9 - 12)
- **What you need:** True Positives, False Positives, True Negatives, False Negatives across 5 trials.
- **How to get it:** The daemon tracks total `inspected`, `dropped`, `passed`, and `blocked` packets. You can view these in the UI or fetch them via API. Compare SentiNet's block counts against your Baseline IDPS (e.g., Snort) logs.

### Phase 3: Cold-Start Condition (Table 13)
- **What you need:** Time of first detection when the blacklist is empty.
- **How to get it:** Restart the `sentinet_daemon.py` (which clears the in-memory set). Launch an attack from `traffic-gen`. Look at the daemon terminal; it will print `[Tier 2] THREAT DETECTED` with a timestamp.

### Phase 4: Collaborative Response (Tables 14 - 17)
- **What you need:** Broadcast Latency and Time-to-Block (TTB) across isolated nodes.
- **How to get it:** 
  1. Attack Agent A. Note the timestamp the threat hits the `admin-backend` terminal.
  2. Switch your attack to Agent B. Note the timestamp Agent B drops the packet in its terminal.
  3. The difference in milliseconds is your TTB.

### Phase 5: Degraded Mode (Table 18)
- **What you need:** System behavior when the Relay Node is offline.
- **How to get it:** Manually kill the `admin-backend` server `CTRL+C` while an attack is running. Verify that Agent A and B continue to block attacks locally using Tier-1 and Tier-2, even without WebSocket syncing.

---

## The `experiments/` Directory Rules

To keep the project clean, **all your work for Chapter 4 should stay inside this `experiments/` folder.**

**What goes here?**
1. **Data Parsing Scripts:** Python scripts you write to extract data from `sentinet.db` or parse terminal logs.
2. **Raw Data:** Any `.csv` or `.json` files containing your raw telemetry or timestamp recordings.
3. **Jupyter Notebooks:** If you use Pandas or Matplotlib to generate the graphs for Chapter 4, put the notebooks here.

*Example workflow:* You might write a script here called `extract_latencies.py` that connects to the `../admin-backend/sentinet.db`, pulls all the threat timestamps, and calculates the averages for Table 15 automatically.
