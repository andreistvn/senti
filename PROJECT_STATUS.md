# SentiNet Project Status & Implementation Roadmap

**Context for AI/Reviewer:** This document serves as the bridge between the theoretical architecture defined in the "SentiNet" thesis paper (Chapters 1-3) and the actual state of the codebase. It details what has been implemented so far and the concrete next steps required to fully realize the proposed 3-Tier Defense Architecture.

---

## 1. Current Codebase Status

The codebase has successfully scaffolded the primary runtime environments and IPC (Inter-Process Communication) plumbing, but currently relies on simulated data and localized inference to prove out the architecture.

### What is Completed:
- **UI & Visualization Dashboards**: Both the `admin-dashboard` (IT network view) and `agent-dashboard` (local endpoint view) are built and functional. They successfully poll their respective backends but currently display mock or simulated telemetry.
- **Backend Infrastructures**: 
  - `admin-backend`: A FastAPI server is running but uses in-memory Python dictionaries to simulate agent sessions, threat logs, and the blockchain ledger (`state.py`).
  - `tray-app`: The privileged Python daemon is fully operational. It implements the dual-process architecture, handling system tray UI interactions via a local loopback API.
- **Tier 1 (Fast-Filter)**: The `tray-app` daemon successfully uses Scapy to sniff raw ARP packets and performs an O(1) lookup against an in-memory Python `set()`. If a MAC address is blacklisted, it simulates an instant drop, fulfilling the Tier-1 active mitigation requirement.
- **Machine Learning Assets**: The data collection and training pipeline is complete. The 8-dimensional Random Forest behavioral classifier (`sentinet_rf_model.joblib`) and its label encoder have been serialized and added to the project. The raw training datasets (`.csv`) and scripts have been isolated into a `model-training/` directory and `.gitignore` has been updated to prevent repo bloat.

### What is Missing (The Gap):
- The pre-trained `.joblib` model is not yet actively executing inferences inside the `tray-app` packet capture loop (Tier 2 is missing).
- There is no 5-second sliding window mechanism to extract behavioral features (like ARP request-to-reply ratio) from the live network traffic.
- The backends do not communicate threat intelligence with each other. The Tier-3 Bayanihan (Relay Node) WebSocket broadcast is not implemented.
- The `admin-backend` lacks a real database (SQLite/PostgreSQL) and the immutable MultiChain ledger integration.

---

## 2. Detailed Implementation Plan (Next Steps)

To transition from the current "mocked" state to the fully functional decentralized IDPS described in the thesis, the following phases must be executed:

### Phase 1: Tier-2 (Detective ML Engine) Integration
Currently, `tray-app/sentinet_daemon.py` drops packets if they are in the blacklist (Tier 1), but lacks the ML logic for unknown packets. We will integrate the Random Forest model into the capture loop.

1. **Create `tray-app/ml_engine.py`**:
   - Load `sentinet_rf_model.joblib` and `sentinet_label_encoder.joblib` using `scikit-learn`.
   - Implement the **5-second Sliding Window** logic to track and aggregate packet data per MAC address.
   - Calculate the 8-dimensional feature vector: ARP request rate, ARP reply rate, request-to-reply ratio, inter-arrival mean, inter-arrival variance, packet burstiness, unique IP-per-MAC count, and gratuitous ARP count.
2. **Modify `tray-app/sentinet_daemon.py`**:
   - Hook the `CaptureEngine` to feed unknown MAC addresses into the sliding window in `ml_engine.py`.
   - Execute the inference. If the model's probability score is $\ge 0.50$, automatically add the MAC to the local Tier-1 in-memory blacklist.
   - Generate an "Attack Report" payload (MAC, Timestamp, Score) to be sent to the Relay Node.

### Phase 2: Tier-3 (Bayanihan Collaborative Layer)
The thesis requires isolated nodes to share intelligence without direct peer-to-peer communication, using a Relay Node to bypass Client Isolation.

1. **Modify `admin-backend/main.py` (Relay Node)**:
   - Add a **WebSocket (Socket.io) Server** to accept incoming Attack Reports from any active SentiNet Agent.
   - When an Attack Report is received, instantly broadcast the malicious MAC address to all other connected agents so they can update their local Tier-1 blacklists.
2. **Create `tray-app/bayanihan_client.py`**:
   - Implement a WebSocket client in the agent daemon that continuously listens to the Relay Node.
   - When a broadcast is received, safely insert the new MAC address into the Tier-1 `DaemonState.blacklist`.

### Phase 3: Blockchain Ledger & Persistence
The final layer guarantees immutability and persistence, moving away from the hardcoded Python dictionaries in the current codebase.

1. **Database Integration (`admin-backend/state.py`)**:
   - Replace the in-memory arrays for `agents`, `threats`, and `sessions` with an ORM (like SQLAlchemy) backed by **SQLite**. This fulfills the persistence requirement for the proof-of-concept.
2. **MultiChain Integration**:
   - Per the thesis (Chapter 3), the MultiChain daemon will be deployed natively on the physical Central Relay Node. 
   - When a new threat is verified by the backend, write the metadata (blockId, timestamp, macHash, score) to the permissioned MultiChain stream via its JSON-RPC API, ensuring the "tamper-proof audit trail" described in the paper.

---

**End of Report.**
