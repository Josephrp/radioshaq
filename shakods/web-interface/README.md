# SHAKODS Web Interface

React + TypeScript UI for audio configuration, confirmation queue, and VAD metrics.

## Setup

```bash
cd web-interface
npm install
```

## Environment

- `VITE_SHAKODS_API` – API base URL (default: `http://localhost:8000`)
- `VITE_SHAKODS_TOKEN` – Optional Bearer token for authenticated API calls

## Run

```bash
npm run dev
```

Open http://localhost:3000. The dev server proxies `/api` and `/ws` to the SHAKODS API (port 8000).

## Build

```bash
npm run build
npm run preview
```

## Features

- **Response mode** – Listen only, confirm first, confirm timeout, auto-respond
- **Confirmation queue** – Approve or reject pending responses when using confirm_first
- **VAD visualizer** – WebSocket-based heartbeat for metrics (placeholder)
- **Audio devices** – List input/output devices from the API
