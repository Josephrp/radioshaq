"""Interactive and non-interactive setup: .env, config.yaml, Docker, migrations."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import typer
from radioshaq.config.schema import (
    Config,
    LLMProvider,
    Mode,
    load_config,
    save_config,
)


# Default Postgres URL (asyncpg for app; sync for Alembic uses POSTGRES_* or DATABASE_URL)
DEFAULT_POSTGRES_URL = "postgresql+asyncpg://radioshaq:radioshaq@127.0.0.1:5434/radioshaq"
DEFAULT_JWT_SECRET = "dev-secret-change-in-production"
CONFIG_FILENAME = "config.yaml"
ENV_FILENAME = ".env"
RADIOSHAQ_CONFIG_DIR = ".radioshaq"
DB_CHOICE_DOCKER = "docker"
DB_CHOICE_URL = "url"
DB_CHOICE_SKIP = "skip"
COMPOSE_PATH = "infrastructure/local/docker-compose.yml"
ALEMBIC_INI = "infrastructure/local/alembic.ini"
POSTGRES_PORT_DEFAULT = 5434


def resolve_project_root(config_dir: Optional[Path] = None) -> Path:
    """Resolve project root (directory containing pyproject.toml). Search upward from CWD or from this file."""
    if config_dir is not None and config_dir.is_dir():
        return config_dir
    # Search from CWD
    cwd = Path.cwd()
    current = cwd.resolve()
    for _ in range(20):
        if (current / "pyproject.toml").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    # Fallback: directory of this package (radioshaq/radioshaq/)
    this_file = Path(__file__).resolve()
    for _ in range(5):
        current = this_file.parent
        if (current / "pyproject.toml").exists():
            return current
        this_file = current
    return cwd


def detect_existing(
    project_root: Path,
) -> tuple[bool, bool, bool]:
    """Return (has_dotenv, has_config_yaml, has_radioshaq_config)."""
    dotenv = (project_root / ENV_FILENAME).exists()
    config_yaml = (project_root / CONFIG_FILENAME).exists()
    radioshaq_config = (project_root / RADIOSHAQ_CONFIG_DIR / CONFIG_FILENAME).exists()
    return dotenv, config_yaml, radioshaq_config


def _parse_postgres_url(url: str) -> dict[str, str]:
    """Parse postgresql[+asyncpg]://user:pass@host:port/db into POSTGRES_* components."""
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = str(parsed.port or 5434)
    path = (parsed.path or "/radioshaq").strip("/")
    db = path.split("/")[0] if path else "radioshaq"
    user = parsed.username or "radioshaq"
    password = parsed.password or "radioshaq"
    return {
        "POSTGRES_HOST": host,
        "POSTGRES_PORT": port,
        "POSTGRES_DB": db,
        "POSTGRES_USER": user,
        "POSTGRES_PASSWORD": password,
    }


def _env_line(key: str, value: str) -> str:
    """Escape value for .env (no newlines in value; quote if contains space or #)."""
    value = str(value).strip().replace("\r", "").replace("\n", " ")
    if not value or " " in value or "#" in value or value.startswith("'"):
        return f'{key}="{value}"'
    return f"{key}={value}"


