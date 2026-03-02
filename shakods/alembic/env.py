"""Alembic environment configuration.

This module configures Alembic to work with SHAKODS database models,
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

# Import SHAKODS models for autogenerate support
from shakods.database.models import Base

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
        PostgreSQL connection URL for migrations (sync)
    """
    # Priority: DATABASE_URL > individual vars > default
    if database_url := os.getenv("DATABASE_URL"):
        # Convert async URL to sync URL if needed
        if "+asyncpg" in database_url:
            return database_url.replace("+asyncpg", "")
        if "+aiosqlite" in database_url:
            return database_url.replace("+aiosqlite", "")
        return database_url
    
    # Build from individual components
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "shakods")
    user = os.getenv("POSTGRES_USER", "shakods")
    password = os.getenv("POSTGRES_PASSWORD", "shakods")
    
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


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
