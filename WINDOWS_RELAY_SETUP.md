# Relay Node Setup — Windows

This is the guide for whoever hosts the **Relay Node** (Machine 1) on a Windows PC.

You do not need to know anything about the rest of the project. Two commands and
you're done: one to install, one to run.

**Why Windows:** MultiChain — the permissioned blockchain behind SentiNet's Tier 3
"Bayanihan" layer — ships native binaries for Windows and Linux x86-64 only. There's
no macOS or ARM build, so the relay runs here.

---

## What you need

- Windows 10 or 11, 64-bit
- ~2 GB free disk space
- The PC on the **same network** as the rest of the demo machines
- Administrator access (for the firewall rule — the setup script asks for it)

Python and Node.js are handy to have already, but the setup script installs them via
`winget` if they're missing.

---

## Step 1 — Get the code

Install [Git for Windows](https://git-scm.com/download/win) if you don't have it, then
in Command Prompt:

```bat
cd %USERPROFILE%
git clone <repo-url> senti
cd senti
```

No Git? Download the repo as a ZIP and extract it to `C:\Users\<you>\senti`.

---

## Step 2 — Run the setup (once)

```bat
launch_scripts\setup_windows_relay.bat
```

It will ask for administrator permission — that's for the firewall rule that lets the
agent machines connect.

It does five things:

1. Checks for Python 3 and Node.js, installing them via `winget` if missing.
2. Downloads MultiChain 2.3.3 and installs it to
   `%LOCALAPPDATA%\SentiNet\multichain`, then **runs it to confirm it works**.
3. Creates the Python virtual environment and installs the backend dependencies.
4. Installs the dashboard's npm packages (the slow part — a few minutes).
5. Opens TCP **8771** and **5175** in Windows Firewall.

> **If it installs Python or Node**, it will tell you to close the window and run the
> script again. That's normal — a new terminal is needed to pick up the updated PATH.

> **Antivirus:** MultiChain's own README warns that antivirus software may block
> `multichaind.exe`. If the script reports that the binary won't run, add an exclusion
> for `%LOCALAPPDATA%\SentiNet\multichain` and run it again.

At the end it prints **this machine's LAN IP** — write it down, the agent machines
need it.

---

## Step 3 — Start the relay

```bat
launch_scripts\start_relay_node.bat
```

Every time you want the relay running. It:

1. Creates the `sentinet` blockchain on first run.
2. Starts the MultiChain node in its own window.
3. Reads the node's real RPC credentials and writes `admin-backend\.env`.
4. Starts the relay API on port 8771, reachable from other machines.
5. Starts the Admin Dashboard on port 5175.

You'll end up with several windows open. **Leave them all running.** The one titled
*SentiNet MultiChain Node* is the blockchain — if something goes wrong, its output is
where to look.

Expected ending:

```
RELAY NODE is up.
   Admin API:        http://192.168.1.50:8771  (bound on 0.0.0.0)
   Admin Dashboard:  http://localhost:5175
   MultiChain:       sentinet

   Point agent machines at this relay with:
     launch_scripts\start_agent_node.bat 192.168.1.50
```

**Send that last line to your teammates** — it's exactly what they run on the agent
machines.

---

## Step 4 — Check it works

```bat
curl http://localhost:8771/health
"%LOCALAPPDATA%\SentiNet\multichain\multichain-cli.exe" sentinet getinfo
```

Expect `{"status":"ok"}` and then the chain's name and block height.

> `multichain-cli` isn't on your system `PATH` — MultiChain is installed into a
> private folder, not a machine-wide location. The full path above works from any
> Command Prompt. (The window running `start_relay_node.bat` itself has it on `PATH`
> for that session, so the bare command also works there.)

Then open <http://localhost:5175>, log in with digital ID **`ADM-7734-ALPHA`**, and
confirm the **Chain Status** tile reads **HEALTHY**.

If it reads `DEGRADED`, the relay isn't talking to the blockchain. Run this for the
exact reason:

```bat
curl http://localhost:8771/ledger/status
```

---

## Step 5 — Shut down

```bat
launch_scripts\stop_all.bat
```

Closes the dashboards, the relay and the MultiChain node cleanly. Don't just close the
windows — the blockchain flushes data on a proper shutdown.

To leave the blockchain running between sessions:

```bat
set KEEP_CHAIN=1 && launch_scripts\stop_all.bat
```

---

## Everyday use

| Task | Command |
|---|---|
| Start the relay | `launch_scripts\start_relay_node.bat` |
| Stop everything | `launch_scripts\stop_all.bat` |
| Clear the threat log for a fresh demo | `flush_db.bat` |

`flush_db.bat` clears the local database only. The blockchain keeps its full history —
which is rather the point of a ledger. To reset the chain itself, stop everything and
delete `%APPDATA%\MultiChain\sentinet`; the next start rebuilds it.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `'multichaind' not found` | Run `launch_scripts\setup_windows_relay.bat` first. |
| Setup says `multichaind.exe would not run` | Antivirus quarantined it. Add an exclusion for `%LOCALAPPDATA%\SentiNet\multichain`, then re-run setup. |
| `'python' is not recognized` | Python isn't on PATH. Reinstall from [python.org](https://www.python.org/downloads/) with **"Add python.exe to PATH"** ticked. |
| MultiChain node window opens then closes instantly | Read it before it vanishes: run `multichaind sentinet` directly in a Command Prompt to see the error. Usually antivirus or a port conflict. |
| Agents can't connect | Confirm you gave them the **LAN IP**, not `localhost`. Check both machines are on the same network, and that the firewall rules exist: `netsh advfirewall firewall show rule name="SentiNet Relay API 8771"` |
| Dashboard loads but everything is empty | `admin-dashboard\.env.local` has the wrong address. Re-run `start_relay_node.bat` — it rewrites it with the current LAN IP. |
| `Chain Status: DEGRADED` | `"%LOCALAPPDATA%\SentiNet\multichain\multichain-cli.exe" sentinet getinfo` to see if the node is alive; `curl http://localhost:8771/ledger/status` for the exact error. Threat reports queue in memory and publish automatically once the chain returns — nothing is lost. |
| `'multichain-cli' is not recognized` | It's not on `PATH` — that's expected in a fresh Command Prompt. Use the full path shown above, or run the check from the window `start_relay_node.bat` is running in. |
| LAN IP changed (new Wi-Fi, reboot) | Re-run `start_relay_node.bat` and send teammates the new IP. A static IP or DHCP reservation avoids this. |

---

## What this machine does in the demo

It's the collaborative-defense hub. Agents on other machines detect ARP attacks
locally, report them here, and this node:

1. Writes the threat to the MultiChain ledger (the tamper-evident audit record).
2. Broadcasts the attacker's MAC to **every other agent**, so they block a host they
   have never seen attack them.

That second point is the thesis claim the whole POC exists to demonstrate — and it
runs through this machine.

Full demo script: [`POC_DEMO_GUIDE.md`](POC_DEMO_GUIDE.md)
