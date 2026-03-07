"""FastAPI application with lifespan-managed resources."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from radioshaq import __version__
from radioshaq.config.schema import Config


def _web_ui_dir() -> Path | None:
    """Path to bundled web UI static files (when present in installed package)."""
    p = Path(__file__).resolve().parent.parent / "web_ui"
    return p if (p / "index.html").exists() else None


def _is_bus_consumer_enabled(config: Config) -> bool:
    """True if MessageBus inbound consumer should run (config or RADIOSHAQ_BUS_CONSUMER_ENABLED)."""
    import os
    if getattr(config, "bus_consumer_enabled", None) is True:
        return True
    return os.environ.get("RADIOSHAQ_BUS_CONSUMER_ENABLED", "").strip().lower() in ("1", "true", "yes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create and tear down shared resources."""
    from zoneinfo import ZoneInfo

    config = Config()
    app.state.config = config
    app.state.db = None
    app.state.callsign_repository = None
    app.state.orchestrator = None
    app.state.agent_registry = None
    app.state.memory_manager = None
    _cron_stop_event = None
    _cron_task = None

    try:
        if config.database.postgres_url:
            try:
                from radioshaq.database.postgres_gis import PostGISManager
                app.state.db = PostGISManager(config.database.postgres_url)
            except Exception:
                pass
        from radioshaq.callsign import get_callsign_repository
        app.state.callsign_repository = get_callsign_repository(getattr(app.state, "db", None))

        # Memory manager and daily summary cron (when memory enabled)
        memory_cfg = getattr(config, "memory", None)
        if memory_cfg and getattr(memory_cfg, "enabled", False) and config.database.postgres_url:
            try:
                from radioshaq.memory import MemoryManager
                from radioshaq.memory.daily_summary_cron import run_midnight_cron_loop
                app.state.memory_manager = MemoryManager(config.database.postgres_url)
                tz_str = getattr(memory_cfg, "summary_timezone", "America/New_York")
                _cron_stop_event = asyncio.Event()
                _cron_task = asyncio.create_task(
                    run_midnight_cron_loop(
                        app.state.memory_manager,
                        config,
                        timezone=ZoneInfo(tz_str),
                        stop_event=_cron_stop_event,
                    )
                )
            except Exception as e:
                from loguru import logger
                logger.warning("Memory manager or cron not started: %s", e)

        from radioshaq.orchestrator.factory import create_orchestrator, create_tool_registry
        from radioshaq.vendor.nanobot.bus.queue import MessageBus
        from loguru import logger
        _bus_consumer_enabled = _is_bus_consumer_enabled(config)
        app.state.message_bus = MessageBus(max_size=1000, inbound_timeout=10.0 if _bus_consumer_enabled else None)
        app.state.tool_registry = None
        try:
            app.state.tool_registry = create_tool_registry(config, db=getattr(app.state, "db", None), app=app)
        except Exception as e:
            logger.warning("Tool registry not created: %s", e)
        try:
            app.state.orchestrator = create_orchestrator(
                config,
                db=getattr(app.state, "db", None),
                message_bus=app.state.message_bus,
                memory_manager=getattr(app.state, "memory_manager", None),
                max_iterations=20,
                tool_registry=getattr(app.state, "tool_registry", None),
            )
            app.state.agent_registry = getattr(app.state.orchestrator, "agent_registry", None)
            rx_audio = app.state.agent_registry.get_agent("radio_rx_audio") if app.state.agent_registry else None
            if rx_audio and hasattr(rx_audio, "set_metrics_callback"):
                rx_audio.set_metrics_callback(lambda d: setattr(app.state, "audio_metrics_latest", d))
        except Exception as e:
            logger.warning("Orchestrator not created (messages/process will be unavailable): %s", e)

        # Optional: run MessageBus inbound consumer and outbound radio handler (set RADIOSHAQ_BUS_CONSUMER_ENABLED=1)
        _consumer_task = None
        _outbound_radio_task = None
        _outbound_radio_stop = None
        if _bus_consumer_enabled:
            if getattr(app.state, "orchestrator", None) and getattr(app.state, "message_bus", None):
                from radioshaq.orchestrator.bridge import run_inbound_consumer
                from radioshaq.orchestrator.outbound_radio import run_outbound_radio_handler
                _stop_event = asyncio.Event()
                _consumer_task = asyncio.create_task(
                    run_inbound_consumer(
                        app.state.message_bus,
                        app.state.orchestrator,
                        stop_event=_stop_event,
                        callsign_repository=getattr(app.state, "callsign_repository", None),
                    )
                )
                app.state._bus_consumer_stop = _stop_event
                app.state._bus_consumer_task = _consumer_task
                logger.info("MessageBus inbound consumer started")
                radio_tx = app.state.agent_registry.get_agent("radio_tx") if getattr(app.state, "agent_registry", None) else None
                _outbound_radio_stop = asyncio.Event()
                _outbound_radio_task = asyncio.create_task(
                    run_outbound_radio_handler(
                        app.state.message_bus,
                        radio_tx,
                        config,
                        stop_event=_outbound_radio_stop,
                    )
                )
                app.state._outbound_radio_stop = _outbound_radio_stop
                app.state._outbound_radio_task = _outbound_radio_task
                logger.info("Outbound radio handler started")

        # Optional: multi-band listener (listen_bands or default_band + listener_enabled)
        _listener_task = None
        _listener_stop = None
        _relay_delivery_task = None
        _relay_delivery_stop = None
        radio_cfg = getattr(config, "radio", None)
        if radio_cfg and getattr(radio_cfg, "listener_enabled", False):
            bands = (getattr(radio_cfg, "listen_bands", None) or []) or (
                [radio_cfg.default_band] if getattr(radio_cfg, "default_band", None) else []
            )
            if bands and getattr(app.state, "agent_registry", None):
                radio_rx = app.state.agent_registry.get_agent("radio_rx")
                if radio_rx:
                    from radioshaq.database.transcripts import TranscriptStorage
                    from radioshaq.listener.band_listener import run_band_listener
                    _listener_stop = asyncio.Event()
                    storage = TranscriptStorage(db=app.state.db) if app.state.db else None
                    _listener_task = asyncio.create_task(
                        run_band_listener(
                            config,
                            storage,
                            app.state.message_bus,
                            radio_rx,
                            stop_event=_listener_stop,
                            inject_into_queue=True,
                            publish_to_bus=not getattr(radio_cfg, "listener_skip_bus", False),
                        )
                    )
                    app.state._band_listener_stop = _listener_stop
                    app.state._band_listener_task = _listener_task
                    logger.info("Band listener started for bands: %s", bands)

        # Optional: voice listener (audio_input_enabled + voice_listener_enabled)
        _voice_listener_task = None
        _voice_listener_stop = None
        if radio_cfg and getattr(radio_cfg, "audio_input_enabled", False):
            voice_listener_on = getattr(radio_cfg, "voice_listener_enabled", True) or getattr(
                radio_cfg, "audio_monitoring_enabled", False
            )
            if voice_listener_on and getattr(app.state, "agent_registry", None):
                rx_audio = app.state.agent_registry.get_agent("radio_rx_audio")
                if rx_audio and getattr(app.state, "message_bus", None):
                    from radioshaq.listener.voice_listener import run_voice_listener
                    _voice_listener_stop = asyncio.Event()
                    cycle = getattr(radio_cfg, "voice_listener_cycle_seconds", 3600.0) or 3600.0
                    _voice_listener_task = asyncio.create_task(
                        run_voice_listener(
                            config,
                            app.state.message_bus,
                            rx_audio,
                            stop_event=_voice_listener_stop,
                            cycle_seconds=cycle,
                        )
                    )
                    app.state._voice_listener_stop = _voice_listener_stop
                    app.state._voice_listener_task = _voice_listener_task
                    logger.info("Voice listener started")

        # Optional: relay scheduled delivery worker
        _relay_delivery_task = None
        _relay_delivery_stop = None
        if radio_cfg and getattr(radio_cfg, "relay_scheduled_delivery_enabled", False) and app.state.db:
            if hasattr(app.state.db, "search_pending_relay_deliveries"):
                from radioshaq.listener.relay_delivery import run_relay_delivery_worker
                _relay_delivery_stop = asyncio.Event()
                radio_tx = app.state.agent_registry.get_agent("radio_tx") if getattr(app.state, "agent_registry", None) else None
                _relay_delivery_task = asyncio.create_task(
                    run_relay_delivery_worker(
                        app.state.db,
                        config,
                        stop_event=_relay_delivery_stop,
                        interval_seconds=60.0,
                        radio_tx_agent=radio_tx,
                    )
                )
                app.state._relay_delivery_stop = _relay_delivery_stop
                app.state._relay_delivery_task = _relay_delivery_task
                logger.info("Relay delivery worker started")

        yield
        if _voice_listener_stop is not None:
            _voice_listener_stop.set()
        if _voice_listener_task is not None and not _voice_listener_task.done():
            _voice_listener_task.cancel()
            try:
                await _voice_listener_task
            except asyncio.CancelledError:
                pass
        if _relay_delivery_stop is not None:
            _relay_delivery_stop.set()
        if _relay_delivery_task is not None and not _relay_delivery_task.done():
            _relay_delivery_task.cancel()
            try:
                await _relay_delivery_task
            except asyncio.CancelledError:
                pass
        if _listener_stop is not None:
            _listener_stop.set()
        if _listener_task is not None and not _listener_task.done():
            _listener_task.cancel()
            try:
                await _listener_task
            except asyncio.CancelledError:
                pass
        if _outbound_radio_stop is not None:
            _outbound_radio_stop.set()
        if _outbound_radio_task is not None and not _outbound_radio_task.done():
            _outbound_radio_task.cancel()
            try:
                await _outbound_radio_task
            except asyncio.CancelledError:
                pass
        if _consumer_task is not None and not _consumer_task.done():
            if getattr(app.state, "_bus_consumer_stop", None):
                app.state._bus_consumer_stop.set()
            _consumer_task.cancel()
            try:
                await _consumer_task
            except asyncio.CancelledError:
                pass
        if _cron_stop_event is not None:
            _cron_stop_event.set()
        if _cron_task is not None and not _cron_task.done():
            _cron_task.cancel()
            try:
                await _cron_task
            except asyncio.CancelledError:
                pass
        if getattr(app.state, "memory_manager", None) and hasattr(app.state.memory_manager, "close"):
            await app.state.memory_manager.close()
    finally:
        if getattr(app.state, "db", None) and hasattr(app.state.db, "close"):
            await app.state.db.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="RadioShaq API",
        description="Strategic Autonomous Ham Radio and Knowledge Operations Dispatch System",
        version=__version__,
        lifespan=lifespan,
    )

    from radioshaq.api.routes import auth, audio, bus, callsigns, config_routes, gis, health, inject, memory, messages, metrics, radio, receiver, relay, transcripts
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(metrics.metrics_router, prefix="/metrics", tags=["metrics"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(radio.router, prefix="/radio", tags=["radio"])
    app.include_router(gis.router, prefix="/gis", tags=["gis"])
    app.include_router(memory.router, prefix="/memory", tags=["memory"])
    app.include_router(messages.router, prefix="/messages", tags=["messages"])
    app.include_router(relay.router, prefix="/messages", tags=["messages"])
    app.include_router(transcripts.router, prefix="/transcripts", tags=["transcripts"])
    app.include_router(callsigns.router, prefix="/callsigns", tags=["callsigns"])
    app.include_router(inject.router, prefix="/inject", tags=["inject"])
    app.include_router(receiver.router, prefix="/receiver", tags=["receiver"])
    app.include_router(bus.router, prefix="/internal", tags=["internal"])
    app.include_router(audio.router, prefix="/api/v1")
    app.include_router(config_routes.router, prefix="/api/v1")
    app.include_router(audio.ws_router, prefix="/ws")

    # Serve bundled web UI at / when present (e.g. from PyPI wheel). API routes above take precedence.
    web_ui = _web_ui_dir()
    if web_ui is not None:
        app.mount("/", StaticFiles(directory=str(web_ui), html=True), name="web_ui")
        if app.router.routes[-1].name != "web_ui":
            raise RuntimeError(
                "web_ui mount must remain the final route. Register all API routes before mounting static files at /."
            )

    return app


app = create_app()

if __name__ == "__main__":
    import os
    import uvicorn
    from radioshaq.config.schema import Config
    config = Config()
    host = os.environ.get("API_HOST", os.environ.get("RADIOSHAQ_API_HOST", config.hq.host))
    port = int(os.environ.get("API_PORT", os.environ.get("RADIOSHAQ_API_PORT", str(config.hq.port))))
    uvicorn.run(
        "radioshaq.api.server:app",
        host=host,
        port=port,
        reload=os.environ.get("RELOAD", "false").lower() in ("1", "true", "yes"),
    )
