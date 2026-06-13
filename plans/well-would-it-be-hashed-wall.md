# Plan: Complete Setup Docs + Local-Run Scaffolding (prerequisites)

## Context

The tray app and dashboard integration are built, but the docs assume Python and
Node are already installed and — critically — told the user to run `npm run dev`,
which **does not exist**. This Figma Make project is not a runnable standalone
Vite app: `package.json` has only a `build` script, `react`/`react-dom` are
*optional* peer deps (a fresh `npm install` skips them), and there is no
`index.html`, no `src/main.tsx` bootstrap, and no `tsconfig.json`. So after
export the dashboard cannot start in a browser, and the tray ↔ dashboard link
can't be demonstrated. This plan fills every gap so a from-zero machine can run
both halves.

User decision: **ignore the Figma Make preview** — only local execution matters,
on **macOS**. So the scaffolding goes straight into the repo (no `local-dev/`
indirection) and the guide is macOS-first (Homebrew). The standard Vite entry
imports `./styles/index.css` + `App` — the `figma:foundry-client-api` virtual
import in `__figma__entrypoint__.ts` is Figma-only and is intentionally omitted.

## Changes

### 1. `package.json`
- Add scripts: `"dev": "vite"`, `"preview": "vite preview --port 5173"`.
- Move `react` `18.3.1` and `react-dom` `18.3.1` into `dependencies` (currently
  optional peer deps) so a plain `npm install` pulls them.

### 2. Local-run scaffolding (created directly in the repo)
- `index.html` (root) — Vite host page: `<div id="root">` +
  `<script type="module" src="/src/main.tsx">`.
- `src/main.tsx` — `createRoot(document.getElementById('root')!).render(<App/>)`,
  importing `./styles/index.css` and `./app/App` (mirrors `__figma__entrypoint__.ts`
  minus the figma virtual module).
- `tsconfig.json` (root) + `tsconfig.node.json` — React-JSX, bundler resolution,
  `@ → src` alias matching `vite.config.ts`.

### 3. New root `SETUP.md` — single from-zero macOS guide
- **Prerequisites (macOS):** install **Homebrew**, then `brew install python`
  and `brew install node`; verify `python3 --version`, `node --version`,
  `npm --version`.
- **Part 1 — Web dashboard:** `npm install` → `npm run dev` → open
  `http://localhost:5173`.
- **Part 2 — Tray app:** `cd tray-app`, venv, `pip install -r requirements.txt`,
  `python sentinet_tray.py` (note: macOS tray works out of the box).
- **Part 3 — Connect them** + green "TRAY CONNECTED" / amber "MOCK MODE" badge.
- **Troubleshooting:** port in use, blank page, tray not detected (port mismatch),
  Python `externally-managed-environment` (use the venv).

### 4. Fix stale instruction in `tray-app/README.md`
Point first-time setup at `SETUP.md`; keep the quick `npm run dev` command.

## Verification
- Clean macOS: follow `SETUP.md` top-to-bottom → `npm install && npm run dev`
  serves the dashboard at `:5173` with amber "MOCK MODE" and no console errors.
- `python sentinet_tray.py` → tray icon appears; dashboard badge turns green
  "TRAY CONNECTED"; toggling from tray or dashboard updates both.

---

# (Built) Plan: Python `pystray` Tray App + Live Dashboard Integration

> NOTE: This supersedes the earlier "detach" plan below, which is already
> implemented. The tray UI now lives at `src/_reference_tray-app/`. This new
> plan builds the REAL native tray controller in Python and wires the existing
> React dashboard to read live state from it.

## Context

The system tray controller cannot run inside Figma Make (browser-only). The user
will **export the project and run it on their own machine**. They want a complete,
runnable Python `pystray` tray app that (a) owns the protection on/off state,
(b) exposes a local loopback HTTP API, and (c) is wired to the existing React
dashboard so the dashboard shows **real** state and counters from the tray —
falling back to mock data when the tray isn't running.

Confirmed decisions:
- **Tray UI = OS menu only** (Toggle Protection / Open Dashboard / Quit). No popup window.
- **Full integration**: tray runs a loopback HTTP API; the React dashboard fetches live state; "Open Dashboard" opens the browser.
- No real packet sniffing — the daemon **simulates** traffic/threats (mirrors the existing React mock logic), so it runs without root and without Scapy.

## Part A — Python tray app (new folder `tray-app/`, outside `src/`)

`.py` files are ignored by Vite/Figma Make, so this ships alongside the web code
without affecting the bundle. Dependencies kept minimal: **`pystray`** + **`pillow`**
(icon rendering). The HTTP API uses the **Python standard library** (`http.server`
+ `ThreadingHTTPServer`) — no Flask/FastAPI needed.

