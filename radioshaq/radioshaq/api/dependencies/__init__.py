"""FastAPI dependencies: auth, db, orchestrator."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from radioshaq.auth.jwt import JWTAuthManager, TokenPayload
from radioshaq.config.schema import Config

_security = HTTPBearer(auto_error=False)


def get_config(request: Request) -> Config:
    """Return app config from state."""
    return request.app.state.config


def get_auth_manager(config: Annotated[Config, Depends(get_config)]) -> JWTAuthManager:
    """Return JWT auth manager from config."""
    return JWTAuthManager(config=config.jwt)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_security)],
    auth_manager: JWTAuthManager = Depends(get_auth_manager),
) -> TokenPayload:
    """Verify Bearer token and return payload. Raises 401 if missing/invalid."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    try:
        return auth_manager.verify_token(credentials.credentials)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


def get_db(request: Request) -> Any:
    """Return PostGIS manager if available, else None."""
    return getattr(request.app.state, "db", None)


def get_transcript_storage(request: Request) -> Any:
    """Return TranscriptStorage if DB is available, else None."""
    db = getattr(request.app.state, "db", None)
    if db is None or not hasattr(db, "store_transcript"):
        return None
    from radioshaq.database.transcripts import TranscriptStorage
    return TranscriptStorage(db=db)


def get_orchestrator(request: Request) -> Any:
    """Return REACT orchestrator if available, else None."""
    return getattr(request.app.state, "orchestrator", None)


def get_agent_registry(request: Request) -> Any:
    """Return agent registry if available, else None."""
    return getattr(request.app.state, "agent_registry", None)


def get_audio_agent(request: Request) -> Any:
    """Return RadioAudioReceptionAgent if registered, else None."""
    registry = get_agent_registry(request)
    if not registry:
        return None
    return registry.get_agent("radio_rx_audio")


def get_radio_tx_agent(request: Request) -> Any:
    """Return radio_tx agent if registered, else None."""
    registry = get_agent_registry(request)
    if not registry:
        return None
    return registry.get_agent("radio_tx")


__all__ = [
    "get_agent_registry",
    "get_audio_agent",
    "get_config",
    "get_current_user",
    "get_db",
    "get_orchestrator",
    "get_radio_tx_agent",
    "get_transcript_storage",
]
