# SentiNet — Proof of Concept Demo Guide

This guide walks through a **three-machine demonstration** of SentiNet's decentralized
IDPS: one Relay Node running the Bayanihan ledger, two Agent Nodes defending
themselves, and an Attacker generating the ARP traffic that triggers the collaborative
defense.

The point of the demo is the moment in **Step 4**: Agent A detects an attacker on its
own, publishes that finding to the MultiChain ledger, and Agent B blocks the same MAC
address *without ever having seen the attack*.

---

## Machine Roles

| Machine | Role | What runs on it |
|---|---|---|
| **Machine 1** | Relay Node | MultiChain node, `admin-backend` (FastAPI + Socket.io), Admin Dashboard |
| **Machine 2** | Agent A | `sentinet_daemon.py`, tray app, Agent Dashboard |
| **Machine 3** | Agent B | `sentinet_daemon.py`, tray app, Agent Dashboard |
| **Machine 4**\* | Attacker | `traffic-gen/attack_generator.py` (Kali Linux) |

\* The attacker can share a machine with nothing else, or you can run the attack from
a fourth box. What matters is that all machines sit on the **same isolated Layer-2
network** — ARP does not cross routers, so the agents must be on the same subnet as
the attacker for Tier 1/Tier 2 detection to see anything.

### Before you start

On every machine: clone the repo, then install dependencies.

```bash
# Python venvs (admin-backend, tray-app, traffic-gen — whichever that machine needs)
cd admin-backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# Dashboards
cd admin-dashboard && npm install     # Machine 1
cd agent-dashboard && npm install     # Machines 2 & 3
```

MultiChain is needed **only on Machine 1**:

On **Windows** (the recommended relay host) one script installs MultiChain, Python
and the dashboard dependencies for you — see
[`WINDOWS_RELAY_SETUP.md`](WINDOWS_RELAY_SETUP.md):

```bat
launch_scripts\setup_windows_relay.bat
```

On an **x86-64 Linux** relay, install MultiChain by hand:

```bash
wget https://www.multichain.com/download/multichain-2.3.3.tar.gz
tar -xvzf multichain-2.3.3.tar.gz
sudo mv multichain-2.3.3/multichain* /usr/local/bin/
```

> ### ⚠️ Machine 1 must run Linux or Windows
>
> **MultiChain publishes no macOS binary** — the community download page offers
> Linux 64-bit and Windows 64-bit only, with "compile from source" as the sole Mac
> path (and no Apple Silicon build). A Mac therefore cannot host the relay's ledger
> without building MultiChain yourself, which is not a supported path for this project.
>
> Pick one:
>
> | Option | What you get |
> |---|---|
> | **Relay on an x86-64 Linux box** | Full POC, real ledger. Install MultiChain manually (see above). ARM machines — including UTM VMs on Apple Silicon — can't run it without emulation, which is not worth the trouble. |
> | **Relay on Windows** (recommended) | Full POC, native MultiChain, no VM or emulation. Setup guide: [`WINDOWS_RELAY_SETUP.md`](WINDOWS_RELAY_SETUP.md) |
> | **Relay on macOS** | Everything *except* the ledger. `start_relay_node.sh` detects the missing node, warns, and runs with `MULTICHAIN_ENABLED=false`. Detection, blocking and the collaborative blacklist broadcast all still work; Chain Status reads `DEGRADED` and the Ledger tab stays empty |
>
> Running on a Mac for development is fine — just don't record the thesis demo
> there, because the ledger is the Tier 3 evidence.

Note each machine's LAN IP (`ip addr` / `ifconfig` / `ipconfig`) — you'll need
Machine 1's address for the agents.

---

## Step 1 — Start the Relay Node (Machine 1)

```bash
./launch_scripts/start_relay_node.sh
```
```bat
launch_scripts\start_relay_node.bat
```

This single command:

1. Creates the `sentinet` MultiChain chain if it doesn't exist yet, and starts
   `multichaind sentinet -daemon`.
2. Waits for the chain's JSON-RPC port to accept connections.
3. Reads the real `rpcuser`, `rpcpassword` and `rpcport` out of
   `~/.multichain/sentinet/` and writes them into `admin-backend/.env`
   (any existing `.env` is backed up to `.env.bak`).
