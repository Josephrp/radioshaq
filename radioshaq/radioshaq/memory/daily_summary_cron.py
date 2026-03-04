"""End-of-day cron: generate daily summaries for active callsigns at midnight EST."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from loguru import logger

from radioshaq.config.resolve import get_llm_config_for_role
from radioshaq.config.schema import Config
from radioshaq.llm.client import LLMClient
from radioshaq.orchestrator.factory import _llm_api_key_from_llm_config, _llm_model_string_from_llm_config

DEFAULT_TZ = ZoneInfo("America/New_York")
SUMMARY_PROMPT = """You are summarizing a day's conversation between a ham radio operator and SHAKODS (an AI assistant for ham radio operations).

Below are the messages from this operator's conversation today. Write a concise daily summary (3-8 sentences) covering:
- Key topics discussed
- Tasks or requests handled
- Anything worth remembering for future context

Be factual and concise. Write in third person ("The operator asked...", "SHAKODS helped...").

Messages:
{messages}

Daily summary:"""


async def run_daily_summary_job(
    memory_manager: "MemoryManager",
    llm_client: LLMClient,
    *,
    summary_date: date | None = None,
    timezone: ZoneInfo = DEFAULT_TZ,
) -> int:
    """
    For each callsign with activity on summary_date, generate and save a daily summary.
    Returns count of summaries written.
    """
    from radioshaq.memory.manager import MemoryManager

    if summary_date is None:
        summary_date = (datetime.now(timezone) - timedelta(days=1)).date()

    since = datetime.combine(summary_date, datetime.min.time(), tzinfo=timezone)
    until = since + timedelta(days=1)

    callsigns = await memory_manager.get_callsigns_with_activity_since(since, until=until)
    written = 0
    for callsign in callsigns:
        try:
            msgs = await memory_manager.load_messages(
                callsign,
                limit=500,
                since=since,
                until=until,
                max_tokens=50000,
            )
            if not msgs:
                continue

            # Format for LLM
            lines = []
            for m in msgs:
                role = m.get("role", "unknown")
                content = (m.get("content") or "").strip()
                if content:
                    lines.append(f"[{role}]: {content[:500]}")
            if not lines:
                continue
            messages_text = "\n".join(lines[-50:])  # Last 50 to avoid token limit

            response = await llm_client.chat(
                messages=[
                    {"role": "user", "content": SUMMARY_PROMPT.format(messages=messages_text)},
                ],
                temperature=0.2,
                max_tokens=512,
            )
            summary = (response.content or "").strip()
            if not summary:
                continue

            await memory_manager.upsert_daily_summary(
                callsign,
                summary_date.isoformat(),
                summary,
            )
            written += 1
            logger.info("Daily summary written for %s (%s)", callsign, summary_date)
        except Exception as e:
            logger.warning("Daily summary failed for %s: %s", callsign, e)

    return written


async def run_midnight_cron_loop(
    memory_manager: "MemoryManager",
    config: Config,
    *,
    timezone: ZoneInfo = DEFAULT_TZ,
    stop_event: asyncio.Event | None = None,
) -> None:
    """
    Background loop: sleep until next midnight, run daily summary job, repeat.
    """
    from radioshaq.memory.manager import MemoryManager
    from radioshaq.llm.client import LLMClient

    llm_cfg = get_llm_config_for_role(config, "daily_summary")
    model = _llm_model_string_from_llm_config(llm_cfg)
    api_key = _llm_api_key_from_llm_config(llm_cfg)
    api_base = getattr(llm_cfg, "custom_api_base", None)
    llm = LLMClient(model=model, api_key=api_key, api_base=api_base, temperature=0.2, max_tokens=512)

    while True:
        now = datetime.now(timezone)
        # Next midnight
        next_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        wait_seconds = (next_midnight - now).total_seconds()
        logger.info(
            "Daily summary cron: next run at %s (in %.0f s)",
            next_midnight,
            wait_seconds,
        )

        if stop_event:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=wait_seconds)
            except asyncio.TimeoutError:
                pass
            if stop_event.is_set():
                break
        else:
            await asyncio.sleep(min(wait_seconds, 3600))  # Cap at 1h for responsiveness

        if stop_event and stop_event.is_set():
            break

        # Run for yesterday
        yesterday = (datetime.now(timezone) - timedelta(days=1)).date()
        try:
            n = await run_daily_summary_job(
                memory_manager,
                llm,
                summary_date=yesterday,
                timezone=timezone,
            )
            logger.info("Daily summary cron: wrote %d summaries for %s", n, yesterday)
        except Exception as e:
            logger.exception("Daily summary cron failed: %s", e)
