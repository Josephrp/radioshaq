# RadioShaq Web Interface

React + TypeScript UI for audio configuration, confirmation queue, and VAD metrics.

## Setup

```bash
cd web-interface
npm install
```

## Environment

- `VITE_RADIOSHAQ_API` – API base URL (default: `http://localhost:8000`)
- Authentication token is set at runtime via login (`/auth/token`) and `setApiToken(...)`; it is not read from `VITE_` build-time env vars
- `VITE_GOOGLE_MAPS_API_KEY` – Optional. Google Maps JavaScript API key for the **Map** page, **Radio** page field map panel, and **Transcripts** “View on map”. Create a key in [Google Cloud Console](https://console.cloud.google.com/apis/credentials), enable **Maps JavaScript API**, and restrict the key by HTTP referrer to your app origin(s) to avoid misuse. If unset, map features show a short message instead of a map.

## Run

```bash
npm run dev
```

Open <http://localhost:3000>. The dev server proxies `/api` and `/ws` to the RadioShaq API (port 8000).

## Build

```bash
npm run build
npm run preview
```

## Features

- **Response mode** – Listen only, confirm first, confirm timeout, auto-respond
- **Confirmation queue** – Approve or reject pending responses when using confirm_first
- **VAD visualizer** – WebSocket-based metrics; shows "Placeholder" when no audio pipeline is feeding metrics
- **Audio devices** – List input/output devices from the API
- **Map** – Operator map (nav **Map**): view operator locations from the GIS API, center on a callsign, change radius. Requires `VITE_GOOGLE_MAPS_API_KEY`.
- **Field map panel** – On **Radio**: station and nearby operators map; update station location (lat/lng). Requires `VITE_GOOGLE_MAPS_API_KEY`.
- **Transcripts “View on map”** – Per-transcript button to open a modal with source/destination operator locations and distance. Requires `VITE_GOOGLE_MAPS_API_KEY`.