Files to create:
- `tray-app/sentinet_tray.py` — entry point. Builds the `pystray.Icon` with a
  PIL-generated shield glyph that is **green when protected, grey when off**.
  Menu: a disabled status line, **Toggle Protection** (checkable), **Open Dashboard**
  (`webbrowser.open(DASHBOARD_URL)`), **Quit**. Starts the API server + simulation
  threads, runs `icon.run()` on the main thread.
- `tray-app/api_server.py` — `ThreadingHTTPServer` on `127.0.0.1:8770` serving JSON
  with permissive CORS (handles `OPTIONS` preflight for the POST). Endpoints:
  - `GET  /api/status`  → `{ protected, relay, version, since }`
  - `POST /api/toggle`  → flips protection, returns new status
  - `GET  /api/stats`   → `{ inspected, dropped, passed, blocked, cpu, memory, bayanihan:{contributions,usersProtected}, lastThreat }`
  - `GET  /api/events`  → recent simulated detection-log rows (mac/attack/tier/action/timestamp)
  - `GET  /api/health`  → the daemon-services list (mirrors `INITIAL_DAEMONS` in `Dashboard.tsx:57`)
- `tray-app/state.py` — thread-safe `AgentState` (protection flag, counters,
  rolling event log) + a `SimulationEngine` background thread that, **only while
  protected**, increments inspected/dropped/passed, bumps Bayanihan occasionally,
  and emits threat events — porting the logic from `Dashboard.tsx:117` and
  `AgentToggle.tsx`'s interval so the numbers feel identical.
- `tray-app/config.py` — `API_HOST/API_PORT` (8770) and `DASHBOARD_URL`
  (default `http://localhost:5173`), overridable via env vars.
- `tray-app/requirements.txt` — `pystray`, `pillow`.
- `tray-app/README.md` — per-OS run steps (`python -m venv`, `pip install -r
  requirements.txt`, `python sentinet_tray.py`), Linux note (`pystray` needs a
  GTK/AppIndicator backend), how to point it at the dashboard URL, and a clear
  statement that traffic is simulated (no root / no Scapy).

## Part B — Wire the React dashboard to the tray (live data + fallback)

New files:
- `src/app/lib/trayClient.ts` — typed fetch helpers (`getStatus`, `toggle`,
  `getStats`, `getHealth`, `getEvents`) against `http://127.0.0.1:8770`, each with
  a short `AbortController` timeout so a missing tray fails fast.
- `src/app/hooks/useTrayConnection.ts` — polls `/api/status` + `/api/stats` every
  2s; returns `{ connected, status, stats, toggle() }`. `connected=false` on any error.

Edit `src/app/components/Dashboard.tsx`:
- Consume `useTrayConnection`. When `connected`, drive these from live data instead
  of the local `setInterval` mock: the **Protection Status** card (`Dashboard.tsx:250`,
  currently hardcoded `PROTECTED`), **inspected/dropped/passed** (`:91-93`),
  **CPU/memory** (`:86-89`), **Bayanihan** (`:96-97`), **Last Detected Threat**
  (`:273`), and the **Diagnostics** services (`:114`) from `/api/health`.
- Keep the existing mock generators as the **fallback** path when `!connected`, so
  the dashboard still works standalone inside Figma Make.
- Make the header `LIVE` badge (`Dashboard.tsx:214`) reflect reality:
  green **"TRAY CONNECTED"** vs amber **"MOCK MODE"**.
- Add a small toggle control to the Protection Status card that calls `toggle()`
  (POST `/api/toggle`) so on/off is bidirectional between tray and dashboard.
- The existing `setInterval` effect (`:117`) becomes the fallback-only simulator
  (guarded by `!connected`) to avoid fighting live data.

## Verification

