# SentiNet — Local Setup (macOS, from zero)

This guide takes a Mac with **nothing installed** to both halves running and
talking to each other:

- **Web dashboard** — the React app, served at `http://localhost:5173`.
- **Tray app** — the Python `pystray` controller in [`tray-app/`](./tray-app/),
  which the dashboard reads live state from.

Follow the parts in order.

---

## 0. Prerequisites (install once)

### a. Homebrew (the macOS package manager)
Open **Terminal** (Cmd+Space → "Terminal") and run:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
After it finishes, follow the on-screen "Next steps" (it prints two
`echo ... >> ~/.zprofile` lines and an `eval` line) so the `brew` command works
in new terminals.

### b. Node.js + npm (for the web dashboard)
```bash
brew install node
```

### c. Python 3 (for the tray app)
```bash
brew install python
```

### d. Verify everything
```bash
node --version     # expect v18 or newer
npm --version      # expect 9 or newer
python3 --version  # expect 3.10 or newer
```
If all three print a version, you're ready.

---

## 1. Web dashboard

From the **project root** (the folder containing `package.json`):

```bash
npm install
```

### One-time scaffolding file you must create

The project was authored in Figma Make, which uses its own hidden entry point.
For local Vite it needs a standard `index.html` at the project root. **Create a
file named `index.html`** next to `package.json` with exactly this content:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>SentiNet Agent Dashboard</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

> `src/main.tsx`, `tsconfig.json`, and the `dev` script already exist in the
> project — `index.html` is the only file you add by hand (a Figma Make export
> quirk).

### Start it
```bash
npm run dev
```
Open the printed URL — **http://localhost:5173**. You'll see the dashboard with
an amber **"MOCK MODE"** badge in the header: that's expected when the tray app
isn't running yet (it falls back to simulated data). Leave this terminal running.

---

## 2. Tray app

Open a **second** Terminal tab/window (Cmd+T):

```bash
cd tray-app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python sentinet_tray.py
```

A small **shield icon** appears in your macOS menu bar (top-right):
- **grey** = unprotected, **green** = protected.
- Click it for: **Protection Active** (toggle), **Open Dashboard**, **Quit**.

macOS shows the tray icon out of the box — no extra system packages needed.

---

## 3. Connect them

With both running:

1. In the menu-bar icon, choose **Open Dashboard** (or just refresh
   `http://localhost:5173`).
2. The header badge turns green **"TRAY CONNECTED"**. The Protection card,
   relay status, traffic counters, CPU/memory, Bayanihan tracker, detection log,
   and diagnostics now show **live** data from the tray.
3. Toggle protection from **either** side — the menu-bar icon and the dashboard
   stay in sync.

Quick API sanity check (optional):
```bash
curl http://127.0.0.1:8770/api/status
curl -X POST http://127.0.0.1:8770/api/toggle
```

---

## Troubleshooting

- **Badge stays amber "MOCK MODE":** the tray app isn't running, or it's on a
  different port. Confirm `python sentinet_tray.py` is up and that
  `curl http://127.0.0.1:8770/api/status` returns JSON. If you changed the port,
  update `BASE_URL` in `src/app/lib/trayClient.ts` to match `tray-app/config.py`.
- **Blank white page at :5173:** you probably skipped creating `index.html`, or
  it doesn't point at `/src/main.tsx`. Re-check step 1.
- **`Port 5173 is already in use`:** stop the other process, or run
  `npm run dev -- --port 5174` and set `SENTINET_DASHBOARD_URL=http://localhost:5174`
  before launching the tray app.
- **`error: externally-managed-environment` from pip:** you're not in the venv.
  Run `source .venv/bin/activate` first (your prompt should show `(.venv)`).
- **`command not found: brew` after install:** open a new terminal, or run the
  `eval "$(/opt/homebrew/bin/brew shellenv)"` line Homebrew printed.
- **Menu-bar icon doesn't appear:** make sure you're on a desktop session (not
  SSH), and that `pip install` finished without errors (`pystray`, `pillow`).

---

## What's simulated

There is **no real packet capture**. The tray's `SimulationEngine` generates
traffic and threat events so the agent ↔ dashboard link is fully demonstrable
without root or Scapy. To make it real later, replace that engine in
`tray-app/state.py` — the dashboard API contract stays identical. See
[`tray-app/README.md`](./tray-app/README.md) for the endpoint reference.
