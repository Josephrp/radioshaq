"""Audio configuration, devices, confirmation queue, and metrics WebSocket."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect

from radioshaq.api.dependencies import get_audio_agent, get_config, get_current_user
from radioshaq.auth.jwt import TokenPayload
from radioshaq.config.schema import AudioConfig, Config

router = APIRouter(prefix="", tags=["audio"])
ws_router = APIRouter(prefix="", tags=["audio-ws"])


def _audio_config_dict(config: AudioConfig) -> dict[str, Any]:
    """Serialize AudioConfig to JSON-serializable dict."""
    return config.model_dump(mode="json")


@router.get("/config/audio")
async def get_audio_config(
    request: Request,
    config: Config = Depends(get_config),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Get current audio configuration (env/file + optional runtime overrides)."""
    audio = getattr(config, "audio", None)
    if not audio:
        raise HTTPException(status_code=503, detail="Audio config not available")
    out = _audio_config_dict(audio)
    override = getattr(request.app.state, "audio_config_override", None)
    if override:
        out = {**out, **override}
    return out


@router.patch("/config/audio")
async def update_audio_config(
    request: Request,
    body: dict[str, Any],
    config: Config = Depends(get_config),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Update audio configuration (runtime overlay only; does not persist to file)."""
    audio = getattr(config, "audio", None)
    if not audio:
        raise HTTPException(status_code=503, detail="Audio config not available")
    if not hasattr(request.app.state, "audio_config_override"):
        request.app.state.audio_config_override = {}
    request.app.state.audio_config_override.update(body)
    base = _audio_config_dict(audio)
    return {**base, **request.app.state.audio_config_override}


@router.post("/config/audio/reset")
async def reset_audio_config(
    request: Request,
    config: Config = Depends(get_config),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Clear runtime audio config overrides."""
    if hasattr(request.app.state, "audio_config_override"):
        request.app.state.audio_config_override = {}
    audio = getattr(config, "audio", None)
    if not audio:
        raise HTTPException(status_code=503, detail="Audio config not available")
    return _audio_config_dict(audio)


@router.get("/audio/devices")
async def list_audio_devices(
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """List available audio input/output devices (requires voice_rx)."""
    try:
        import sounddevice as sd
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="sounddevice not available. Install with: uv sync --extra voice_rx",
        )
    try:
        devices = sd.query_devices()
        if not isinstance(devices, (list, tuple)):
            devices = [devices] if devices is not None else []
        input_devices = []
        output_devices = []
        for i, d in enumerate(devices):
            if not isinstance(d, dict):
                continue
            max_in = d.get("max_input_channels")
            max_out = d.get("max_output_channels")
            if max_in is not None and int(max_in) > 0:
                input_devices.append({
                    "index": i,
                    "name": str(d.get("name", "?")),
                    "channels": int(max_in),
                    "sample_rate": float(d["default_samplerate"]) if d.get("default_samplerate") is not None else None,
                })
            if max_out is not None and int(max_out) > 0:
                output_devices.append({
                    "index": i,
                    "name": str(d.get("name", "?")),
                    "channels": int(max_out),
                    "sample_rate": float(d["default_samplerate"]) if d.get("default_samplerate") is not None else None,
                })
        return {"input_devices": input_devices, "output_devices": output_devices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audio/devices/{device_id:int}/test")
async def test_audio_device(
    device_id: int,
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Test an audio device by ID (placeholder)."""
    try:
        import sounddevice as sd
        sd.query_devices(device_id)
    except ImportError:
        raise HTTPException(status_code=503, detail="sounddevice not available")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "message": f"Device {device_id} exists", "device_id": device_id}


@router.get("/audio/pending")
async def list_pending_responses(
    audio_agent: Any = Depends(get_audio_agent),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """List pending responses awaiting human confirmation."""
    if not audio_agent:
        raise HTTPException(status_code=503, detail="Audio reception agent not available")
    result = await audio_agent.execute({"action": "list_pending"})
    return result


@router.post("/audio/pending/{pending_id}/approve")
async def approve_pending_response(
    pending_id: str,
    body: dict[str, Any] = Body(default={}),
    audio_agent: Any = Depends(get_audio_agent),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Approve a pending response (send it over the radio)."""
    if not audio_agent:
        raise HTTPException(status_code=503, detail="Audio reception agent not available")
    result = await audio_agent.execute({
        "action": "approve_response",
        "pending_id": pending_id,
        "operator": body.get("operator", _user.sub if hasattr(_user, "sub") else None),
    })
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/audio/pending/{pending_id}/reject")
async def reject_pending_response(
    pending_id: str,
    body: dict[str, Any] = Body(default={}),
    audio_agent: Any = Depends(get_audio_agent),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Reject a pending response."""
    if not audio_agent:
        raise HTTPException(status_code=503, detail="Audio reception agent not available")
    result = await audio_agent.execute({
        "action": "reject_response",
        "pending_id": pending_id,
        "operator": body.get("operator"),
        "notes": body.get("notes"),
    })
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@ws_router.websocket("/audio/metrics/{session_id}")
async def websocket_audio_metrics(websocket: WebSocket, session_id: str) -> None:
    """WebSocket for real-time audio metrics (VAD, SNR, state). Placeholder: sends heartbeat."""
    await websocket.accept()
    import asyncio
    try:
        while True:
            await websocket.send_json({
                "session_id": session_id,
                "type": "heartbeat",
                "vad_active": False,
                "snr_db": None,
                "state": "idle",
            })
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
