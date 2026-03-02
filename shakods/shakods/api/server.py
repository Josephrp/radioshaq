"""FastAPI application with lifespan-managed resources."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from shakods.config.schema import Config


def _is_bus_consumer_enabled(config: Config) -> bool:
    """True if MessageBus inbound consumer should run (config or SHAKODS_BUS_CONSUMER_ENABLED)."""
    import os
    if getattr(config, "bus_consumer_enabled", None) is True:
        return True
    return os.environ.get("SHAKODS_BUS_CONSUMER_ENABLED", "").strip().lower() in ("1", "true", "yes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create and tear down shared resources."""
    config = Config()
    app.state.config = config
    app.state.db = None
    app.state.orchestrator = None
    app.state.agent_registry = None

    try:
        if config.database.postgres_url and "localhost" in config.database.postgres_url:
            try:
                from shakods.database.postgres_gis import PostGISManager
                app.state.db = PostGISManager(config.database.postgres_url)
            except Exception:
                pass

        from shakods.orchestrator.factory import create_orchestrator, create_tool_registry
        from shakods.vendor.nanobot.bus.queue import MessageBus
        from loguru import logger
        _bus_consumer_enabled = _is_bus_consumer_enabled(config)
        app.state.message_bus = MessageBus(max_size=1000, inbound_timeout=10.0 if _bus_consumer_enabled else None)
        app.state.tool_registry = None
        try:
            app.state.tool_registry = create_tool_registry(config, db=getattr(app.state, "db", None))
        except Exception as e:
            logger.warning("Tool registry not created: %s", e)
        try:
            app.state.orchestrator = create_orchestrator(
                config,
                db=getattr(app.state, "db", None),
                message_bus=app.state.message_bus,
                max_iterations=20,
            )
            app.state.agent_registry = getattr(app.state.orchestrator, "agent_registry", None)
        except Exception as e:
            logger.warning("Orchestrator not created (messages/process will be unavailable): %s", e)

        # Optional: run MessageBus inbound consumer in background (set SHAKODS_BUS_CONSUMER_ENABLED=1)
        _consumer_task = None
        if _bus_consumer_enabled:
            if getattr(app.state, "orchestrator", None) and getattr(app.state, "message_bus", None):
                from shakods.orchestrator.bridge import run_inbound_consumer
                _stop_event = asyncio.Event()
                _consumer_task = asyncio.create_task(run_inbound_consumer(app.state.message_bus, app.state.orchestrator, stop_event=_stop_event))
                app.state._bus_consumer_stop = _stop_event
                app.state._bus_consumer_task = _consumer_task
                logger.info("MessageBus inbound consumer started")

        yield
        if _consumer_task is not None and not _consumer_task.done():
            if getattr(app.state, "_bus_consumer_stop", None):
                app.state._bus_consumer_stop.set()
            _consumer_task.cancel()
            try:
                await _consumer_task
            except asyncio.CancelledError:
                pass
    finally:
        if getattr(app.state, "db", None) and hasattr(app.state.db, "close"):
            await app.state.db.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="SHAKODS API",
        description="Strategic Autonomous Ham Radio and Knowledge Operations Dispatch System",
        version="0.1.0",
        lifespan=lifespan,
    )

    from shakods.api.routes import auth, bus, health, inject, messages, radio, relay, transcripts
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(radio.router, prefix="/radio", tags=["radio"])
    app.include_router(messages.router, prefix="/messages", tags=["messages"])
    app.include_router(relay.router, prefix="/messages", tags=["messages"])
    app.include_router(transcripts.router, prefix="/transcripts", tags=["transcripts"])
    app.include_router(inject.router, prefix="/inject", tags=["inject"])
    app.include_router(bus.router, prefix="/internal", tags=["internal"])

    return app


app = create_app()

if __name__ == "__main__":
    import os
    import uvicorn
    from shakods.config.schema import Config
    config = Config()
    host = os.environ.get("API_HOST", os.environ.get("SHAKODS_API_HOST", config.hq.host))
    port = int(os.environ.get("API_PORT", os.environ.get("SHAKODS_API_PORT", str(config.hq.port))))
    uvicorn.run(
        "shakods.api.server:app",
        host=host,
        port=port,
        reload=os.environ.get("RELOAD", "false").lower() in ("1", "true", "yes"),
    )
