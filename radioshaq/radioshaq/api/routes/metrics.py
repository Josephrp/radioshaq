"""Prometheus /metrics endpoint and optional GPU gauges."""

from __future__ import annotations

import subprocess
import time
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

metrics_router = APIRouter()

# Uptime start (process start time)
_start_time = time.monotonic()


def _uptime_seconds() -> float:
    return time.monotonic() - _start_time


def _get_gpu_metrics() -> list[dict[str, Any]]:
    """Return list of GPU stats (utilization, memory) via nvidia-smi. Empty if unavailable."""
    import csv
    import io
    result = []
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if out.returncode != 0 or not out.stdout:
            return result
        for row in csv.reader(io.StringIO(out.stdout)):
            if len(row) >= 5:
                result.append({
                    "index": int(row[0].strip()) if row[0].strip().isdigit() else 0,
                    "name": row[1].strip() if len(row) > 1 else "gpu",
                    "utilization_gpu": int(row[2].strip()) if row[2].strip().isdigit() else 0,
                    "memory_used_mb": int(row[3].strip()) if row[3].strip().isdigit() else 0,
                    "memory_total_mb": int(row[4].strip()) if row[4].strip().isdigit() else 0,
                })
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return result


async def _callsign_count(request: Request) -> int:
    """Return number of registered callsigns if repo available."""
    repo = getattr(request.app.state, "callsign_repository", None)
    if repo is not None:
        try:
            registered = await repo.list_registered()
            return len(registered)
        except Exception:
            pass
    db = getattr(request.app.state, "db", None)
    if db is not None and hasattr(db, "list_registered_callsigns"):
        try:
            registered = await db.list_registered_callsigns()
            return len(registered)
        except Exception:
            pass
    return 0


def _render_prometheus_with_client(request: Request, callsign_count: int) -> str | None:
    """If prometheus_client is installed, register gauges and return exposition format."""
    try:
        from prometheus_client import CollectorRegistry, Gauge, generate_latest
    except ImportError:
        return None

    # Use a temporary registry so we don't pollute global REGISTRY with per-request gauges
    registry = CollectorRegistry()
    g_uptime = Gauge("radioshaq_uptime_seconds", "Process uptime in seconds", registry=registry)
    g_uptime.set(_uptime_seconds())
    g_callsigns = Gauge("radioshaq_callsigns_registered_total", "Number of registered (whitelisted) callsigns", registry=registry)
    g_callsigns.set(callsign_count)

    gpu_metrics = _get_gpu_metrics()
    if gpu_metrics:
        g_util = Gauge("radioshaq_gpu_utilization_percent", "GPU utilization (0-100)", ["gpu_index", "gpu_name"], registry=registry)
        g_mem_used = Gauge("radioshaq_gpu_memory_used_mb", "GPU memory used (MB)", ["gpu_index", "gpu_name"], registry=registry)
        g_mem_total = Gauge("radioshaq_gpu_memory_total_mb", "GPU memory total (MB)", ["gpu_index", "gpu_name"], registry=registry)
        for g in gpu_metrics:
            idx = str(g["index"])
            name = (g.get("name") or "gpu").replace(" ", "_")[:32]
            g_util.labels(gpu_index=idx, gpu_name=name).set(g.get("utilization_gpu", 0))
            g_mem_used.labels(gpu_index=idx, gpu_name=name).set(g.get("memory_used_mb", 0))
            g_mem_total.labels(gpu_index=idx, gpu_name=name).set(g.get("memory_total_mb", 0))

    return generate_latest(registry).decode("utf-8", errors="replace")


def _render_prometheus_fallback(callsign_count: int) -> str:
    """Minimal Prometheus exposition when prometheus_client is not installed."""
    lines = [
        "# RadioShaq metrics (minimal; install with: uv sync --extra metrics)",
        "# TYPE radioshaq_uptime_seconds gauge",
        f"radioshaq_uptime_seconds {_uptime_seconds():.2f}",
        "# TYPE radioshaq_callsigns_registered_total gauge",
        f"radioshaq_callsigns_registered_total {callsign_count}",
    ]
    for g in _get_gpu_metrics():
        idx = g.get("index", 0)
        name = (g.get("name") or "gpu").replace(" ", "_")[:32]
        lines.append("# TYPE radioshaq_gpu_utilization_percent gauge")
        lines.append(f'radioshaq_gpu_utilization_percent{{gpu_index="{idx}",gpu_name="{name}"}} {g.get("utilization_gpu", 0)}')
        lines.append("# TYPE radioshaq_gpu_memory_used_mb gauge")
        lines.append(f'radioshaq_gpu_memory_used_mb{{gpu_index="{idx}",gpu_name="{name}"}} {g.get("memory_used_mb", 0)}')
        lines.append("# TYPE radioshaq_gpu_memory_total_mb gauge")
        lines.append(f'radioshaq_gpu_memory_total_mb{{gpu_index="{idx}",gpu_name="{name}"}} {g.get("memory_total_mb", 0)}')
    return "\n".join(lines) + "\n"


@metrics_router.get("", response_class=PlainTextResponse)
async def metrics(request: Request) -> PlainTextResponse:
    """
    Prometheus scrape endpoint. Exposes radioshaq_uptime_seconds, radioshaq_callsigns_registered_total,
    and optional GPU gauges (when nvidia-smi is available). Install prometheus-client for full metrics.
    """
    callsign_count = await _callsign_count(request)
    body = _render_prometheus_with_client(request, callsign_count)
    if body is None:
        body = _render_prometheus_fallback(callsign_count)
    return PlainTextResponse(
        content=body,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
