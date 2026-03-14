"""Run transcript and memory retention: delete rows older than configured days.

Loads config from config.yaml / RADIOSHAQ_* env, then:
- If radio.transcript_retention_days > 0: deletes transcripts with timestamp < now - days.
- If memory.memory_retention_days > 0: deletes memory_messages with created_at < now - days.

Intended for cron (e.g. daily). Usage:
  uv run python -m radioshaq.scripts.retention
  # or from repo root: cd radioshaq && uv run python scripts/retention.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running as script from radioshaq dir (repo root must be on path for radioshaq package)
if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


async def run_retention() -> None:
    from loguru import logger
    from radioshaq.config.schema import Config
    from radioshaq.database.postgres_gis import PostGISManager
    from radioshaq.memory.manager import MemoryManager, _ensure_async_url

    config = Config()
    transcript_days = getattr(config.radio, "transcript_retention_days", 0) or 0
    memory_days = getattr(config.memory, "memory_retention_days", 0) or 0
    if transcript_days <= 0 and memory_days <= 0:
        logger.info("Retention: transcript_retention_days and memory_retention_days are 0; nothing to do.")
        return

    db_url = config.database.postgres_url
    db_url = _ensure_async_url(db_url)

    if transcript_days > 0:
        cutoff_t = datetime.now(timezone.utc) - timedelta(days=transcript_days)
        pg = PostGISManager(db_url)
        try:
            deleted = await pg.delete_transcripts_older_than(cutoff_t, limit=50_000)
            logger.info(
                "Retention: deleted {} transcript(s) older than {} days (cutoff {})",
                deleted,
                transcript_days,
                cutoff_t.isoformat(),
            )
        finally:
            await pg.engine.dispose()

    if memory_days > 0:
        cutoff_m = datetime.now(timezone.utc) - timedelta(days=memory_days)
        memory = MemoryManager(db_url)
        try:
            deleted = await memory.delete_messages_older_than(cutoff_m, limit=50_000)
            logger.info(
                "Retention: deleted {} memory_messages older than {} days (cutoff {})",
                deleted,
                memory_days,
                cutoff_m.isoformat(),
            )
        finally:
            await memory.engine.dispose()


def main() -> None:
    asyncio.run(run_retention())


if __name__ == "__main__":
    main()
