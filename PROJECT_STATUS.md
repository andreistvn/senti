# SentiNet Project Status & Implementation Roadmap

**Context for AI/Reviewer:** This document serves as the bridge between the theoretical architecture defined in the "SentiNet" thesis paper (Chapters 1-3) and the actual state of the codebase. It details what has been implemented so far and the concrete next steps required to fully realize the proposed 3-Tier Defense Architecture.

---

## 1. Current Codebase Status

The codebase has successfully scaffolded the primary runtime environments and IPC (Inter-Process Communication) plumbing, and now uses real, live data persistence and evaluation to prove out the architecture.

### What is Completed:
- **UI & Visualization Dashboards**: Both the `admin-dashboard` (IT network view) and `agent-dashboard` (local endpoint view) are built and functional. They have been successfully de-mocked to display live, real-time telemetry from their respective backends (SQLite for Admin, live traffic for Agent).
- **Backend Infrastructures**: 
  - `admin-backend`: A FastAPI server is running with SQLite database persistence via SQLAlchemy (`sentinet.db`). It includes a mocked MultiChain JSON-RPC client interface that currently catches connection errors and gracefully falls back to local SQLite logging.
  - `tray-app`: The privileged Python daemon is fully operational. It implements the dual-process architecture, handling system tray UI interactions via a local loopback API.
- **Tier 1 (Fast-Filter)**: The `tray-app` daemon successfully uses Scapy to sniff raw ARP packets and performs an O(1) lookup against an in-memory Python `set()`. If a MAC address is blacklisted, it drops the packet.
- **Tier 2 (Detective ML Engine)**: Fully integrated into `tray-app/sentinet_daemon.py` and `ml_engine.py`. Unknown MACs are evaluated via a 5-second sliding window that computes the 8-dimensional feature vector and executes an inference using the pre-trained `RandomForest` model.
- **Tier 3 (Bayanihan Collaborative Layer)**: 
  - **Relay Node**: `admin-backend` hosts an ASGI Socket.io server to accept Attack Reports and broadcast `blacklist_update` events.
  - **Agent Client**: `tray-app/bayanihan_client.py` connects to the Relay Node, transmits local threats, and listens for network-wide broadcasts to update the local Fast-Filter memory cache.
- **Machine Learning Assets**: The data collection and training pipeline is complete. The 8-dimensional Random Forest behavioral classifier (`sentinet_rf_model.joblib`) and its label encoder have been serialized and added to the project.
- **Traffic Generation Scripts**: `traffic-gen/benign_traffic.py` and `traffic-gen/attack_generator.py` have been implemented to generate both normal benign traffic and malicious network traffic (ARP spoofing, MITM, high-volume flooding) within the Kali Linux testbed.

### What is Missing (The Gap):
- **MultiChain Ledger Implementation**: The `write_to_multichain` function in `admin-backend/state.py` is currently a placeholder shell that intentionally falls back to SQLite. The actual deployment, configuration, and integration of the true MultiChain blockchain stream still needs to be completed by a teammate.

---

---

**End of Report.**
