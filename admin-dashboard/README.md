# SentiNet Admin Dashboard

A POC administrative dashboard for the **SentiNet Relay Node**, used to monitor a
decentralized Wi-Fi security network. Built with TypeScript, React, Tailwind, and
React Router, with a strictly utilitarian/industrial 2D flat design.

It includes:

- **Login** (`/`) — public page, gated entry to the protected dashboard.
- **Dashboard** (`/dashboard`) — protected, with tabs for **Dashboard, Analytics,
  Policy, and Settings**.
- **Threat Analytics** — live rolling AreaChart (ARP packets-per-second) and a
  historical 24-hour BarChart (Recharts).
- **Real-time push notifications** (sonner) that fire when PPS exceeds the ARP Flood Limit.
- **Policy configurator** — slider-based ML thresholds / network parameters with a
  "Broadcast to All Agents" action.
- **Node Topology & Health Map** — per-agent CPU/RAM bars with warnings when CPU > 70%.
- **Blockchain Metrics** — Block Height / Chain Status plus Export CSV for incident reports.

## Running locally

```bash
cd admin-dashboard
npm install
npm run dev
```

The app runs on **http://localhost:5175** (strict port).

## Project layout

This project is designed to sit beside two sibling apps under a shared root:

```
root/
├── dashboard/        ← agent dashboard (Vite/React), port 5173
├── tray-app/         ← Python pystray app, local API on 127.0.0.1:8770
└── admin-dashboard/  ← THIS project, port 5175
```

Port **5175** is chosen specifically to avoid colliding with the agent dashboard
(5173) and the tray API (8770). This app is fully self-contained — it does not
import from any sibling folder.
