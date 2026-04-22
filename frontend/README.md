# NIIP Operator Dashboard

React + Vite frontend for the Network Interface Intelligence Platform.

## Design direction

Industrial NOC terminal. Dense monospace UI. Tactical color palette (cyan/amber/red on near-black). Information density over decoration — every pixel should carry signal. Typography: JetBrains Mono (body/tables) + Space Grotesk (display headings).

## Prerequisites

- Node.js 18+ and npm 9+
- The Flask backend running on `http://localhost:5000` (the Vite dev server proxies `/api` requests to it)

## Setup

```bash
cd frontend
npm install
```

## Development

```bash
# Terminal 1 — start the Flask backend from the project root
poetry run python -m app.main

# Terminal 2 — start the Vite dev server
cd frontend
npm run dev
```

Open `http://localhost:5173`. The dashboard will call the backend via the Vite proxy.

Click **LOAD SAMPLE** to analyze the bundled 30-interface LogicMonitor CSV, or drag-and-drop your own CSV file onto the upload panel.

## Production build

```bash
cd frontend
npm run build
# Output in frontend/dist — serve behind the same reverse proxy as the API
```

### Example nginx config

```nginx
server {
  listen 80;
  server_name niip.example.com;

  root /var/www/niip-dashboard;
  index index.html;

  location / {
    try_files $uri /index.html;
  }

  location /api/ {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
  }
}
```

## Structure

```
frontend/
├── public/
│   └── favicon.svg
├── src/
│   ├── components/
│   │   ├── StatusBar.jsx          — top bar with live clock + API health
│   │   ├── UploadPanel.jsx        — file drop zone + sample load
│   │   ├── SummaryTiles.jsx       — 6 KPI tiles (healthy/warning/critical/anomalies/avg)
│   │   ├── HealthChart.jsx        — score-distribution histogram (Recharts)
│   │   ├── FleetGrid.jsx          — sortable/filterable interface table
│   │   ├── InterfaceDetail.jsx    — drill-down panel (anomalies/forecast/root cause/actions)
│   │   └── Toast.jsx              — error surface
│   ├── lib/
│   │   ├── api.js                 — fetch wrapper for the Flask backend
│   │   └── sampleData.js          — embedded LogicMonitor-style sample CSV
│   ├── styles/
│   │   └── global.css             — design tokens + base styles
│   ├── App.jsx                    — layout composition
│   └── main.jsx                   — entry point
├── index.html
├── vite.config.js
└── package.json
```

## Features

- **Live backend status** in the top bar — polls `/api/v1/health` every 15s
- **Drop-in upload or sample load** — no CSV required for first-run demo
- **Sortable / filterable fleet table** with search across device, interface, description
- **Click-to-drill-down** — selecting any interface populates the detail panel with anomalies, forecast, root cause, and ordered recommended actions
- **Score histogram** — see the shape of your fleet's health at a glance
- **Keyboard-friendly** — all controls are tabbable
- **Responsive** — collapses to single-column below 1100 px, two-column tiles below 680 px
- **Accessibility** — semantic landmarks, aria labels on icon buttons, sufficient contrast for WCAG AA in all text/background combinations

## Browser support

Modern Chromium, Firefox, Safari. No IE11.

## Hot-wiring to a different backend

The Vite dev proxy points at `http://localhost:5000`. Change `vite.config.js` or set an environment variable pointing to your backend host. The API contract is unchanged from the Flask backend — any service that implements `POST /api/v1/analysis/upload` returning the same JSON shape will work.