4. Starts the FastAPI relay, bound to `0.0.0.0:8771` so the agent machines can reach it.
5. Starts the Admin Dashboard on port 5175.

If `multichaind` isn't installed (e.g. you're on a Mac), the script prints a warning
banner, writes `MULTICHAIN_ENABLED=false`, and continues — you get a working relay
with no ledger. It says so plainly in the summary:
`MultiChain: *** DISABLED — no ledger, Chain Status = DEGRADED ***`.
Set `REQUIRE_CHAIN=1` to make a missing node abort instead.

**The script prints the exact command to run on the agent machines — copy it.** It
looks like:

```
Point agent machines at this relay with:
  ./launch_scripts/start_agent_node.sh 192.168.10.10
```

### Verify before continuing

```bash
curl -s http://localhost:8771/health          # -> {"status":"ok"}
multichain-cli sentinet getinfo               # -> chain name, block height
```

Open <http://localhost:5175>, log in with digital ID **`ADM-7734-ALPHA`**, and check
the **Chain Status** tile reads `HEALTHY`. If it reads `DEGRADED`, the relay can't
reach the chain — hit `GET /ledger/status` for the exact error:

```bash
curl -s -b cookies.txt http://localhost:8771/ledger/status
```

> **Firewall:** the agents connect inbound on **TCP 8771**. Open it before Step 2:
> `sudo ufw allow 8771/tcp` (Linux) or a matching inbound rule in Windows Defender Firewall.

---

## Step 2 — Start the Agent Nodes (Machines 2 & 3)

On **each** agent machine, passing Machine 1's LAN IP:

```bash
./launch_scripts/start_agent_node.sh 192.168.10.10
```
```bat
launch_scripts\start_agent_node.bat 192.168.10.10
```

This starts the privileged Scapy daemon (it will prompt for `sudo` — Tier 1 needs raw
socket access), the tray app, and the Agent Dashboard on port 5173. The script pings
the relay's `/health` first and warns you if it's unreachable, rather than failing
silently later. It also verifies the daemon actually came up before moving on — if
elevation was declined or Scapy couldn't bind, it stops with an error instead of
silently starting a dashboard with no data behind it. Check `/tmp/sentinet_daemon.log`
(macOS/Linux) or the **SentiNet Agent Daemon** window (Windows) for the real reason.

**Then click the tray icon and toggle protection ON.** The daemon doesn't capture
until you do. The agent reports itself to the relay on connect.

### Verify before continuing

On Machine 1's Admin Dashboard, both agents should now appear in the agent list with
state `PROTECTED`. If an agent is missing, check `/tmp/sentinet_daemon.log` on that
machine for connection errors.

---

## Step 3 — Establish a benign baseline (optional but recommended)

From the attacker machine, or any agent machine:

```bash
cd traffic-gen && source venv/bin/activate
python3 benign_traffic.py
```

Let this run for a minute. It generates normal HTTP and DNS activity so the demo shows
the ML engine *not* firing on ordinary traffic — which is what makes the detection in
Step 4 meaningful rather than a system that flags everything.

---

## Step 4 — Run the attack (Attacker machine)

This is the demonstration. Run **one** attack at a time and watch all three dashboards.

### 4a. Targeted MITM / ARP poisoning (~100 PPS → Tier 2, the ML engine)

Point it at **Agent A's IP**, with your network's real gateway:

```bash
cd traffic-gen && source venv/bin/activate
sudo python3 attack_generator.py poison --target 192.168.10.21 --gateway 192.168.10.1
```

### 4b. High-volume ARP flood (~1,000 PPS → Tier 1 / Tier 2)

```bash
sudo python3 attack_generator.py flood --target 192.168.10.21
```

### What to watch — the collaborative defense

