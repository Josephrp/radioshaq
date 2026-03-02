"""FastAPI application with lifespan-managed resources."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from shakods.config.schema import Config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create and tear down shared resources."""
    config = Config()
    app.state.config = config
    app.state.db = None
    app.state.orchestrator = None

    try:
        if config.database.postgres_url and "localhost" in config.database.postgres_url:
            try:
                from shakods.database.postgres_gis import PostGISManager
                app.state.db = PostGISManager(config.database.postgres_url)
            except Exception:
                pass
        yield
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

    from shakods.api.routes import auth, health, inject, messages, radio, relay, transcripts
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(radio.router, prefix="/radio", tags=["radio"])
    app.include_router(messages.router, prefix="/messages", tags=["messages"])
    app.include_router(relay.router, prefix="/messages", tags=["messages"])
    app.include_router(transcripts.router, prefix="/transcripts", tags=["transcripts"])
    app.include_router(inject.router, prefix="/inject", tags=["inject"])

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
