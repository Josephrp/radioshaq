"""Build memory context for REACT orchestrator.

Assembles: core blocks (user, identity, ideaspace, system_instructions) +
daily summaries (last 7) + conversation history (today OR last N, whichever wider).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

from radioshaq.memory.manager import (
    MemoryManager,
    RECENT_MESSAGES_LIMIT,
    CONTEXT_WINDOW_TOKENS,
    DEFAULT_TIMEZONE,
)


def _format_current_time(dt: datetime) -> str:
    """Format datetime for agent awareness."""
    return dt.strftime("%A, %B %d, %Y at %I:%M %p %Z")


async def build_memory_context(
    memory: MemoryManager,
    callsign: str,
    *,
    current_time: datetime | None = None,
    recent_limit: int = RECENT_MESSAGES_LIMIT,
    summary_days: int = 7,
    max_tokens: int = CONTEXT_WINDOW_TOKENS,
    timezone: ZoneInfo = DEFAULT_TIMEZONE,
) -> dict[str, Any]:
    """
    Build full memory context for a callsign.

    Returns dict with:
    - system_prefix: str - Core blocks + summaries to prepend to system prompt
    - messages: list[dict] - Recent conversation turns (role, content, ...)
    - metadata: dict - callsign, current_time, etc.
    """
    return await _build_async(memory, callsign, current_time, recent_limit, summary_days, max_tokens, timezone)


async def _build_async(
    memory: MemoryManager,
    callsign: str,
    current_time: datetime | None,
    recent_limit: int,
    summary_days: int,
    max_tokens: int,
    tz: ZoneInfo,
) -> dict[str, Any]:
    """Internal async builder."""
    if current_time is None:
        current_time = datetime.now(tz)

    # Load all in parallel
    blocks_task = memory.get_core_blocks(callsign)
    today_midnight = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    messages_task = memory.load_messages(
        callsign,
        limit=recent_limit,
        since=today_midnight,
        max_tokens=max_tokens,
    )
    summaries_task = memory.load_daily_summaries(callsign, days=summary_days)

    blocks = await blocks_task
    messages = await messages_task
    summaries = await summaries_task

    # Build system prefix
    parts = []
    parts.append(f"# Current Time\n\nIt is currently: {_format_current_time(current_time)}\n\n---\n\n")

    # System instructions (read-only)
    sys_instr = blocks.get("system_instructions", "").strip()
    if sys_instr:
        parts.append("# System Instructions (READ ONLY)\n\n")
        parts.append(sys_instr)
        parts.append("\n\n---\n\n")

    # Core memory (editable)
    parts.append("# Core Memory (editable)\n\nThese blocks are always in context.\n")
    for name, label in [("user", "User"), ("identity", "Identity"), ("ideaspace", "Ideaspace")]:
        content = blocks.get(name, "").strip()
        parts.append(f"## {label}\n{content or '(empty)'}\n")
    parts.append("\n---\n\n")

    # Daily summaries
    if summaries:
        parts.append("# Recent Days (daily summaries)\n\n")
        for s in reversed(summaries):
            parts.append(f"**{s['summary_date']}**: {s['content']}\n\n")
        parts.append("---\n\n")

    system_prefix = "\n".join(parts)

    return {
        "system_prefix": system_prefix,
        "messages": messages,
        "metadata": {
            "callsign": callsign.upper(),
            "current_time": current_time.isoformat(),
            "message_count": len(messages),
            "summary_count": len(summaries),
        },
    }
