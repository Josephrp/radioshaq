"""Alembic environment configuration.

This module configures Alembic to work with RadioShaq database models,
supporting both synchronous (for migrations) and asynchronous (for runtime)
PostgreSQL connections with PostGIS extension.
"""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection

# Import RadioShaq models for autogenerate support
from radioshaq.database.models import Base

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def get_database_url() -> str:
    """Get database URL from environment or config.

    Returns:
        PostgreSQL connection URL for migrations (sync).
        Uses psycopg2, adds connect_timeout and optional sslmode=disable
        so migrations do not hang (e.g. on SSL handshake or slow network).
    """
    # Query params: avoid hang on connect (timeout) and optional no-SSL (WSL/Docker)
    connect_timeout = os.getenv("ALEMBIC_CONNECT_TIMEOUT", "10")
    extra_params = f"connect_timeout={connect_timeout}"
    if os.getenv("ALEMBIC_SSLMODE_DISABLE", "").lower() in ("1", "true", "yes"):
        extra_params = f"sslmode=disable&{extra_params}"

    # Priority: DATABASE_URL > individual vars > default
    if database_url := os.getenv("DATABASE_URL"):
        # Convert async URL to sync URL if needed
        if "+asyncpg" in database_url:
            database_url = database_url.replace("+asyncpg", "")
        if "+aiosqlite" in database_url:
            database_url = database_url.replace("+aiosqlite", "")
        # Ensure sync driver for migrations (psycopg2)
        if "postgresql://" in database_url and "+" not in database_url.split("//")[0]:
            database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        # Append timeout (and optional sslmode) if not already present
        base, _, query = database_url.partition("?")
        if "connect_timeout" not in query:
            query = f"{query}&{extra_params}" if query else extra_params
            database_url = f"{base}?{query.lstrip('&')}"
        return database_url

    # Build from individual components (default port 5434 to match local Docker Postgres)
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5434")
    database = os.getenv("POSTGRES_DB", "radioshaq")
    user = os.getenv("POSTGRES_USER", "radioshaq")
    password = os.getenv("POSTGRES_PASSWORD", "radioshaq")

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}?{extra_params}"
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    
    This configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the given string to the script output.
    """
    url = get_database_url()
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        # Enable PostGIS support
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.
    
    In this scenario we create an Engine and associate a connection with the context.
    """
    # Get database URL
    database_url = get_database_url()
    
    # Create engine configuration
    configuration = config.get_section(config.config_ini_section)
    if configuration is None:
        configuration = {}
    
    configuration["sqlalchemy.url"] = database_url
    
    # Create engine
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            render_as_batch=True,
            # Compare type and server default for accurate autogenerate
            compare_type=True,
            compare_server_default=True,
        )
        
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
