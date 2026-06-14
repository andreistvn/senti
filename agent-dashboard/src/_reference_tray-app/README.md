# System Tray Controller — Reference Code (NOT part of the web app)

This folder contains the UI for the **SentiNet System Tray Controller**. It is
**inert**: nothing in the Figma Make project imports anything from here, so it
ships in no bundle and cannot break the dashboard. It exists so you can lift it
out wholesale into a real native project.

## Why it lives here and not in the running app

Figma Make produces **browser React only**. A real system tray controller is a
**native OS process** — it owns a tray/menu-bar icon and talks to the privileged
daemon over a local loopback API. That cannot run in a browser tab. So the tray
UI was extracted here as a visual/behavioral reference to rebuild natively.

## Files

- `AgentToggle.tsx` — the 340×480 tray popup: protection toggle (Protected /
  Local Only / Unprotected), live packet/blocked stats, module statuses, and an
  "Open Agent Dashboard" button. All data is simulated with `setInterval`.
- `TrayEntry.tsx` — a `createMemoryRouter` wrapper that mounts `AgentToggle` and
  the `sonner` toast surface used for blocked-threat notifications.

## How to port it

Pick a native shell that can render a webview and own a tray icon:

- **Python** — `pystray` for the tray icon + `pywebview` to render this React UI.
- **Electron** or **Tauri** — `Tray` API + a renderer window.

Then wire the real behavior:

- Replace the `onOpenDashboard` no-op in `TrayEntry.tsx` with an action that
  opens the locally-served **Agent Dashboard** (the daemon's loopback URL).
- Replace the simulated `setInterval` packet/threat data in `AgentToggle.tsx`
  with calls to the daemon's local HTTP API (status, counters, threat events).
- The toggle's on/off should call the daemon to start/stop protection rather
  than only flipping local React state.

## Dependencies this UI relies on

Recreate these in the new project:

- `react`, `react-router` (memory router)
- `lucide-react` (icons)
- `sonner` (toast notifications)
- `@radix-ui/react-switch`, `@radix-ui/react-dropdown-menu`
- Tailwind CSS, plus the **JetBrains Mono** + **Inter** fonts
- The dark navy / red-accent palette is hardcoded as hex values in the
  `className` / `style` props (e.g. `#0b1120`, `#0d1b3e`, `#1e3a5f`, `#00ccaa`,
  `#1a4fd6`, `#ff3b3b`, `#00cc66`, `#f59e0b`).