def write_env(
    project_root: Path,
    *,
    mode: str = "field",
    db_url: Optional[str] = None,
    jwt_secret: Optional[str] = None,
    llm_provider: Optional[str] = None,
    llm_api_key: Optional[str] = None,
    merge: bool = False,
) -> None:
    """Write or merge .env with POSTGRES_*, RADIOSHAQ_MODE, JWT, LLM, and optional RADIOSHAQ_*."""
    env_path = project_root / ENV_FILENAME
    url = db_url or DEFAULT_POSTGRES_URL.replace("+asyncpg", "")
    if "postgresql://" not in url and "postgresql+asyncpg://" in url:
        url = url.replace("postgresql+asyncpg://", "postgresql://")
    parts = _parse_postgres_url(url)

    override_keys = {
        "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD",
        "RADIOSHAQ_MODE", "RADIOSHAQ_JWT__SECRET_KEY", "RADIOSHAQ_LLM__PROVIDER",
        "MISTRAL_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "RADIOSHAQ_LLM__MISTRAL_API_KEY", "RADIOSHAQ_LLM__OPENAI_API_KEY", "RADIOSHAQ_LLM__ANTHROPIC_API_KEY",
    }
    lines: list[str] = []
    if merge and env_path.exists():
        existing = env_path.read_text(encoding="utf-8")
        for line in existing.splitlines():
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=", line)
            if m and m.group(1) in override_keys:
                continue
            lines.append(line)
        if lines and lines[-1].strip():
            lines.append("")
    else:
        lines = []

    if lines and lines[-1].strip():
        lines.append("")
    lines.append("# Database (PostgreSQL) – used by app and Alembic")
    for k, v in parts.items():
        lines.append(_env_line(k, v))
    lines.append("")
    lines.append("# Core")
    lines.append(_env_line("RADIOSHAQ_MODE", mode))
    if jwt_secret is not None:
        lines.append("")
        lines.append("# JWT (set SECRET_KEY in production)")
        lines.append(_env_line("RADIOSHAQ_JWT__SECRET_KEY", jwt_secret))
    if llm_provider is not None:
        lines.append("")
        lines.append("# LLM (set API key for your provider)")
        lines.append(_env_line("RADIOSHAQ_LLM__PROVIDER", llm_provider))
    if llm_api_key and llm_provider:
        key_var = {
            "mistral": "MISTRAL_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }.get(llm_provider.lower())
        if key_var:
            lines.append(_env_line(key_var, llm_api_key))

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _docker_available() -> bool:
    """Return True if docker CLI is available."""
    return shutil.which("docker") is not None


def _start_docker_postgres(project_root: Path) -> bool:
    """Run docker compose up -d postgres from project root. Return True on success."""
    compose_file = project_root / COMPOSE_PATH
    if not compose_file.exists():
        typer.echo(f"Compose file not found: {compose_file}", err=True)
        return False
    try:
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "up", "-d", "postgres"],
            cwd=str(project_root),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        typer.echo(f"Docker compose failed: {e.stderr or e}", err=True)
        return False
    return True


def _wait_for_port(host: str, port: int, timeout_sec: float = 60.0) -> bool:
    """Wait until host:port is accepting connections. Return True when ready."""
    import socket
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            s = socket.create_connection((host, port), timeout=2)
            s.close()
            return True
        except (OSError, socket.error):
            time.sleep(1.0)
    return False


