# Monitoring

RadioShaq exposes a **Prometheus**-compatible scrape endpoint and an optional **VAD/metrics WebSocket** for the dashboard.

## Prometheus `/metrics`

**Endpoint:** `GET /metrics` (no authentication).

Returns Prometheus exposition format (text/plain) with:

| Metric | Type | Description |
|--------|------|-------------|
| `radioshaq_uptime_seconds` | gauge | Process uptime in seconds |
| `radioshaq_callsigns_registered_total` | gauge | Number of registered (whitelisted) callsigns |
| `radioshaq_gpu_utilization_percent` | gauge | GPU utilization 0–100 (when `nvidia-smi` is available) |
| `radioshaq_gpu_memory_used_mb` | gauge | GPU memory used in MB |
| `radioshaq_gpu_memory_total_mb` | gauge | GPU memory total in MB |

GPU metrics are populated only when **nvidia-smi** is on the PATH and returns data (e.g. NVIDIA drivers and GPU present). No extra Python dependency is required for GPU metrics.

**Optional:** Install the `prometheus_client` library for standard exposition format and future expansion (e.g. default process metrics):

```bash
cd radioshaq && uv sync --extra metrics
```

Without it, the server still exposes the gauges above in valid Prometheus text format.

**Example scrape config (Prometheus):**

```yaml
scrape_configs:
  - job_name: radioshaq
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: /metrics
```

## VAD / audio metrics WebSocket

**Endpoint:** `WS /ws/audio/metrics/{session_id}`.

Used by the dashboard **VAD visualizer** for real-time audio pipeline state (VAD active, SNR, state). By default the server sends a **placeholder heartbeat** every second (`vad_active: false`, `snr_db: null`, `state: "idle"`).

When the **voice_rx pipeline** is wired, the pipeline can push live metrics by setting **`app.state.audio_metrics_latest`** to a dict before each WebSocket send:

- `vad_active` (bool): whether voice activity is detected
- `snr_db` (float | null): signal-to-noise ratio in dB
- `state` (str): e.g. `"idle"`, `"speech"`, `"processing"`
- `type` (str, optional): e.g. `"metrics"` or `"heartbeat"`

The WebSocket handler reads this once per second and sends it to connected clients. If `audio_metrics_latest` is not set or not a dict, the placeholder heartbeat is sent.

## Health checks

Use **`GET /health`** for liveness and **`GET /health/ready`** for readiness (DB, orchestrator, audio agent). See [API Reference](api-reference.md).
