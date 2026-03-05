"""RadioShaq CLI: full server communication (auth, health, callsigns, messages, transcripts, radio)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import typer
import httpx

from radioshaq.license_acceptance import ensure_license_accepted

app = typer.Typer(
    name="radioshaq",
    help="RadioShaq CLI: auth, health, callsigns, messages, transcripts, radio, run API server.",
    no_args_is_help=True,
)


def _base_url() -> str:
    return os.environ.get("RADIOSHAQ_API", "http://localhost:8000").rstrip("/")


def _token() -> Optional[str]:
    return os.environ.get("RADIOSHAQ_TOKEN", "").strip() or None


def _headers() -> dict[str, str]:
    h: dict[str, str] = {"Content-Type": "application/json"}
    t = _token()
    if t:
        h["Authorization"] = f"Bearer {t}"
    return h


def _require_token() -> None:
    if not _token():
        typer.echo("Set RADIOSHAQ_TOKEN or run: radioshaq token ...", err=True)
        raise typer.Exit(1)


def _api_get(path: str, base_url: Optional[str] = None, params: Optional[dict] = None) -> dict:
    url = (base_url or _base_url()).rstrip("/")
    r = httpx.get(f"{url}{path}", headers=_headers(), timeout=30.0, params=params or {})
    if r.status_code == 401:
        typer.echo("Unauthorized. Get a token with: radioshaq token", err=True)
        raise typer.Exit(1)
    if r.status_code >= 400:
        typer.echo(r.text, err=True)
        raise typer.Exit(1)
    return r.json()


def _api_post(
    path: str,
    json: Optional[dict] = None,
    base_url: Optional[str] = None,
    files: Optional[dict] = None,
    data: Optional[dict] = None,
) -> dict:
    url = (base_url or _base_url()).rstrip("/")
    kwargs: dict = {"timeout": 60.0}
    if files or data:
        kwargs["headers"] = {"Authorization": f"Bearer {_token()}"} if _token() else {}
        if files:
            kwargs["files"] = files
        if data:
            kwargs["data"] = data
    else:
        kwargs["headers"] = _headers()
        if json is not None:
            kwargs["json"] = json
    r = httpx.post(f"{url}{path}", **kwargs)
    if r.status_code == 401:
        typer.echo("Unauthorized. Get a token with: radioshaq token", err=True)
        raise typer.Exit(1)
    if r.status_code >= 400:
        typer.echo(r.text, err=True)
        raise typer.Exit(1)
    return r.json()


def _api_delete(path: str, base_url: Optional[str] = None) -> dict:
    url = (base_url or _base_url()).rstrip("/")
    r = httpx.delete(f"{url}{path}", headers=_headers(), timeout=30.0)
    if r.status_code == 401:
        typer.echo("Unauthorized. Get a token with: radioshaq token", err=True)
        raise typer.Exit(1)
    if r.status_code >= 400:
        typer.echo(r.text, err=True)
        raise typer.Exit(1)
    return r.json() if r.content else {}


# -----------------------------------------------------------------------------
# Top-level: health, token, run-api
# -----------------------------------------------------------------------------


@app.command()
def health(
    base_url: str = typer.Option(None, "--base-url", "-b", help="API base URL"),
    ready: bool = typer.Option(False, "--ready", "-r", help="Hit /health/ready instead of /health"),
) -> None:
    """Check API liveness or readiness."""
    url = (base_url or _base_url()).rstrip("/")
    path = "/health/ready" if ready else "/health"
    try:
        r = httpx.get(f"{url}{path}", timeout=10.0)
        typer.echo(r.json())
        raise typer.Exit(0 if r.status_code == 200 else 1)
    except httpx.HTTPError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def token(
    subject: str = typer.Option("cli", "--subject", "-s", help="Token subject"),
    role: str = typer.Option("field", "--role", "-r", help="Role (field, hq, receiver)"),
    station_id: Optional[str] = typer.Option(None, "--station-id", help="Station ID"),
    base_url: str = typer.Option(None, "--base-url", "-b", help="API base URL"),
) -> None:
    """Get a JWT from POST /auth/token and print access_token."""
    url = (base_url or _base_url()).rstrip("/")
    params: dict[str, str] = {"subject": subject, "role": role}
    if station_id:
        params["station_id"] = station_id
    try:
        r = httpx.post(f"{url}/auth/token", params=params, timeout=10.0)
        if r.status_code != 200:
            typer.echo(r.text, err=True)
            raise typer.Exit(1)
        data = r.json()
        typer.echo(data.get("access_token", ""))
    except httpx.HTTPError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def run_api(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Bind host"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Enable uvicorn reload"),
) -> None:
    """Run the FastAPI server (uvicorn)."""
    import uvicorn
    os.environ.setdefault("API_HOST", host)
    os.environ.setdefault("API_PORT", str(port))
    if reload:
        os.environ.setdefault("RELOAD", "true")
    uvicorn.run(
        "radioshaq.api.server:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def run_receiver(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Bind host"),
    port: int = typer.Option(8765, "--port", "-p", help="Bind port"),
) -> None:
    """Run the remote receiver service (SDR, JWT auth, HQ upload). Set JWT_SECRET, STATION_ID, HQ_URL."""
    from radioshaq.remote_receiver.server import main
    os.environ.setdefault("RECEIVER_HOST", host)
    os.environ.setdefault("RECEIVER_PORT", str(port))
    main()


# -----------------------------------------------------------------------------
# Callsigns group
# -----------------------------------------------------------------------------

callsigns_app = typer.Typer(help="Registered callsigns (whitelist): list, add, remove, register-from-audio.")
app.add_typer(callsigns_app, name="callsigns")


@callsigns_app.command("list")
def callsigns_list(
    base_url: Optional[str] = typer.Option(None, "--base-url", "-b"),
) -> None:
    """List all registered callsigns."""
    _require_token()
    data = _api_get("/callsigns", base_url=base_url)
    registered = data.get("registered", [])
    count = data.get("count", len(registered))
    typer.echo(f"Registered callsigns: {count}")
    for c in registered:
        if isinstance(c, dict):
            typer.echo(f"  - {c.get('callsign', c)}")
        else:
            typer.echo(f"  - {c}")


@callsigns_app.command("add")
def callsigns_add(
    callsign: str = typer.Argument(..., help="Callsign to register (e.g. K5ABC or W1XYZ-1)"),
    source: str = typer.Option("api", "--source", "-s", help="Source: api or audio"),
    base_url: Optional[str] = typer.Option(None, "--base-url", "-b"),
) -> None:
    """Register a callsign (POST /callsigns/register)."""
    _require_token()
    data = _api_post("/callsigns/register", json={"callsign": callsign.strip().upper(), "source": source}, base_url=base_url)
    typer.echo(f"Registered: {data.get('callsign', callsign)} (id={data.get('id', '')})")


@callsigns_app.command("remove")
def callsigns_remove(
    callsign: str = typer.Argument(..., help="Callsign to remove"),
    base_url: Optional[str] = typer.Option(None, "--base-url", "-b"),
) -> None:
    """Remove a callsign from the registry (DELETE /callsigns/registered/{callsign})."""
    _require_token()
    normalized = callsign.strip().upper()
    _api_delete(f"/callsigns/registered/{normalized}", base_url=base_url)
    typer.echo(f"Removed: {normalized}")


@callsigns_app.command("register-from-audio")
def callsigns_register_from_audio(
    file_path: Path = typer.Argument(..., help="Path to audio file (WAV etc.)"),
    callsign: Optional[str] = typer.Option(None, "--callsign", "-c", help="Override callsign (else extracted from ASR)"),
    base_url: Optional[str] = typer.Option(None, "--base-url", "-b"),
) -> None:
    """Upload audio; ASR extracts or confirm callsign and register (POST /callsigns/register-from-audio)."""
    _require_token()
    if not file_path.exists():
        typer.echo(f"File not found: {file_path}", err=True)
        raise typer.Exit(1)
    url = (base_url or _base_url()).rstrip("/")
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "audio/wav")}
        params = {} if not callsign else {"callsign": callsign.strip().upper()}
        r = httpx.post(
            f"{url}/callsigns/register-from-audio",
            headers={"Authorization": f"Bearer {_token()}"},
            files=files,
            params=params,
            timeout=60.0,
        )
    if r.status_code >= 400:
        typer.echo(r.text, err=True)
        raise typer.Exit(1)
    data = r.json()
    typer.echo(f"Registered: {data.get('callsign', '')} (id={data.get('id', '')})")
    if data.get("transcript"):
        typer.echo(f"Transcript: {data['transcript'][:200]}...")


# -----------------------------------------------------------------------------
# Message group
# -----------------------------------------------------------------------------

message_app = typer.Typer(help="Messages: process (REACT), inject, whitelist-request, relay.")
app.add_typer(message_app, name="message")


@message_app.command("process")
def message_process(
    text: str = typer.Argument(..., help="Message text for REACT orchestration"),
    base_url: Optional[str] = typer.Option(None, "--base-url", "-b"),
) -> None:
    """Submit message for REACT orchestration (POST /messages/process)."""
    _require_token()
    data = _api_post("/messages/process", json={"message": text}, base_url=base_url)
    typer.echo(f"Success: {data.get('success')}")
    typer.echo(f"Message: {data.get('message', '')}")
    if data.get("task_id"):
        typer.echo(f"Task ID: {data['task_id']}")


@message_app.command("inject")
def message_inject(
    text: str = typer.Argument(..., help="Message text to inject into RX path"),
    band: Optional[str] = typer.Option(None, "--band", "-b", help="Band (e.g. 40m, 2m)"),
    mode: str = typer.Option("PSK31", "--mode", "-m"),
    source_callsign: Optional[str] = typer.Option(None, "--source-callsign"),
    destination_callsign: Optional[str] = typer.Option(None, "--destination-callsign"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
) -> None:
    """Inject a message into the RX path for demo (POST /inject/message)."""
    _require_token()
    body: dict = {"text": text, "mode": mode}
    if band:
        body["band"] = band
    if source_callsign:
        body["source_callsign"] = source_callsign
    if destination_callsign:
        body["destination_callsign"] = destination_callsign
    data = _api_post("/inject/message", json=body, base_url=base_url)
    typer.echo(f"Injected. Queue size: {data.get('qsize', '')}")


@message_app.command("whitelist-request")
def message_whitelist_request(
    text: str = typer.Argument(..., help="Request text (or use --file for audio)"),
    callsign: Optional[str] = typer.Option(None, "--callsign", "-c"),
    send_audio_back: bool = typer.Option(True, "--audio/--no-audio"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
) -> None:
    """Whitelist request: text or audio → orchestrator (POST /messages/whitelist-request)."""
    _require_token()
    body: dict = {"text": text, "send_audio_back": send_audio_back}
    if callsign:
        body["callsign"] = callsign
    data = _api_post("/messages/whitelist-request", json=body, base_url=base_url)
    typer.echo(f"Success: {data.get('success')}")
    typer.echo(f"Message: {data.get('message', '')}")
    if data.get("approved") is not None:
        typer.echo(f"Approved: {data['approved']}")


@message_app.command("relay")
def message_relay(
    message: str = typer.Argument(..., help="Message text to relay"),
    source_band: str = typer.Option(..., "--source-band", "-s", help="e.g. 40m"),
    target_band: str = typer.Option(..., "--target-band", "-t", help="e.g. 2m"),
    source_callsign: str = typer.Option("UNKNOWN", "--source-callsign"),
    destination_callsign: Optional[str] = typer.Option(None, "--destination-callsign"),
    deliver_at: Optional[str] = typer.Option(None, "--deliver-at", help="ISO datetime when to deliver on target band"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
) -> None:
    """Relay message from one band to another (POST /messages/relay)."""
    _require_token()
    body: dict = {
        "message": message,
        "source_band": source_band,
        "target_band": target_band,
        "source_callsign": source_callsign,
    }
    if destination_callsign:
        body["destination_callsign"] = destination_callsign
    if deliver_at:
        body["deliver_at"] = deliver_at
    data = _api_post("/messages/relay", json=body, base_url=base_url)
    typer.echo(f"Relayed. Source transcript ID: {data.get('source_transcript_id')}, relayed ID: {data.get('relayed_transcript_id')}")


# -----------------------------------------------------------------------------
# Transcripts group
# -----------------------------------------------------------------------------

transcripts_app = typer.Typer(help="Transcripts: list, get, play.")
app.add_typer(transcripts_app, name="transcripts")


@transcripts_app.command("list")
def transcripts_list(
    callsign: Optional[str] = typer.Option(None, "--callsign", "-c"),
    band: Optional[str] = typer.Option(None, "--band", "-b"),
    mode: Optional[str] = typer.Option(None, "--mode", "-m"),
    since: Optional[str] = typer.Option(None, "--since", help="ISO 8601 time"),
    limit: int = typer.Option(100, "--limit", "-n", help="Max results (1-500)"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
) -> None:
    """Search transcripts (GET /transcripts)."""
    _require_token()
    params: dict = {"limit": limit}
    if callsign:
        params["callsign"] = callsign
    if band:
        params["band"] = band
    if mode:
        params["mode"] = mode
    if since:
        params["since"] = since
    data = _api_get("/transcripts", base_url=base_url, params=params)
    transcripts = data.get("transcripts", [])
    count = data.get("count", len(transcripts))
    typer.echo(f"Transcripts: {count}")
    for t in transcripts:
        tid = t.get("id") or t.get("transcript_id")
        src = t.get("source_callsign", "?")
        text = (t.get("transcript_text") or "")[:60]
        typer.echo(f"  [{tid}] {src}: {text}...")


@transcripts_app.command("get")
def transcripts_get(
    transcript_id: int = typer.Argument(..., help="Transcript ID"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
) -> None:
    """Get a single transcript by ID (GET /transcripts/{id})."""
    _require_token()
    data = _api_get(f"/transcripts/{transcript_id}", base_url=base_url)
    typer.echo(f"ID: {data.get('id') or transcript_id}")
    typer.echo(f"Source: {data.get('source_callsign')}")
    typer.echo(f"Text: {data.get('transcript_text', '')}")


@transcripts_app.command("play")
def transcripts_play(
    transcript_id: int = typer.Argument(..., help="Transcript ID to play over radio (TTS)"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
) -> None:
    """Play transcript as TTS over radio (POST /transcripts/{id}/play)."""
    _require_token()
    _api_post(f"/transcripts/{transcript_id}/play", base_url=base_url)
    typer.echo(f"Playing transcript {transcript_id} over radio.")


# -----------------------------------------------------------------------------
# Radio group
# -----------------------------------------------------------------------------

radio_app = typer.Typer(help="Radio: bands, send-tts.")
app.add_typer(radio_app, name="radio")


@radio_app.command("bands")
def radio_bands(
    base_url: Optional[str] = typer.Option(None, "--base-url"),
) -> None:
    """List supported bands (GET /radio/bands)."""
    _require_token()
    data = _api_get("/radio/bands", base_url=base_url)
    bands = data.get("bands", [])
    typer.echo("Bands: " + ", ".join(bands))


@radio_app.command("send-tts")
def radio_send_tts(
    message: str = typer.Argument(..., help="Message to speak over radio (TTS)"),
    frequency_hz: Optional[float] = typer.Option(None, "--frequency-hz"),
    mode: Optional[str] = typer.Option(None, "--mode"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
) -> None:
    """Send text as TTS over the radio (POST /radio/send-tts)."""
    _require_token()
    body: dict = {"message": message}
    if frequency_hz is not None:
        body["frequency_hz"] = frequency_hz
    if mode:
        body["mode"] = mode
    _api_post("/radio/send-tts", json=body, base_url=base_url)
    typer.echo("Sent TTS.")


# -----------------------------------------------------------------------------
# Config group (show LLM, memory, overrides from file)
# -----------------------------------------------------------------------------

config_app = typer.Typer(help="Configuration: show LLM, memory, and per-role overrides from config file.")
app.add_typer(config_app, name="config")


def _load_config_for_cli(config_dir: Optional[Path] = None) -> Optional[dict]:
    """Load config.yaml from project root; return dict or None."""
    try:
        from radioshaq.config.schema import load_config
        root = config_dir or Path.cwd()
        for candidate in [root / "config.yaml", root / "config.json", Path(__file__).resolve().parent.parent.parent / "config.yaml"]:
            if candidate.exists():
                cfg = load_config(candidate)
                return {"llm": _safe_llm_dict(cfg.llm), "memory": cfg.memory.model_dump(mode="json"), "llm_overrides": getattr(cfg, "llm_overrides", None) or {}, "memory_overrides": getattr(cfg, "memory_overrides", None) or {}}
        return None
    except Exception:
        return None


def _safe_llm_dict(llm: Any) -> dict:
    """Dict from LLMConfig with API keys redacted."""
    d = llm.model_dump(mode="json") if hasattr(llm, "model_dump") else {}
    for k in ("mistral_api_key", "openai_api_key", "anthropic_api_key", "custom_api_key"):
        if d.get(k):
            d[k] = "(set)"
    return d


@config_app.command("show")
def config_show(
    section: Optional[str] = typer.Option(None, "--section", "-s", help="Section: llm | memory | overrides (default: all)"),
    config_dir: Optional[Path] = typer.Option(None, "--config-dir", path_type=Path),
) -> None:
    """Show configuration from config.yaml (LLM, memory, overrides). API keys are redacted."""
    import json
    data = _load_config_for_cli(config_dir)
    if not data:
        typer.echo("No config.yaml found in project root or --config-dir.", err=True)
        raise typer.Exit(1)
    if section:
        if section == "llm":
            typer.echo(json.dumps(data["llm"], indent=2))
        elif section == "memory":
            typer.echo(json.dumps(data["memory"], indent=2))
        elif section == "overrides":
            typer.echo(json.dumps({"llm_overrides": data["llm_overrides"], "memory_overrides": data["memory_overrides"]}, indent=2))
        else:
            typer.echo(f"Unknown section: {section}. Use llm | memory | overrides.", err=True)
            raise typer.Exit(1)
    else:
        typer.echo(json.dumps(data, indent=2))


# -----------------------------------------------------------------------------
# Setup (interactive / non-interactive)
# -----------------------------------------------------------------------------


@app.command("setup")
def setup(
    interactive: bool = typer.Option(
        True,
        "--interactive/--no-interactive",
        help="Run with prompts (default). Use --no-interactive for CI.",
    ),
    no_input: bool = typer.Option(
        False,
        "--no-input/--input",
        help="Non-interactive: use env/flags only, no prompts.",
    ),
    ci: bool = typer.Option(
        False,
        "--ci",
        help="Same as --no-input (for CI/scripts).",
    ),
    quick: bool = typer.Option(
        False,
        "--quick/--full",
        help="Minimal prompts (mode, Docker for DB?), then defaults.",
    ),
    reconfigure: bool = typer.Option(
        False,
        "--reconfigure/--fresh",
        help="Update existing configuration (merge) instead of starting fresh.",
    ),
    config_dir: Optional[Path] = typer.Option(
        None,
        "--config-dir",
        path_type=Path,
        help="Directory for config.yaml and .env (default: project root).",
    ),
    force: bool = typer.Option(
        False,
        "--force/--no-force",
        help="Overwrite existing .env/config without asking.",
    ),
    mode: Optional[str] = typer.Option(
        None,
        "--mode",
        "-m",
        help="Mode for --no-input: field | hq | receiver.",
    ),
    db_url: Optional[str] = typer.Option(
        None,
        "--db-url",
        help="PostgreSQL URL for --no-input (e.g. postgresql://user:pass@host:5434/db).",
    ),
    station_callsign: Optional[str] = typer.Option(
        None,
        "--station-callsign",
        help="This station's ham callsign (e.g. K5ABC). Used with --no-input.",
    ),
    trigger_phrases: Optional[str] = typer.Option(
        None,
        "--trigger-phrases",
        help="Comma-separated trigger phrases for voice (e.g. 'radioshaq, field station'). Used with --no-input.",
    ),
    llm_provider: Optional[str] = typer.Option(
        None,
        "--llm-provider",
        help="LLM provider for --no-input: mistral | openai | anthropic | custom.",
    ),
    llm_model: Optional[str] = typer.Option(
        None,
        "--llm-model",
        help="LLM model name (e.g. mistral-large-latest, ollama/llama2). Used with --no-input.",
    ),
    custom_api_base: Optional[str] = typer.Option(
        None,
        "--custom-api-base",
        help="Custom LLM API base URL (e.g. http://localhost:11434 for Ollama). Used with --no-input.",
    ),
    hindsight_url: Optional[str] = typer.Option(
        None,
        "--hindsight-url",
        help="Hindsight base URL (e.g. http://localhost:8888). Used with --no-input.",
    ),
    memory_enabled: Optional[bool] = typer.Option(
        None,
        "--memory-enabled/--memory-disabled",
        help="Enable or disable memory (Hindsight). Used with --no-input.",
    ),
    radio_reply_tx_enabled: Optional[bool] = typer.Option(
        None,
        "--radio-reply-tx-enabled/--radio-reply-tx-disabled",
        help="Enable/disable outbound radio replies from MessageBus (used with --no-input).",
    ),
    radio_reply_use_tts: Optional[bool] = typer.Option(
        None,
        "--radio-reply-use-tts/--radio-reply-no-tts",
        help="Use TTS for outbound MessageBus radio replies (used with --no-input).",
    ),
    llm_overrides: Optional[str] = typer.Option(
        None,
        "--llm-overrides",
        help="Per-role LLM overrides as JSON (e.g. {\"whitelist\":{\"provider\":\"custom\",\"model\":\"ollama/llama2\",\"custom_api_base\":\"http://localhost:11434\"}}). Used with --no-input.",
    ),
) -> None:
    """Interactive setup: create .env and config.yaml in project root (or --config-dir).

    By default writes to the directory containing pyproject.toml (project root).
    Use --no-input or --ci with --mode and optionally --db-url for CI/scripts.
    Use --quick for minimal prompts; --reconfigure to update only selected sections.
    See docs/quick-start.md and docs/configuration.md.
    """
    from radioshaq.setup import run_setup
    trigger_list: Optional[list[str]] = None
    if trigger_phrases is not None:
        trigger_list = [p.strip() for p in trigger_phrases.split(",") if p.strip()]
    exit_code = run_setup(
        interactive=interactive,
        no_input=no_input or ci,
        quick=quick,
        reconfigure=reconfigure,
        config_dir=config_dir,
        force=force,
        mode=mode,
        db_url=db_url,
        station_callsign=station_callsign,
        trigger_phrases=trigger_list,
        llm_provider=llm_provider,
        llm_model=llm_model,
        custom_api_base=custom_api_base,
        hindsight_url=hindsight_url,
        memory_enabled=memory_enabled,
        radio_reply_tx_enabled=radio_reply_tx_enabled,
        radio_reply_use_tts=radio_reply_use_tts,
        llm_overrides=llm_overrides,
    )
    raise typer.Exit(exit_code)


# -----------------------------------------------------------------------------
# Launch (docker / pm2) – start dependencies and app for dev
# -----------------------------------------------------------------------------

launch_app = typer.Typer(
    name="launch",
    help="Start dependencies and app for development (Docker Compose or PM2).",
)


def _project_root() -> Path:
    from radioshaq.setup import resolve_project_root
    return resolve_project_root(None)


@launch_app.command("docker")
def launch_docker(
    hindsight: bool = typer.Option(
        False,
        "--hindsight/--no-hindsight",
        help="Also start Hindsight (semantic memory) container.",
    ),
    project_root: Optional[Path] = typer.Option(
        None,
        "--project-root",
        path_type=Path,
        help="Project root (default: auto-detect from CWD).",
    ),
) -> None:
    """Start Docker Compose services: Postgres (required), optionally Hindsight.

    Ensures upstreams are started in order (Postgres first; Hindsight depends on Postgres).
    Use from the radioshaq project root or pass --project-root.

    Examples:
      radioshaq launch docker
      radioshaq launch docker --hindsight
    """
    root = (project_root or _project_root()).resolve()
    compose_file = root / "infrastructure" / "local" / "docker-compose.yml"
    if not compose_file.exists():
        typer.echo(f"Compose file not found: {compose_file}", err=True)
        raise typer.Exit(1)
    if shutil.which("docker") is None:
        typer.echo("Docker not found. Install Docker or use: radioshaq launch pm2", err=True)
        raise typer.Exit(1)
    if hindsight:
        cmd = [
            "docker", "compose", "-f", str(compose_file),
            "--profile", "hindsight", "up", "-d", "postgres", "hindsight",
        ]
    else:
        cmd = [
            "docker", "compose", "-f", str(compose_file),
            "up", "-d", "postgres",
        ]
    typer.echo(f"Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=str(root), check=True)
    except subprocess.CalledProcessError as e:
        typer.echo(f"Docker compose failed (exit {e.returncode})", err=True)
        raise typer.Exit(1)
    if hindsight:
        typer.echo("Postgres and Hindsight are up. API: radioshaq run-api or pm2 start ... --only radioshaq-api")
    else:
        typer.echo("Postgres is up. Start API: radioshaq run-api (or use: radioshaq launch pm2)")


@launch_app.command("pm2")
def launch_pm2(
    hindsight: bool = typer.Option(
        False,
        "--hindsight/--no-hindsight",
        help="Also start Hindsight API (requires pip install hindsight-all or use Docker for Hindsight).",
    ),
    project_root: Optional[Path] = typer.Option(
        None,
        "--project-root",
        path_type=Path,
        help="Project root (default: auto-detect from CWD).",
    ),
    ensure_docker: bool = typer.Option(
        True,
        "--ensure-docker/--no-ensure-docker",
        help="Start Docker Postgres first if docker is available.",
    ),
) -> None:
    """Start app via PM2 (API, optionally Hindsight). Starts Postgres via Docker first if available.

    Uses infrastructure/local/ecosystem.config.js. Hindsight is started before the API when --hindsight.

    Examples:
      radioshaq launch pm2
      radioshaq launch pm2 --hindsight
    """
    root = (project_root or _project_root()).resolve()
    ecosystem = root / "infrastructure" / "local" / "ecosystem.config.js"
    if not ecosystem.exists():
        typer.echo(f"Ecosystem file not found: {ecosystem}", err=True)
        raise typer.Exit(1)
    if shutil.which("pm2") is None:
        typer.echo("PM2 not found. Install: npm i -g pm2", err=True)
        raise typer.Exit(1)
    # Optionally start Docker Postgres first
    if ensure_docker and shutil.which("docker"):
        compose_file = root / "infrastructure" / "local" / "docker-compose.yml"
        if compose_file.exists():
            typer.echo("Starting Postgres with Docker...")
            subprocess.run(
                ["docker", "compose", "-f", str(compose_file), "up", "-d", "postgres"],
                cwd=str(root),
                check=False,
                capture_output=True,
            )
    # Start Hindsight first so API can connect to it
    if hindsight:
        typer.echo("Starting Hindsight API (pm2)...")
        try:
            subprocess.run(
                ["pm2", "start", str(ecosystem), "--only", "hindsight-api"],
                cwd=str(root),
                check=True,
            )
        except subprocess.CalledProcessError as e:
            typer.echo(f"PM2 start hindsight-api failed: {e}. Install hindsight-all or use Docker Hindsight.", err=True)
            raise typer.Exit(1)
    # Start RadioShaq API (and optionally other apps from ecosystem)
    typer.echo("Starting RadioShaq API (pm2)...")
    try:
        subprocess.run(
            ["pm2", "start", str(ecosystem), "--only", "radioshaq-api"],
            cwd=str(root),
            check=True,
        )
    except subprocess.CalledProcessError as e:
        typer.echo("PM2 start radioshaq-api failed.", err=True)
        raise typer.Exit(1)
    typer.echo("Done. pm2 logs / pm2 monit")


# Register launch subcommands: radioshaq launch docker | radioshaq launch pm2
app.add_typer(launch_app)


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------


def main() -> int:
    """Entry point for 'radioshaq' script and python -m radioshaq."""
    try:
        ensure_license_accepted()
        app()
        return 0
    except RuntimeError as e:
        typer.echo(str(e), err=True)
        return 1
    except typer.Exit as e:
        return e.exit_code
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
