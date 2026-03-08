"""Alembic environment configuration for RadioShaq.

This script configures Alembic migrations for the RadioShaq database,
supporting both PostgreSQL with PostGIS. Migrations run with the sync
driver (psycopg2) for compatibility and to avoid asyncpg auth issues
when running from the host.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

# Add project root to path (env.py is in infrastructure/local/alembic/)
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Load .env from project root so DATABASE_URL is available
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection

# Import RadioShaq models
from radioshaq.database.models import Base

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for migrations
target_metadata = Base.metadata

# Database URL: prefer DATABASE_URL env, else explicit default (port 5434 = Docker mapping)
DEFAULT_POSTGRES_URL = "postgresql+asyncpg://radioshaq:radioshaq@127.0.0.1:5434/radioshaq"
if "DATABASE_URL" in os.environ:
    DATABASE_URL = os.environ["DATABASE_URL"]
else:
    DATABASE_URL = DEFAULT_POSTGRES_URL

# If URL points at localhost:5432, use 5434 so migrations hit Docker Postgres (host 5432 often conflicts)
if "127.0.0.1:5432" in DATABASE_URL or "localhost:5432" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("127.0.0.1:5432", "127.0.0.1:5434").replace("localhost:5432", "127.0.0.1:5434")


def _sync_url(url: str) -> str:
    """Convert asyncpg URL to sync psycopg2 URL for Alembic."""
    if "postgresql+asyncpg://" in url or "postgresql+asyncpg:" in url:
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1).replace(
            "postgresql+asyncpg:", "postgresql+psycopg2:", 1
        )
    if "postgresql://" in url and "+" not in url.split("//")[0]:
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


# Sync URL for migrations (psycopg2); app continues to use asyncpg
SYNC_URL = _sync_url(DATABASE_URL)
config.set_main_option("sqlalchemy.url", SYNC_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    
    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.
    
    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Enable PostGIS support
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def include_object(object, name, type_, reflected, compare_to):
    """Filter objects for migration.
    
    Exclude PostGIS tables and other spatial extensions.
    """
    # Skip PostGIS system tables
    if type_ == "table" and name in (
        "spatial_ref_sys",
        "geometry_columns",
        "geography_columns",
    ):
        return False
    return True


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        # Compare types for PostGIS
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with sync engine (psycopg2)."""
    connectable = create_engine(
        SYNC_URL,
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        do_run_migrations(connection)
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