| Where | What you should see |
|---|---|
| **Agent A dashboard** (the target) | Packets Inspected climbs; the Random Forest scores the attacker's MAC ≥ 0.50; the MAC is blocked locally and Dropped starts counting |
| **Admin Dashboard → Threat Log** | A new incident from Agent A: attack type, tier, confidence |
| **Admin Dashboard → Ledger** | A new row appears — `blockId` is a real MultiChain transaction id, not a placeholder |
| **Admin Dashboard → Block Height** | Increments (the relay publishes one stream item per threat) |
| **Agent B dashboard** (never attacked) | **The attacker's MAC appears in its blacklist.** This is the Bayanihan layer: the relay broadcast `blacklist_update` over Socket.io and Agent B's Tier 1 filter absorbed it |

Confirm it on the chain itself, from Machine 1:

```bash
multichain-cli sentinet liststreamitems threat_logs
```

Each item's `keys` holds the attacker's MAC and `data.json` holds the timestamp,
attack type and confidence score.

---

## Step 5 — Shut down

On **each** machine:

```bash
./launch_scripts/stop_all.sh
```
```bat
launch_scripts\stop_all.bat
```

This kills the dashboards, the FastAPI relay, the Python daemons (with `sudo` where
needed) and runs `multichain-cli sentinet stop`. Pass `KEEP_CHAIN=1` to leave the
MultiChain node up between runs.

---

## Quick local testing (single machine)

You don't need three machines to exercise the code. To run the relay and one agent
together on one box:

```bash
./launch_scripts/start_all.sh
```
```bat
launch_scripts\start_all.bat
```

This calls `start_relay_node` then `start_agent_node` pointed at `localhost`, giving
you the Admin Dashboard on 5175 and the Agent Dashboard on 5173.

**This does not demonstrate the decentralized architecture** — with one agent there is
no peer to receive a `blacklist_update`, which is the whole claim the POC exists to
prove. Use it for development; use the three-machine setup for the actual demo.

On macOS this additionally runs without the ledger (no MultiChain binary exists for
Mac — see the box in *Before you start*), so Chain Status will read `DEGRADED`.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Chain Status shows `DEGRADED` | Relay can't reach MultiChain. Check `multichain-cli sentinet getinfo`, then `curl .../ledger/status` for the exact RPC error. Threats are queued in memory meanwhile and republish automatically once the node returns — nothing is lost. |
| Agents don't appear on the Admin Dashboard | Wrong relay IP, port 8771 firewalled, or protection not toggled ON in the tray. Check `/tmp/sentinet_daemon.log`. |
| Traffic counters frozen at 0 | The daemon only sniffs ARP. A quiet network produces nothing — run the traffic generators. |
| Agent B never receives the blacklist update | Both agents must be connected to the *same* relay. Confirm both are listed in the Admin Dashboard before attacking. |
| `multichaind: command not found` (any relay platform) | MultiChain isn't installed or isn't on `PATH`. The relay script no longer aborts on this — it warns, writes `MULTICHAIN_ENABLED=false`, and starts everything else without the ledger (`Chain Status` reads `DEGRADED`). Install it: Windows — `launch_scripts\setup_windows_relay.bat`; Linux — the install snippet above. macOS has no build at all — host the relay on Windows or Linux instead. Set `REQUIRE_CHAIN=1` to make a missing node a hard error instead. |
| Agent script exits with `the agent daemon is not running` | Elevation/`sudo` was declined, or Scapy failed to bind a raw socket. Check `/tmp/sentinet_daemon.log` (macOS/Linux) or the **SentiNet Agent Daemon** window (Windows) for the real error. |
| Relay started but Ledger tab is empty and Chain Status is `DEGRADED` | Either no chain node (see above) or `MULTICHAIN_ENABLED=false` in `admin-backend/.env`. Check the relay's console for the `[MultiChain]` line printed at startup. |
| Attack generator sees no target | Attacker and agents must be on the same Layer-2 subnet; ARP does not route. |
| `.env` has stale credentials | Re-run `start_relay_node.sh`; it regenerates `.env` from the live chain config each time (old one saved as `.env.bak`). |

## Reference

- Architecture and known limitations: [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md)
- Ledger internals and RPC config: [`admin-backend/README.md`](admin-backend/README.md)
- Thesis alignment: [`analysis_results.md`](analysis_results.md)
