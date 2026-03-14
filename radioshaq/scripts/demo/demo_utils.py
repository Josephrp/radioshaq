"""Shared helpers for demo scripts: tokens, API wrappers, and expectation logging."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx

# Default timeouts for demo scripts
AUTH_TIMEOUT = 15.0
API_TIMEOUT = 30.0
UPLOAD_TIMEOUT = 120.0


def get_token(
    base_url: str,
    subject: str = "demo-op1",
    role: str = "field",
    station_id: str = "DEMO-01",
    timeout: float = AUTH_TIMEOUT,
) -> str:
    """Fetch a JWT from POST /auth/token. Raises on non-2xx."""
    url = f"{base_url.rstrip('/')}/auth/token"
    r = httpx.post(
        url,
        params={"subject": subject, "role": role, "station_id": station_id},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    """Return Authorization Bearer headers for requests."""
    return {"Authorization": f"Bearer {token}"}


def expect_status(
    response: httpx.Response,
    expected: int,
    context: str,
    *,
    on_fail: str = "stderr",
) -> bool:
    """
    Print success/failure for a response status. Return True if status matches.
    on_fail: 'stderr' to print to stderr, 'raise' to raise, 'quiet' to only return.
    """
    ok = response.status_code == expected
    if ok:
        print(f"[ok] {context}: HTTP {response.status_code}")
        return True
    out = f"[fail] {context}: expected HTTP {expected}, got {response.status_code}"
    if response.text:
        out += f" — {response.text[:200]}"
    if on_fail == "stderr":
        print(out, file=sys.stderr)
    elif on_fail == "raise":
        raise AssertionError(out)
    return False


def post_from_audio(
    base_url: str,
    token: str,
    file_path: Path | str,
    *,
    source_callsign: str = "K5ABC",
    destination_callsign: str | None = None,
    band: str = "40m",
    mode: str = "NFM",
    frequency_hz: float | str = 0,
    inject: bool = True,
    timeout: float = UPLOAD_TIMEOUT,
) -> httpx.Response:
    """POST /messages/from-audio with a WAV file."""
    url = f"{base_url.rstrip('/')}/messages/from-audio"
    path = Path(file_path)
    with path.open("rb") as f:
        files = {"file": (path.name, f, "audio/wav")}
        data = {
            "source_callsign": source_callsign,
            "destination_callsign": destination_callsign or "",
            "band": band,
            "mode": mode,
            "frequency_hz": str(frequency_hz),
            "inject": "true" if inject else "false",
        }
        return httpx.post(
            url,
            headers=auth_headers(token),
            files=files,
            data=data,
            timeout=timeout,
        )


def post_relay(
    base_url: str,
    token: str,
    message: str,
    *,
    source_band: str = "40m",
    target_band: str | None = "2m",
    source_callsign: str = "K5ABC",
    destination_callsign: str = "W1XYZ",
    target_channel: str = "radio",
    destination_phone: str | None = None,
    timeout: float = API_TIMEOUT,
) -> httpx.Response:
    """POST /messages/relay."""
    url = f"{base_url.rstrip('/')}/messages/relay"
    body: dict[str, Any] = {
        "message": message,
        "source_band": source_band,
        "target_band": target_band,
        "source_callsign": source_callsign,
        "destination_callsign": destination_callsign,
        "target_channel": target_channel,
    }
    if destination_phone is not None:
        body["destination_phone"] = destination_phone
    return httpx.post(url, headers=auth_headers(token), json=body, timeout=timeout)


def get_transcripts(
    base_url: str,
    token: str,
    *,
    limit: int = 20,
    band: str | None = None,
    callsign: str | None = None,
    destination_only: bool | None = None,
    timeout: float = API_TIMEOUT,
) -> httpx.Response:
    """GET /transcripts with optional filters."""
    url = f"{base_url.rstrip('/')}/transcripts"
    params: dict[str, Any] = {"limit": limit}
    if band is not None:
        params["band"] = band
    if callsign is not None:
        params["callsign"] = callsign
    if destination_only is not None:
        params["destination_only"] = "true" if destination_only else "false"
    return httpx.get(url, headers=auth_headers(token), params=params, timeout=timeout)


def post_send_audio(
    base_url: str,
    token: str,
    file_path: Path | str,
    *,
    frequency_hz: float = 145_520_000.0,
    mode: str = "NFM",
    timeout: float = UPLOAD_TIMEOUT,
) -> httpx.Response:
    """POST /radio/send-audio (multipart)."""
    url = f"{base_url.rstrip('/')}/radio/send-audio"
    path = Path(file_path)
    with path.open("rb") as f:
        files = {"file": (path.name, f, "audio/wav")}
        params = {"frequency_hz": str(frequency_hz), "mode": mode}
        return httpx.post(
            url,
            headers=auth_headers(token),
            files=files,
            params=params,
            timeout=timeout,
        )


def post_send_tts(
    base_url: str,
    token: str,
    message: str,
    *,
    frequency_hz: float | None = 145_520_000.0,
    mode: str | None = "NFM",
    timeout: float = UPLOAD_TIMEOUT,
) -> httpx.Response:
    """POST /radio/send-tts."""
    url = f"{base_url.rstrip('/')}/radio/send-tts"
    body: dict[str, Any] = {"message": message}
    if frequency_hz is not None:
        body["frequency_hz"] = frequency_hz
    if mode is not None:
        body["mode"] = mode
    return httpx.post(url, headers=auth_headers(token), json=body, timeout=timeout)


def post_inject_message(
    base_url: str,
    token: str,
    text: str,
    *,
    band: str | None = "40m",
    frequency_hz: float = 0.0,
    mode: str = "PSK31",
    source_callsign: str | None = None,
    destination_callsign: str | None = None,
    metadata: dict[str, Any] | None = None,
    timeout: float = API_TIMEOUT,
) -> httpx.Response:
    """POST /inject/message (inject into RX path)."""
    url = f"{base_url.rstrip('/')}/inject/message"
    body: dict[str, Any] = {
        "text": text,
        "band": band,
        "frequency_hz": frequency_hz,
        "mode": mode,
        "metadata": metadata or {},
    }
    if source_callsign is not None:
        body["source_callsign"] = source_callsign
    if destination_callsign is not None:
        body["destination_callsign"] = destination_callsign
    return httpx.post(url, headers=auth_headers(token), json=body, timeout=timeout)


def post_inject_and_store(
    base_url: str,
    token: str,
    text: str,
    *,
    band: str = "40m",
    mode: str = "PSK31",
    source_callsign: str = "K5ABC",
    destination_callsign: str | None = None,
    metadata: dict[str, Any] | None = None,
    timeout: float = API_TIMEOUT,
) -> httpx.Response:
    """POST /messages/inject-and-store."""
    url = f"{base_url.rstrip('/')}/messages/inject-and-store"
    body: dict[str, Any] = {
        "text": text,
        "band": band,
        "mode": mode,
        "source_callsign": source_callsign,
        "metadata": metadata or {},
    }
    if destination_callsign is not None:
        body["destination_callsign"] = destination_callsign
    return httpx.post(url, headers=auth_headers(token), json=body, timeout=timeout)


def post_callsign_register(
    base_url: str,
    token: str,
    callsign: str,
    source: str = "api",
    timeout: float = API_TIMEOUT,
) -> httpx.Response:
    """POST /callsigns/register."""
    url = f"{base_url.rstrip('/')}/callsigns/register"
    return httpx.post(
        url,
        headers=auth_headers(token),
        json={"callsign": callsign.strip().upper(), "source": source},
        timeout=timeout,
    )


def post_whitelist_request(
    base_url: str,
    token: str,
    text: str,
    *,
    callsign: str | None = None,
    timeout: float = API_TIMEOUT,
) -> httpx.Response:
    """POST /messages/whitelist-request (JSON body)."""
    url = f"{base_url.rstrip('/')}/messages/whitelist-request"
    body: dict[str, Any] = {"text": text}
    if callsign is not None:
        body["callsign"] = callsign
    return httpx.post(url, headers=auth_headers(token), json=body, timeout=timeout)


def post_process(
    base_url: str,
    token: str,
    message: str,
    *,
    channel: str | None = None,
    chat_id: str | None = None,
    sender_id: str | None = None,
    timeout: float = API_TIMEOUT,
) -> httpx.Response:
    """POST /messages/process (REACT orchestration)."""
    url = f"{base_url.rstrip('/')}/messages/process"
    body: dict[str, Any] = {"message": message, "text": message}
    if channel is not None:
        body["channel"] = channel
    if chat_id is not None:
        body["chat_id"] = chat_id
    if sender_id is not None:
        body["sender_id"] = sender_id
    return httpx.post(url, headers=auth_headers(token), json=body, timeout=timeout)


def get_health(base_url: str, timeout: float = 10.0) -> httpx.Response:
    """GET /health (no auth)."""
    return httpx.get(f"{base_url.rstrip('/')}/health", timeout=timeout)


def get_radio_bands(base_url: str, token: str, timeout: float = API_TIMEOUT) -> httpx.Response:
    """GET /radio/bands."""
    return httpx.get(
        f"{base_url.rstrip('/')}/radio/bands",
        headers=auth_headers(token),
        timeout=timeout,
    )


def get_radio_status(base_url: str, token: str, timeout: float = API_TIMEOUT) -> httpx.Response:
    """GET /radio/status."""
    return httpx.get(
        f"{base_url.rstrip('/')}/radio/status",
        headers=auth_headers(token),
        timeout=timeout,
    )


def get_audio_config(base_url: str, token: str, timeout: float = API_TIMEOUT) -> httpx.Response:
    """GET /api/v1/config/audio."""
    return httpx.get(
        f"{base_url.rstrip('/')}/api/v1/config/audio",
        headers=auth_headers(token),
        timeout=timeout,
    )


def get_audio_pending(base_url: str, token: str, timeout: float = API_TIMEOUT) -> httpx.Response:
    """GET /api/v1/audio/pending (list pending voice responses)."""
    return httpx.get(
        f"{base_url.rstrip('/')}/api/v1/audio/pending",
        headers=auth_headers(token),
        timeout=timeout,
    )


def get_receiver_tx_status(receiver_base_url: str, timeout: float = API_TIMEOUT) -> httpx.Response:
    """GET receiver /tx/status (HackRF TX broker availability). No auth required."""
    return httpx.get(
        f"{receiver_base_url.rstrip('/')}/tx/status",
        timeout=timeout,
    )


def check_hq_hackrf_tx_available(base_url: str, token: str, timeout: float = API_TIMEOUT) -> bool:
    """Return True if HQ reports SDR TX (HackRF) configured and available for live demos."""
    r = get_radio_status(base_url, token, timeout=timeout)
    if r.status_code != 200:
        return False
    try:
        data = r.json()
        return data.get("sdr_tx_available", False) is True
    except Exception:
        return False


def check_receiver_hackrf_available(receiver_base_url: str, timeout: float = API_TIMEOUT) -> bool:
    """Return True if receiver reports HackRF TX broker available (real device when SDR_TYPE=hackrf)."""
    r = get_receiver_tx_status(receiver_base_url, timeout=timeout)
    if r.status_code != 200:
        return False
    try:
        data = r.json()
        return data.get("available", False) is True
    except Exception:
        return False


# --- GIS (operator location, operators-nearby, propagation) ---


def post_gis_location(
    base_url: str,
    token: str,
    callsign: str,
    latitude: float,
    longitude: float,
    *,
    altitude_meters: float | None = None,
    accuracy_meters: float | None = None,
    timeout: float = API_TIMEOUT,
) -> httpx.Response:
    """POST /gis/location — store operator location (user_disclosed)."""
    url = f"{base_url.rstrip('/')}/gis/location"
    body: dict[str, Any] = {
        "callsign": callsign.strip().upper(),
        "latitude": latitude,
        "longitude": longitude,
    }
    if altitude_meters is not None:
        body["altitude_meters"] = altitude_meters
    if accuracy_meters is not None:
        body["accuracy_meters"] = accuracy_meters
    return httpx.post(url, headers=auth_headers(token), json=body, timeout=timeout)


def get_gis_location(
    base_url: str,
    token: str,
    callsign: str,
    timeout: float = API_TIMEOUT,
) -> httpx.Response:
    """GET /gis/location/{callsign} — latest stored location for a callsign."""
    url = f"{base_url.rstrip('/')}/gis/location/{callsign.strip().upper()}"
    return httpx.get(url, headers=auth_headers(token), timeout=timeout)


def get_gis_operators_nearby(
    base_url: str,
    token: str,
    latitude: float,
    longitude: float,
    *,
    radius_meters: float = 50000,
    recent_hours: int = 24,
    max_results: int = 100,
    timeout: float = API_TIMEOUT,
) -> httpx.Response:
    """GET /gis/operators-nearby — find operators within radius of a point."""
    url = f"{base_url.rstrip('/')}/gis/operators-nearby"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "radius_meters": radius_meters,
        "recent_hours": recent_hours,
        "max_results": max_results,
    }
    return httpx.get(url, headers=auth_headers(token), params=params, timeout=timeout)


def get_radio_propagation(
    base_url: str,
    token: str,
    lat_origin: float,
    lon_origin: float,
    lat_dest: float,
    lon_dest: float,
    timeout: float = API_TIMEOUT,
) -> httpx.Response:
    """GET /radio/propagation — distance and band suggestions between two points."""
    url = f"{base_url.rstrip('/')}/radio/propagation"
    params = {
        "lat_origin": lat_origin,
        "lon_origin": lon_origin,
        "lat_dest": lat_dest,
        "lon_dest": lon_dest,
    }
    return httpx.get(url, headers=auth_headers(token), params=params, timeout=timeout)
