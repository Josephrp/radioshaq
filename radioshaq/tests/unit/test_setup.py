"""Unit tests for radioshaq setup (interactive and non-interactive)."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest

from radioshaq.setup import (
    DB_CHOICE_SKIP,
    detect_existing,
    resolve_project_root,
    run_setup,
    write_env,
)


def test_resolve_project_root_from_given_dir(tmp_path: Path) -> None:
    """When config_dir is provided, it is returned as project root."""
    assert resolve_project_root(tmp_path) == tmp_path
    assert resolve_project_root(None) != tmp_path  # None uses CWD or package location


def test_detect_existing_nothing(tmp_path: Path) -> None:
    """Detect reports no files when none exist."""
    has_dotenv, has_config, has_radioshaq = detect_existing(tmp_path)
    assert has_dotenv is False
    assert has_config is False
    assert has_radioshaq is False


def test_detect_existing_dotenv_and_config(tmp_path: Path) -> None:
    """Detect finds .env and config.yaml when present."""
    (tmp_path / ".env").write_text("X=1")
    (tmp_path / "config.yaml").write_text("mode: field")
    has_dotenv, has_config, has_radioshaq = detect_existing(tmp_path)
    assert has_dotenv is True
    assert has_config is True
    assert has_radioshaq is False


def test_run_setup_no_input_creates_env_and_config(tmp_path: Path) -> None:
    """run_setup --no-input creates .env and config.yaml with expected keys."""
    exit_code = run_setup(
        interactive=False,
        no_input=True,
        quick=False,
        reconfigure=False,
        config_dir=tmp_path,
        force=False,
        mode="field",
        db_url=None,
    )
    assert exit_code == 0
    env_path = tmp_path / ".env"
    config_path = tmp_path / "config.yaml"
    assert env_path.exists()
    assert config_path.exists()

    env_content = env_path.read_text()
    assert "POSTGRES_HOST" in env_content
    assert "POSTGRES_PORT" in env_content
    assert "RADIOSHAQ_MODE" in env_content
    assert re.search(r"RADIOSHAQ_MODE=field", env_content) or "field" in env_content

    config_content = config_path.read_text()
    assert "mode:" in config_content
    assert "field" in config_content
    assert "database:" in config_content or "postgres" in config_content.lower()


def test_run_setup_no_input_with_mode_hq(tmp_path: Path) -> None:
    """run_setup --no-input --mode hq writes mode hq."""
    exit_code = run_setup(
        interactive=False,
        no_input=True,
        config_dir=tmp_path,
        mode="hq",
    )
    assert exit_code == 0
    env_content = (tmp_path / ".env").read_text()
    assert "RADIOSHAQ_MODE" in env_content
    assert "hq" in env_content
    config_content = (tmp_path / "config.yaml").read_text()
    assert "hq" in config_content


def test_run_setup_no_input_with_db_url(tmp_path: Path) -> None:
    """run_setup --no-input --db-url writes POSTGRES_* from URL."""
    exit_code = run_setup(
        interactive=False,
        no_input=True,
        config_dir=tmp_path,
        db_url="postgresql://myuser:mypass@dbhost:5433/mydb",
    )
    assert exit_code == 0
    env_content = (tmp_path / ".env").read_text()
    assert "POSTGRES_HOST=dbhost" in env_content or "dbhost" in env_content
    assert "POSTGRES_PORT=5433" in env_content or "5433" in env_content
    assert "POSTGRES_USER=myuser" in env_content or "myuser" in env_content
    assert "mydb" in env_content


def test_run_setup_no_input_radio_reply_tts_flags(tmp_path: Path) -> None:
    """run_setup --no-input writes radio reply TX/TTS flags when explicitly provided."""
    exit_code = run_setup(
        interactive=False,
        no_input=True,
        config_dir=tmp_path,
        radio_reply_tx_enabled=True,
        radio_reply_use_tts=False,
    )
    assert exit_code == 0
    config_content = (tmp_path / "config.yaml").read_text()
    assert "radio_reply_tx_enabled: true" in config_content.lower()
    assert "radio_reply_use_tts: false" in config_content.lower()


def test_write_env_merge_preserves_other_vars(tmp_path: Path) -> None:
    """write_env with merge=True keeps existing vars not overridden."""
    env_path = tmp_path / ".env"
    env_path.write_text("CUSTOM_VAR=keep\nRADIOSHAQ_MODE=receiver\n")
    write_env(tmp_path, mode="field", merge=True)
    content = env_path.read_text()
    assert "CUSTOM_VAR" in content
    assert "keep" in content
    assert "RADIOSHAQ_MODE" in content
    assert "field" in content


def test_run_setup_quick_mocked_writes_config(tmp_path: Path) -> None:
    """run_setup --quick with mocked prompts writes .env and config.yaml."""
    with (
        patch("radioshaq.setup._prompt_mode", return_value="field"),
        patch("radioshaq.setup.typer.confirm") as mock_confirm,
    ):
        mock_confirm.return_value = False  # No Docker for Postgres
        exit_code = run_setup(
            interactive=True,
            no_input=False,
            quick=True,
            reconfigure=False,
            config_dir=tmp_path,
            force=False,
        )
    assert exit_code == 0
    assert (tmp_path / ".env").exists()
    assert (tmp_path / "config.yaml").exists()
    env_content = (tmp_path / ".env").read_text()
    assert "RADIOSHAQ_MODE" in env_content
    assert "field" in env_content
    config_content = (tmp_path / "config.yaml").read_text()
    assert "mode:" in config_content
    assert "field" in config_content


def test_run_setup_interactive_mocked_writes_config(tmp_path: Path) -> None:
    """run_setup interactive with all prompts mocked writes expected config."""
    with (
        patch("radioshaq.setup._run_interactive_prompts_core") as mock_core,
        patch("radioshaq.setup._prompt_radio_audio", return_value=(False, 1, "COM1", False, True, True)),
        patch("radioshaq.setup._prompt_memory", return_value=(True, "http://localhost:8888")),
        patch("radioshaq.setup._prompt_field_hq", return_value=("FIELD-01", None, None, None, None)),
        patch("radioshaq.setup._prompt_station_callsign_trigger", return_value=(None, [])),
        patch("radioshaq.setup._prompt_compliance_region", return_value=("FCC", None)),
        patch("radioshaq.setup._prompt_llm_overrides", return_value={}),
        patch("radioshaq.setup.typer.confirm", return_value=False),
        patch("radioshaq.setup._docker_available", return_value=False),
    ):
        from radioshaq.config.schema import Config

        mock_core.return_value = (
            None,  # base_config
            "hq",  # mode
            DB_CHOICE_SKIP,  # db_choice
            None,  # db_url
            "custom-jwt-secret",  # jwt_secret
            "openai",  # llm_provider
            "sk-fake",  # llm_key
            None,  # llm_model
            None,  # custom_api_base
            False,  # merge_env
            False,  # merge_config
        )
        exit_code = run_setup(
            interactive=True,
            no_input=False,
            quick=False,
            reconfigure=False,
            config_dir=tmp_path,
            force=False,
        )
    assert exit_code == 0
    env_content = (tmp_path / ".env").read_text()
    assert "RADIOSHAQ_MODE" in env_content
    assert "hq" in env_content
    assert "RADIOSHAQ_JWT__SECRET_KEY" in env_content
    assert "custom-jwt-secret" in env_content
    assert "OPENAI_API_KEY" in env_content or "openai" in env_content
    config_content = (tmp_path / "config.yaml").read_text()
    assert "hq" in config_content
    assert "FIELD-01" in config_content or "field:" in config_content
    assert "memory:" in config_content


def test_run_setup_reconfigure_mocked_merges_config(tmp_path: Path) -> None:
    """run_setup --reconfigure with existing config and mocked prompts merges sections."""
    (tmp_path / "config.yaml").write_text(
        "mode: field\ndatabase:\n  postgres_url: postgresql+asyncpg://x:y@localhost:5432/db\n"
    )
    with (
        patch("radioshaq.setup._run_reconfigure_prompts") as mock_reconfig,
        patch("radioshaq.setup._prompt_radio_audio", return_value=(False, 1, "COM1", False, True, True)),
        patch("radioshaq.setup._prompt_memory", return_value=(True, "http://localhost:8888")),
        patch("radioshaq.setup._prompt_field_hq", return_value=("FIELD-01", None, None, None, None)),
        patch("radioshaq.setup._prompt_station_callsign_trigger", return_value=(None, [])),
        patch("radioshaq.setup._prompt_compliance_region", return_value=("FCC", None)),
        patch("radioshaq.setup._prompt_llm_overrides", return_value={}),
        patch("radioshaq.setup.typer.confirm", return_value=False),
        patch("radioshaq.setup._docker_available", return_value=False),
    ):
        from radioshaq.config.schema import Config, Mode

        existing = Config()
        existing.mode = Mode.FIELD
        existing.database.postgres_url = "postgresql+asyncpg://x:y@localhost:5432/db"
        mock_reconfig.return_value = (
            existing,
            "receiver",  # mode changed
            DB_CHOICE_SKIP,
            None,
            "new-secret",
            "mistral",
            None,
            None,  # llm_model_val
            None,  # custom_api_base_val
        )
        exit_code = run_setup(
            interactive=True,
            no_input=False,
            quick=False,
            reconfigure=True,
            config_dir=tmp_path,
            force=False,
        )
    assert exit_code == 0
    config_content = (tmp_path / "config.yaml").read_text()
    assert "receiver" in config_content