def _run_alembic_upgrade(project_root: Path) -> bool:
    """Load .env and run alembic upgrade head. Return True on success."""
    env = os.environ.copy()
    env_path = project_root / ENV_FILENAME
    if env_path.exists():
        from dotenv import dotenv_values
        try:
            for k, v in (dotenv_values(env_path) or {}).items():
                if v is not None and k not in env:
                    env[k] = str(v)
        except Exception:
            pass
    if "DATABASE_URL" not in env and "POSTGRES_HOST" in env:
        h = env.get("POSTGRES_HOST", "127.0.0.1")
        p = env.get("POSTGRES_PORT", "5434")
        d = env.get("POSTGRES_DB", "radioshaq")
        u = env.get("POSTGRES_USER", "radioshaq")
        pw = env.get("POSTGRES_PASSWORD", "radioshaq")
        env["DATABASE_URL"] = f"postgresql://{u}:{pw}@{h}:{p}/{d}"
    alembic_ini = project_root / ALEMBIC_INI
    if not alembic_ini.exists():
        typer.echo(f"Alembic config not found: {alembic_ini}", err=True)
        return False
    try:
        import sys
        alembic_cmd = [sys.executable, "-m", "alembic", "-c", str(alembic_ini), "upgrade", "head"]
        subprocess.run(
            alembic_cmd,
            cwd=str(project_root),
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        typer.echo(f"Alembic upgrade failed: {e.stderr or e}", err=True)
        return False
    return True


def _prompt_mode() -> str:
    """Prompt for mode (field / hq / receiver)."""
    choice = typer.prompt(
        "Mode",
        default="field",
        show_default=True,
    ).strip().lower()
    if choice not in ("field", "hq", "receiver"):
        return "field"
    return choice


def _prompt_database() -> tuple[str, Optional[str]]:
    """Prompt for database: docker / url / skip. Returns (choice, url_or_none)."""
    typer.echo("Database: 1) Use Docker Postgres (port 5434)  2) Existing Postgres URL  3) Skip for now")
    raw = typer.prompt("Choice [1]", default="1", show_default=False).strip() or "1"
    if raw in ("2", "url"):
        url = typer.prompt(
            "PostgreSQL URL (e.g. postgresql://user:pass@host:5434/db)",
            default="postgresql://radioshaq:radioshaq@127.0.0.1:5434/radioshaq",
        ).strip()
        return DB_CHOICE_URL, url or None
    if raw in ("3", "skip"):
        return DB_CHOICE_SKIP, None
    return DB_CHOICE_DOCKER, None


def _prompt_jwt_secret() -> str:
    """Prompt for JWT secret; default with warning."""
    typer.echo("JWT secret (leave default for dev only; change in production)")
    secret = typer.prompt(
        "JWT secret",
        default=DEFAULT_JWT_SECRET,
        show_default=False,
    ).strip()
    if not secret:
        secret = DEFAULT_JWT_SECRET
    if secret == DEFAULT_JWT_SECRET or secret == "dev-secret":
        typer.echo(typer.style("Warning: using default dev secret. Set a strong secret in production.", fg="yellow"))
    return secret


def _prompt_llm() -> tuple[str, Optional[str]]:
    """Prompt for LLM provider and optional API key. Returns (provider, api_key_or_none)."""
    provider = typer.prompt(
        "LLM provider (mistral / openai / anthropic)",
        default="mistral",
        show_default=True,
    ).strip().lower() or "mistral"
    if provider not in ("mistral", "openai", "anthropic"):
        provider = "mistral"
    key = typer.prompt(
        "LLM API key (optional; press Enter to skip and set later in .env)",
        default="",
        show_default=False,
    ).strip() or None
    return provider, key


def _run_interactive_prompts_core(
    project_root: Path,
    has_dotenv: bool,
    has_config: bool,
    force: bool,
    reconfigure: bool,
) -> tuple[Optional[Config], str, str, Optional[str], str, str, Optional[str], bool, bool]:
    """Run core interactive prompts. Returns (base_config, mode, db_choice, db_url, jwt_secret, llm_provider, llm_key, merge_env, merge_config)."""
    base_config: Optional[Config] = None
    merge_env = False
    merge_config = False

    if (has_dotenv or has_config) and not force and not reconfigure:
        typer.echo("Existing .env and/or config.yaml detected.")
        if has_dotenv:
            merge_env = typer.confirm("Merge into existing .env? (y=merge, n=overwrite)", default=False)
        if has_config:
            merge_config = typer.confirm("Merge into existing config.yaml? (y=merge, n=overwrite)", default=False)
            if merge_config:
                try:
                    base_config = load_config(project_root / CONFIG_FILENAME)
                except Exception:
                    base_config = None

    mode = _prompt_mode()
    db_choice, db_choice_url = _prompt_database()
    jwt_secret = _prompt_jwt_secret()
    llm_provider, llm_key = _prompt_llm()

    if db_choice == DB_CHOICE_SKIP:
        db_url: Optional[str] = None
    elif db_choice == DB_CHOICE_DOCKER:
        db_url = "postgresql://radioshaq:radioshaq@127.0.0.1:5434/radioshaq"
    else:
        db_url = db_choice_url

    return base_config, mode, db_choice, db_url, jwt_secret, llm_provider, llm_key, merge_env, merge_config


def _run_quick_prompts() -> tuple[str, str, Optional[str]]:
    """Minimal prompts for --quick: mode and Docker for DB. Returns (mode, db_choice, db_url)."""
    mode = _prompt_mode()
    use_docker = typer.confirm("Use Docker for Postgres (port 5434)?", default=True)
    if use_docker:
        return mode, DB_CHOICE_DOCKER, "postgresql://radioshaq:radioshaq@127.0.0.1:5434/radioshaq"
    return mode, DB_CHOICE_SKIP, None


def _prompt_radio_audio() -> tuple[bool, int, str, bool]:
    """Prompt for radio (enabled, rig model, port) and audio_input_enabled. Returns (radio_enabled, rig_model, port, audio_input_enabled)."""
    radio_enabled = typer.confirm("Enable radio (CAT/rig)?", default=False)
    rig_model = 1
    port = "/dev/ttyUSB0"
    if os.name == "nt":
        port = "COM1"
    if radio_enabled:
        try:
            rig_model = int(typer.prompt("Hamlib rig model number", default="1"))
        except ValueError:
            rig_model = 1
        port = typer.prompt("Radio port", default=port)
    audio_input = typer.confirm("Enable voice_rx / audio input pipeline?", default=False)
    return radio_enabled, rig_model, port, audio_input


def _prompt_memory() -> tuple[bool, Optional[str]]:
    """Prompt for memory (enabled, Hindsight URL). Returns (enabled, hindsight_url)."""
    enabled = typer.confirm("Enable memory (per-callsign, Hindsight)?", default=True)
    url: Optional[str] = None
    if enabled:
        url = typer.prompt("Hindsight base URL (optional)", default="http://localhost:8888").strip() or None
    return enabled, url


def _prompt_field_hq(mode_val: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[int]]:
    """Prompt for field (station_id, hq_base_url, hq_auth_token) or hq (host, port). Returns (station_id, hq_base_url, hq_auth_token, hq_host, hq_port)."""
    station_id = None
    hq_base_url = None
    hq_auth_token = None
    hq_host = None
    hq_port = None
    if mode_val == "field":
        station_id = typer.prompt("Field station ID", default="FIELD-01").strip() or "FIELD-01"
        hq_base_url = typer.prompt("HQ base URL (optional)", default="https://hq.radioshaq.example.com").strip() or None
        hq_auth_token = typer.prompt("HQ auth token (optional)", default="").strip() or None
    elif mode_val == "hq":
        hq_host = typer.prompt("HQ bind host", default="0.0.0.0").strip() or "0.0.0.0"
        try:
            hq_port = int(typer.prompt("HQ port", default="8000"))
        except ValueError:
            hq_port = 8000
    return station_id, hq_base_url, hq_auth_token, hq_host, hq_port


def _run_reconfigure_prompts(project_root: Path, existing_config: Config) -> tuple[Config, str, str, Optional[str], str, str, Optional[str]]:
    """Reconfigure: prompt which sections to change, then prompt only those. Returns (config, mode, db_choice, db_url, jwt_secret, llm_provider, llm_key)."""
    config = existing_config
    mode_val = config.mode.value
    db_choice = DB_CHOICE_URL
    db_url_val: Optional[str] = config.database.postgres_url.replace("postgresql+asyncpg://", "postgresql://")
    jwt_secret = config.jwt.secret_key
    if jwt_secret.startswith("("):
        jwt_secret = DEFAULT_JWT_SECRET
    llm_provider = config.llm.provider.value
    llm_key: Optional[str] = None

    sections = ["mode", "database", "jwt", "llm", "done"]
    while True:
        choice = typer.prompt(
            "What to change? (mode / database / jwt / llm / done)",
            default="done",
        ).strip().lower() or "done"
        if choice == "done":
            break
        if choice == "mode":
            mode_val = _prompt_mode()
        elif choice == "database":
            db_choice, db_url_val = _prompt_database()
            if db_choice == DB_CHOICE_SKIP:
                db_url_val = None
            elif db_choice == DB_CHOICE_DOCKER:
                db_url_val = "postgresql://radioshaq:radioshaq@127.0.0.1:5434/radioshaq"
        elif choice == "jwt":
            jwt_secret = _prompt_jwt_secret()
        elif choice == "llm":
            llm_provider, llm_key = _prompt_llm()

    return config, mode_val, db_choice, db_url_val, jwt_secret, llm_provider, llm_key


def run_setup(
    interactive: bool = True,
    no_input: bool = False,
    quick: bool = False,
    reconfigure: bool = False,
    config_dir: Optional[Path] = None,
    force: bool = False,
    mode: Optional[str] = None,
    db_url: Optional[str] = None,
) -> int:
    """Run setup: non-interactive writes .env + config.yaml; interactive will prompt (Phase 2+).
    Returns exit code (0 = success).
    """
    project_root = resolve_project_root(config_dir)
    has_dotenv, has_config, has_radioshaq_config = detect_existing(project_root)

    if no_input:
        # Require minimal: mode defaults to field; db_url optional (use default)
        mode_val = (mode or os.environ.get("RADIOSHAQ_MODE") or "field").strip().lower()
        if mode_val not in ("field", "hq", "receiver"):
            mode_val = "field"
        db_url_val = db_url or os.environ.get("DATABASE_URL")
        if not db_url_val and (os.environ.get("POSTGRES_HOST") or os.environ.get("POSTGRES_PORT")):
            # Build from POSTGRES_*
            h = os.environ.get("POSTGRES_HOST", "127.0.0.1")
            p = os.environ.get("POSTGRES_PORT", "5434")
            d = os.environ.get("POSTGRES_DB", "radioshaq")
            u = os.environ.get("POSTGRES_USER", "radioshaq")
            pw = os.environ.get("POSTGRES_PASSWORD", "radioshaq")
            db_url_val = f"postgresql://{u}:{pw}@{h}:{p}/{d}"

        try:
            # Build config from defaults and overrides
            config = Config()
            config.mode = Mode(mode_val)
            if db_url_val:
                url_async = db_url_val.replace("postgresql://", "postgresql+asyncpg://")
                config.database.postgres_url = url_async
            config_path = project_root / CONFIG_FILENAME
            env_path = project_root / ENV_FILENAME
            # Optionally skip overwriting if files exist and not force
            write_config = force or not config_path.exists()
            write_env_file = force or not env_path.exists()
            if write_config:
                save_config(config, config_path)
            if write_env_file:
                write_env(
                    project_root,
                    mode=mode_val,
                    db_url=db_url_val or DEFAULT_POSTGRES_URL.replace("+asyncpg", ""),
                    merge=False,
                )
            return 0
        except OSError as e:
            print(f"Cannot write config or .env: {e}", flush=True)
            return 1

    # Interactive path (Phase 2+): quick, reconfigure, or full prompts
    if has_radioshaq_config and not has_config:
        if typer.confirm("Found .radioshaq/config.yaml but no config.yaml. Copy to project root?", default=True):
            shutil.copy(project_root / RADIOSHAQ_CONFIG_DIR / CONFIG_FILENAME, project_root / CONFIG_FILENAME)
            has_config = True

    if quick:
        mode_val, db_choice, db_url_val = _run_quick_prompts()
        jwt_secret = DEFAULT_JWT_SECRET
        llm_provider = "mistral"
        llm_key = None
        merge_env = False
        merge_config = False
        base_config = None
    elif reconfigure and has_config:
        try:
            existing = load_config(project_root / CONFIG_FILENAME)
        except Exception:
            existing = Config()
        base_config, mode_val, db_choice, db_url_val, jwt_secret, llm_provider, llm_key = _run_reconfigure_prompts(project_root, existing)
        merge_env = True
        merge_config = True
    else:
        base_config, mode_val, db_choice, db_url_val, jwt_secret, llm_provider, llm_key, merge_env, merge_config = _run_interactive_prompts_core(
            project_root, has_dotenv, has_config, force, reconfigure
        )

    config = base_config if (base_config and merge_config) else Config()
    config.mode = Mode(mode_val)
    if db_url_val:
        url_async = db_url_val.replace("postgresql://", "postgresql+asyncpg://")
        config.database.postgres_url = url_async
    config.jwt.secret_key = jwt_secret
    config.llm.provider = LLMProvider(llm_provider)

    # Phase 6: radio, audio, memory, field/HQ (full interactive only)
    if not quick:
        radio_enabled, rig_model, radio_port, audio_input = _prompt_radio_audio()
        config.radio.enabled = radio_enabled
        config.radio.rig_model = rig_model
        config.radio.port = radio_port
        config.radio.audio_input_enabled = audio_input
        memory_enabled, hindsight_url = _prompt_memory()
        config.memory.enabled = memory_enabled
        if hindsight_url:
            config.memory.hindsight_base_url = hindsight_url
        sid, hq_url, hq_token, hq_host, hq_port = _prompt_field_hq(mode_val)
        if sid is not None:
            config.field.station_id = sid
        if hq_url is not None:
            config.field.hq_base_url = hq_url
        if hq_token is not None:
            config.field.hq_auth_token = hq_token or None
        if hq_host is not None:
            config.hq.host = hq_host
        if hq_port is not None:
            config.hq.port = hq_port

    # Save config file without secrets (they go in .env only)
    config.jwt.secret_key = "(set via RADIOSHAQ_JWT__SECRET_KEY)"
    config.llm.mistral_api_key = None
    config.llm.openai_api_key = None
    config.llm.anthropic_api_key = None

    config_path = project_root / CONFIG_FILENAME
    try:
        save_config(config, config_path)
        write_env(
            project_root,
            mode=mode_val,
            db_url=db_url_val,
            jwt_secret=jwt_secret,
            llm_provider=llm_provider,
            llm_api_key=llm_key,
            merge=merge_env,
        )
    except OSError as e:
        typer.echo(f"Cannot write config or .env: {e}", err=True)
        return 1

    # Phase 3–4: Docker + migrations when user chose Docker; else optional "Run migrations now?"
    migrations_done = False
    if db_choice == DB_CHOICE_DOCKER and _docker_available():
        do_docker = quick or typer.confirm("Start Docker Postgres and run migrations now?", default=True)
        if do_docker:
            if not _start_docker_postgres(project_root):
                typer.echo("Setup wrote config but Docker failed. Start Postgres manually and run: alembic -c infrastructure/local/alembic.ini upgrade head", err=True)
                return 1
            typer.echo("Waiting for Postgres on port 5434...")
            if not _wait_for_port("127.0.0.1", POSTGRES_PORT_DEFAULT):
                typer.echo("Postgres did not become ready. Check: docker compose -f infrastructure/local/docker-compose.yml logs postgres", err=True)
                return 1
            if not _run_alembic_upgrade(project_root):
                typer.echo("Migrations failed. Run manually: alembic -c infrastructure/local/alembic.ini upgrade head", err=True)
                return 1
            typer.echo("Migrations complete.")
            migrations_done = True
    if db_url_val and not migrations_done and (not quick) and typer.confirm("Run migrations now?", default=True):
        if not _run_alembic_upgrade(project_root):
            typer.echo("Migrations failed. Run manually: alembic -c infrastructure/local/alembic.ini upgrade head", err=True)
        else:
            typer.echo("Migrations complete.")

    # Phase 4: optional verify DB connection (skip in quick mode)
    if (not quick) and db_url_val and typer.confirm("Verify database connection?", default=False):
        try:
            from sqlalchemy import create_engine, text
            sync_url = config.database.postgres_url.replace("+asyncpg", "")
            if "asyncpg" in sync_url:
                sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql://")
            engine = create_engine(sync_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            typer.echo("Database connection OK.")
        except Exception as e:
            typer.echo(f"Database connection failed: {e}", err=True)

    # Phase 4: optional get token and suggest appending to .env (skip in quick mode)
    if (not quick) and typer.confirm("Get a token and append RADIOSHAQ_TOKEN to .env? (API must be running)", default=False):
        typer.echo("Run in another terminal: radioshaq token")
        typer.echo("Then append the output to .env: RADIOSHAQ_TOKEN=<paste token>")

    typer.echo("Setup complete. Start API: radioshaq run-api")
    typer.echo("See docs/quick-start.md and docs/configuration.md")
    return 0
