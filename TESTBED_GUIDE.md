# SentiNet Experimental Testbed Guide

This guide details the exact, step-by-step procedure to set up and test SentiNet across your 3 Kali Linux VMs and your Host Machine.

## 1. Network Setup

Configure your 3 Kali Linux VMs in **Bridged Adapter Mode** so they receive unique IPs on your network.

- **Host Machine:** Runs the central Relay Server and Admin Dashboard.
- **VM 1 (Agent A):** Runs the local SentiNet Agent daemon and Agent Dashboard.
- **VM 2 (Agent B):** Runs the local SentiNet Agent daemon and Agent Dashboard.
- **VM 3 (Attack Generator):** Runs the traffic generation scripts (Does NOT run SentiNet).

---

## 2. Host Machine Setup (The Relay Node)

Do this on your physical computer (or a 4th central VM). 

**Terminal 1 (Admin Backend):**
```bash
cd admin-backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

**Terminal 2 (Admin Dashboard):**
```bash
cd admin-dashboard
npm install
npm run dev
```

---

## 3. VM 1 (Agent A) Setup

Do this entirely inside your first Kali Linux VM.

**Terminal 1 (Daemon - requires root):**
```bash
cd tray-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo venv/bin/python3 sentinet_daemon.py
```

**Terminal 2 (Tray UI - do NOT use root):**
```bash
cd tray-app
source venv/bin/activate
python3 sentinet_tray.py
```

**Terminal 3 (Agent Dashboard):**
```bash
cd agent-dashboard
npm install
npm run dev
```

---

## 4. VM 2 (Agent B) Setup

Do this entirely inside your second Kali Linux VM. *(These are the exact same steps you did for VM 1)*

**Terminal 1 (Daemon - requires root):**
```bash
cd tray-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo venv/bin/python3 sentinet_daemon.py
```

**Terminal 2 (Tray UI - do NOT use root):**
```bash
cd tray-app
source venv/bin/activate
python3 sentinet_tray.py
```

**Terminal 3 (Agent Dashboard):**
```bash
cd agent-dashboard
npm install
npm run dev
```

---

## 5. VM 3 (Attack Generator) Setup

Do this inside your third Kali Linux VM. This VM will act as the hacker.

**Terminal 1 (Traffic Scripts):**
```bash
cd traffic-gen
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 6. How to Run the Experiment (SOP 3)

Now that everything is running across your machines, it's time to test the collaborative defense!

1. Go to **VM 3 (Attack Generator)** and launch a targeted attack against Agent A's IP address:
   ```bash
   python3 attack_generator.py poison --target <IP_OF_AGENT_A> --gateway <IP_OF_ROUTER>
   ```
2. Look at **VM 1 (Agent A)**: The daemon will detect the anomaly and block it locally.
3. Look at the **Host Machine (Admin Dashboard)**: You will see the Threat logged to the blockchain and broadcasted across the network.
4. Go back to **VM 3 (Attack Generator)** and try to attack Agent B:
   ```bash
   python3 attack_generator.py poison --target <IP_OF_AGENT_B> --gateway <IP_OF_ROUTER>
   ```
5. Look at **VM 2 (Agent B)**: The attack will instantly fail (dropped at Tier-1) because Agent B already received the threat broadcast from Agent A!
