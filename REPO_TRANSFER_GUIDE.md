# SentiNet POC Setup Guide: Transferring the Codebase to VMs

This guide covers the easiest way to transfer your codebase from your Mac to the other POC machines: the Relay Node (a Windows PC), Agent 1, Agent 2 and the Attacker VM.

## Phase 1: Transferring the Repository

The absolute easiest and most reliable way to sync your codebase across 4 VMs is using **Git**. 

### Step 1: Push from your Mac (if you haven't already)
If your code isn't on GitHub yet, create a private repository on GitHub, then run this on your Mac:
```bash
git init
git add .
git commit -m "POC ready"
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

### Step 2: Clone onto the 4 VMs
On **every** VM, open the terminal and run:
```bash
git clone <YOUR_GITHUB_REPO_URL>
cd senti
```

*(Alternative: If you don't want to use GitHub, you can use `scp` to copy the folder directly from your Mac to each VM over SSH: `scp -r ~/Downloads/senti user@<VM_IP>:~/`)*

---

## Phase 2: System Preparation (On ALL VMs)

Before launching the scripts, every VM needs its basic dependencies installed (Python virtual environments and Node modules). Run this block on **all 4 VMs**:

```bash
# Setup Python for the Backend & Daemons
cd admin-backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && cd ..
cd traffic-gen && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && cd ..

# Setup Node.js for the Dashboards
cd admin-dashboard && npm install && cd ..
cd agent-dashboard && npm install && cd ..
```

---

## Phase 3: Launching the POC

*(Follow [`WINDOWS_RELAY_SETUP.md`](WINDOWS_RELAY_SETUP.md) for the Relay Node, then [`POC_DEMO_GUIDE.md`](POC_DEMO_GUIDE.md) for the agents and attacker.)*

Note: the Relay Node runs `setup_windows_relay.bat`, which installs its own dependencies — Phase 2 above applies to the agent and attacker machines.
