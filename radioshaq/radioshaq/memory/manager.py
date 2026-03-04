"""Async memory manager for per-callsign stateful context.

Uses PostgreSQL for core blocks, conversation history, and daily summaries.
Uses Hindsight service for semantic recall/reflect (bank_id per callsign).
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Default: America/New_York for daily summary cron
DEFAULT_TIMEZONE = ZoneInfo("America/New_York")
RECENT_MESSAGES_LIMIT = 40
CONTEXT_WINDOW_TOKENS = 200_000


def _normalize_callsign(callsign: str) -> str:
    """Normalize callsign for storage (uppercase, strip)."""
    return (callsign or "").strip().upper() or "UNKNOWN"


def _ensure_async_url(url: str) -> str:
    """Ensure URL uses asyncpg driver."""
    if url.startswith("postgresql://") and "asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


class MemoryManager:
    """Async manager for per-callsign memory (core blocks, messages, summaries)."""

    def __init__(self, database_url: str):
        self.database_url = _ensure_async_url(database_url)
        self.engine = create_async_engine(
            self.database_url,
            pool_size=5,
            max_overflow=10,
            echo=False,
        )
        self.async_session = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def get_core_blocks(self, callsign: str) -> dict[str, str]:
        """Load all core memory blocks for a callsign. Returns {block_type: content}."""
        callsign = _normalize_callsign(callsign)
        async with self.async_session() as session:
            result = await session.execute(
                text(
                    "SELECT block_type, content FROM memory_core_blocks "
                    "WHERE callsign = :callsign ORDER BY block_type"
                ),
                {"callsign": callsign},
            )
            rows = result.fetchall()
        result_dict = {row[0]: (row[1] or "") for row in rows}
        # Add system instructions (global, read-only)
        sys_instr = await self.get_system_instructions()
        result_dict["system_instructions"] = sys_instr
        return result_dict

    async def get_system_instructions(self) -> str:
        """Load read-only system instructions. Agent cannot edit."""
        async with self.async_session() as session:
            result = await session.execute(
                text("SELECT content FROM memory_system_instructions WHERE id = 1")
            )
            row = result.fetchone()
        return (row[0] or "") if row else ""

    async def get_block(self, callsign: str, block_type: str) -> str:
        """Get a single block. Returns empty string if not found."""
        blocks = await self.get_core_blocks(callsign)
        return blocks.get(block_type, "")

    async def update_block(
        self, callsign: str, block_type: str, content: str
    ) -> tuple[bool, str]:
        """Replace block content. Saves previous version to history. Returns (success, message)."""
        if block_type not in ("user", "identity", "ideaspace"):
            return False, f"Invalid block_type: {block_type}"
        callsign = _normalize_callsign(callsign)

        async with self.async_session() as session:
            # Get current version
            result = await session.execute(
                text(
                    "SELECT content, version FROM memory_core_blocks "
                    "WHERE callsign = :callsign AND block_type = :block_type"
                ),
                {"callsign": callsign, "block_type": block_type},
            )
            row = result.fetchone()
            if row:
                # Save to history before overwriting
                await session.execute(
                    text(
                        """
                        INSERT INTO memory_core_history (callsign, block_type, content, version)
                        SELECT callsign, block_type, content, version FROM memory_core_blocks
                        WHERE callsign = :callsign AND block_type = :block_type
                        """
                    ),
                    {"callsign": callsign, "block_type": block_type},
                )
                new_version = row[1] + 1
            else:
                new_version = 1

            await session.execute(
                text(
                    """
                    INSERT INTO memory_core_blocks (callsign, block_type, content, version, updated_at)
                    VALUES (:callsign, :block_type, :content, :version, NOW())
                    ON CONFLICT (callsign, block_type) DO UPDATE SET
                        content = EXCLUDED.content,
                        version = EXCLUDED.version,
                        updated_at = NOW()
                    """
                ),
                {"callsign": callsign, "block_type": block_type, "content": content, "version": new_version},
            )
            await session.commit()

        return True, f"Updated {block_type} (v{new_version})"

    async def append_to_block(
        self, callsign: str, block_type: str, addition: str
    ) -> tuple[bool, str]:
        """Append to block. Saves previous version to history."""
        current = await self.get_block(callsign, block_type)
        new_content = (current + "\n\n" + addition).strip() if current else addition
        return await self.update_block(callsign, block_type, new_content)

    async def load_messages(
        self,
        callsign: str,
        *,
        limit: int = RECENT_MESSAGES_LIMIT,
        since: datetime | None = None,
        until: datetime | None = None,
        max_tokens: int | None = CONTEXT_WINDOW_TOKENS,
        exclude_tool_messages: bool = True,
    ) -> list[dict[str, Any]]:
        """Load conversation history. Today OR last N, whichever is wider.
        Optional since/until for date range filtering."""
        callsign = _normalize_callsign(callsign)
        conditions = ["callsign = :callsign"]
        params: dict[str, Any] = {"callsign": callsign}
        if exclude_tool_messages:
            conditions.append("role != 'tool'")
        if since is not None:
            conditions.append("created_at >= :since")
            params["since"] = since
        if until is not None:
            conditions.append("created_at < :until")
            params["until"] = until
        where_clause = " AND ".join(conditions)
        async with self.async_session() as session:
            result = await session.execute(
                text(
                    f"""
                    SELECT id, callsign, idx, role, content, reasoning, created_at, metadata
                    FROM memory_messages
                    WHERE {where_clause}
                    ORDER BY idx ASC
                    """
                ),
                params,
            )
            rows = result.fetchall()

        out = []
        for r in rows:
            out.append({
                "role": r[3],
                "content": r[4] or "",
                "reasoning": r[5],
                "created_at": r[6],
                "metadata": dict(r[7] or {}),
            })

        if limit is not None or since is not None:
            today_start = len(out)
            if since is not None:
                for i, row in enumerate(out):
                    if row["created_at"] >= since:
                        today_start = i
                        break
            last_n_start = max(0, len(out) - limit) if limit is not None else len(out)
            out = out[min(today_start, last_n_start):]

        if max_tokens and max_tokens > 0:
            out = self._trim_to_token_limit(out, max_tokens)

        return out

    def _trim_to_token_limit(
        self, rows: list[dict[str, Any]], max_tokens: int
    ) -> list[dict[str, Any]]:
        """Keep most recent messages that fit within max_tokens."""
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model("gpt-4o")
        except Exception:
            enc = None

        def count_tokens(text: str) -> int:
            if enc:
                return len(enc.encode(text))
            return len(text) // 4

        total = 0
        result = []
        for row in reversed(rows):
            text_val = row.get("content") or ""
            if row.get("reasoning"):
                text_val = f"[Reasoning: {row['reasoning']}]\n\n{text_val}"
            tokens = count_tokens(text_val)
            if total + tokens > max_tokens and result:
                break
            result.insert(0, row)
            total += tokens
        return result

    async def append_messages(
        self,
        callsign: str,
        messages: list[tuple[str, str, dict | None, str | None]],
    ) -> None:
        """Append messages. Each tuple: (role, content, metadata_extra, reasoning)."""
        if not messages:
            return
        callsign = _normalize_callsign(callsign)

        async with self.async_session() as session:
            result = await session.execute(
                text(
                    "SELECT COALESCE(MAX(idx), -1) + 1 AS next_idx "
                    "FROM memory_messages WHERE callsign = :callsign"
                ),
                {"callsign": callsign},
            )
            row = result.fetchone()
            next_idx = row[0] if row else 0

            for item in messages:
                if len(item) == 3:
                    role, content, meta_extra = item[0], item[1], item[2]
                    reasoning = None
                else:
                    role, content, meta_extra, reasoning = item[0], item[1], item[2], item[3]
                metadata = dict(meta_extra or {})
                await session.execute(
                    text(
                        """
                        INSERT INTO memory_messages (callsign, idx, role, content, reasoning, metadata)
                        VALUES (:callsign, :idx, :role, :content, :reasoning, :metadata)
                        """
                    ),
                    {
                        "callsign": callsign,
                        "idx": next_idx,
                        "role": role,
                        "content": content,
                        "reasoning": reasoning,
                        "metadata": metadata,
                    },
                )
                next_idx += 1
            await session.commit()

    async def load_daily_summaries(
        self, callsign: str, days: int = 7
    ) -> list[dict[str, str]]:
        """Load the most recent N daily summaries for a callsign."""
        callsign = _normalize_callsign(callsign)
        async with self.async_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT summary_date, content
                    FROM memory_daily_summaries
                    WHERE callsign = :callsign
                    ORDER BY summary_date DESC
                    LIMIT :days
                    """
                ),
                {"callsign": callsign, "days": days},
            )
            rows = result.fetchall()
        return [
            {"summary_date": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]), "content": row[1]}
            for row in rows
        ]

    async def upsert_daily_summary(
        self, callsign: str, summary_date: str, content: str
    ) -> dict[str, Any]:
        """Write or overwrite the summary for a given date."""
        callsign = _normalize_callsign(callsign)
        async with self.async_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO memory_daily_summaries (callsign, summary_date, content, updated_at)
                    VALUES (:callsign, CAST(:summary_date AS date), :content, NOW())
                    ON CONFLICT (callsign, summary_date) DO UPDATE SET
                        content = EXCLUDED.content,
                        updated_at = NOW()
                    """
                ),
                {"callsign": callsign, "summary_date": summary_date, "content": content},
            )
            await session.commit()
        return {"callsign": callsign, "summary_date": summary_date, "content": content}

    async def get_callsigns_with_activity_since(
        self, since: datetime, until: datetime | None = None
    ) -> list[str]:
        """Get callsigns that have messages since (and optionally until) the given datetime."""
        params: dict[str, Any] = {"since": since}
        until_clause = "AND created_at < :until" if until else ""
        if until:
            params["until"] = until
        async with self.async_session() as session:
            result = await session.execute(
                text(
                    f"""
                    SELECT DISTINCT callsign
                    FROM memory_messages
                    WHERE created_at >= :since {until_clause}
                    """
                ),
                params,
            )
            rows = result.fetchall()
        return [r[0] for r in rows]

    async def close(self) -> None:
        """Close database connections."""
        await self.engine.dispose()