- **Web (in Figma Make):** dashboard still renders with no tray running — badge
  shows amber "MOCK MODE", counters animate via the fallback simulator, no console
  errors from failed fetches (they're caught/timed out).
- **Native (user's machine, documented in README):**
  1. `cd tray-app && python -m venv .venv && pip install -r requirements.txt`
  2. `python sentinet_tray.py` → shield icon appears in the OS tray (grey).
  3. Run the exported web app (`npm i && npm run dev`) and open it (or use tray →
     Open Dashboard). Badge turns green "TRAY CONNECTED".
  4. Click tray **Toggle Protection** → icon turns green, dashboard Protection card
     flips to PROTECTED and counters start climbing. Toggle the dashboard control →
     tray menu checkmark + icon update. Confirm `/api/status`, `/api/stats`,
     `/api/health` return JSON via `curl http://127.0.0.1:8770/api/status`.

---

# (Completed) Plan: Detach the System Tray App into Isolated Reference Code

## Context

The SentiNet Agent project currently ships the **system tray controller** and the **web dashboard** as one Figma Make web bundle, switched between by a dev launcher in `App.tsx`. This conflates two things that are fundamentally different in the real architecture: the tray controller is meant to be a native OS process (Python `pystray` / Electron / Tauri), while the dashboards are genuine web apps. Figma Make can only produce browser React, so the tray will never be a *real* tray here.

The user wants the Figma Make project to become **dashboard-only**, and the tray code lifted into an **isolated folder** that nothing imports — so it ships nowhere in the running app and can be copied out wholesale into a separate native project later. Decision confirmed: **full detach** (no preview switch).

## Current state (from exploration)

- **Tray-only:** `src/app/tray/TrayEntry.tsx`, `src/app/components/AgentToggle.tsx`
- **Dashboard-only:** `src/app/dashboard/DashboardEntry.tsx`, `src/app/components/{Register,Login,Dashboard}.tsx`
- **Launcher/shared:** `src/app/App.tsx` (holds `AuthContext` + the `'launcher' | 'tray' | 'dashboard'` switcher)
- The tray subtree is already self-contained: it only connects to the rest of the app through `App.tsx`'s launcher and an `onOpenDashboard` callback prop. The dashboard does **not** import any tray file. `AuthContext` is consumed only by `Register.tsx`.

This makes the detach low-risk: it's mostly a move plus simplifying `App.tsx`.

## Changes

### 1. Create the isolated reference folder
New directory `src/_reference_tray-app/` (leading underscore + `_reference` signals "not part of the build"). Move into it:
- `src/app/tray/TrayEntry.tsx` → `src/_reference_tray-app/TrayEntry.tsx`
- `src/app/components/AgentToggle.tsx` → `src/_reference_tray-app/AgentToggle.tsx`

Fix the relative import in the moved `TrayEntry.tsx` so it points at the co-located `./AgentToggle`. Replace the `onOpenDashboard` prop wiring (which previously came from `App.tsx`) with a self-contained stub/no-op and a comment, so the file reads as standalone reference rather than depending on the launcher.

### 2. Add a porting README
New `src/_reference_tray-app/README.md` describing:
- That this is **inert reference code** — nothing in the Figma Make app imports it.
- What the tray controller is supposed to be (native OS tray process) and that it must be rebuilt in Python (`pystray` + a webview) or Electron/Tauri.
- How it talked to the dashboard here (`onOpenDashboard` callback) vs. how it *should* talk to the real daemon (local loopback HTTP API).
- Which shared styles/deps it relied on (`lucide-react`, `sonner`, `@radix-ui/react-switch`, `@radix-ui/react-dropdown-menu`, the JetBrains Mono / Inter fonts and the hardcoded color palette) so the user can recreate them in the new project.

### 3. Make the Figma Make app boot straight into the dashboard
Rewrite `src/app/App.tsx` so it:
- Drops the `'launcher' | 'tray' | 'dashboard'` state, the launchpad UI, the hidden env switcher, and the import of `TrayEntry`.
- Keeps `AuthContext` (still needed by `Register`) and renders `DashboardApp` directly as the default export, wrapped in the provider.

### 4. Remove the now-empty tray plumbing
- Delete the empty `src/app/tray/` directory.
- Leave `DashboardEntry.tsx` and all dashboard components untouched.

## Files touched
- **Move:** `src/app/tray/TrayEntry.tsx`, `src/app/components/AgentToggle.tsx` → `src/_reference_tray-app/`
- **Edit:** moved `TrayEntry.tsx` (import path + stub the dashboard callback)
- **Rewrite:** `src/app/App.tsx` (dashboard-only boot)
- **New:** `src/_reference_tray-app/README.md`
- **Delete:** `src/app/tray/` (empty)

## Verification
- Load the Figma Make preview: it should open **directly on the dashboard flow** (Register → Login → Dashboard) with no launcher screen and no tray option.
- Confirm nothing in `src/app/` imports anything under `src/_reference_tray-app/` (grep for `AgentToggle` and `tray-app` — should only appear inside the reference folder).
- Confirm the dashboard tabs (Dashboard, Analytics, Whitelist, Diagnostics) still render and the app compiles with no missing-import errors.
- Open `src/_reference_tray-app/` and confirm `TrayEntry.tsx` + `AgentToggle.tsx` + `README.md` are present and self-describing for export.
