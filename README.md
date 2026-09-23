# SentiNet — Agent Machine Setup

How to run SentiNet on an **agent machine** (the laptops being protected).

Setting up the **Relay Node** instead? See [`WINDOWS_RELAY_SETUP.md`](WINDOWS_RELAY_SETUP.md).
Running the full demo? See [`POC_DEMO_GUIDE.md`](POC_DEMO_GUIDE.md).

---

## The short version

Everything below is automated. From the repo root:

**Windows** (Command Prompt, run as Administrator — Scapy needs it):

```bat
launch_scripts\start_agent_node.bat <RELAY_IP>
```

**macOS / Linux:**

```bash
./launch_scripts/start_agent_node.sh <RELAY_IP>
```

Replace `<RELAY_IP>` with the relay machine's LAN IP — its start script prints the
exact command to use. This starts the capture daemon, the tray app and the agent
dashboard together, then tells you if anything failed.

Stop everything with `launch_scripts\stop_all.bat` (or `./launch_scripts/stop_all.sh`).

> Running the whole system on one machine for testing? Use
> `launch_scripts\start_all.bat` / `./launch_scripts/start_all.sh` instead — it starts
> the relay and one agent locally.

---

## First-time install

The launch scripts expect dependencies to already be installed. Once per machine:

**Windows:**

```bat
cd senti\agent-dashboard
npm install

cd ..\tray-app
python -m venv venv
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**macOS / Linux:**

```bash
cd senti/agent-dashboard
npm install

cd ../tray-app
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

> **The folder must be named `venv`, not `.venv`.** The launch scripts look for
> `tray-app/venv`; if they don't find it they fall back to your system Python, which
> won't have Scapy installed, and the daemon fails with a confusing import error.

---

## Running the pieces by hand

Only needed for debugging — `start_agent_node` does all of this for you.

| Component | Command | Notes |
|---|---|---|
| Capture daemon | `sudo venv/bin/python sentinet_daemon.py` (Windows: run `python sentinet_daemon.py` as Administrator) | Needs root/admin for raw packet capture |
| Tray app | `python sentinet_tray.py` | Serves the dashboard's local API on port 8770 |
| Agent dashboard | `npm run dev` in `agent-dashboard/` | Opens on port 5173 |

Point the daemon at a relay on another machine with an environment variable:

```bash
export SENTINET_RELAY_URL=http://192.168.1.50:8771   # Windows: set SENTINET_RELAY_URL=...
```

---

## After starting

Click the tray icon and **toggle protection ON** — the daemon doesn't capture until
you do. Then confirm this machine shows up in the relay's Admin Dashboard agent list.

The agent dashboard is at <http://localhost:5173>.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Traffic counters stuck at 0 | The daemon only sniffs ARP. A quiet network produces nothing — run the attack generator from `traffic-gen/`. |
| Agent missing from the Admin Dashboard | Wrong relay IP, port 8771 blocked by a firewall, or protection not toggled ON. Check `/tmp/sentinet_daemon.log` (macOS/Linux) or the daemon window (Windows). |
| `ModuleNotFoundError: scapy` | The venv is named `.venv` instead of `venv`, or wasn't activated. See the note above. |
| Dashboard loads but shows nothing | The tray app isn't running — it serves the API the dashboard reads. |
