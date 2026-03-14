"""HQ client for authenticated uploads."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from loguru import logger


class HQClient:
    """Upload receiver data to RadioShaq HQ with JWT."""

    def __init__(
        self,
        base_url: str,
        token: str,
        station_id: str,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.station_id = station_id
        self.upload_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def connect(self) -> None:
        """Validate connection to HQ (optional health check)."""
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{self.base_url}/health",
                    timeout=5.0,
                )
                if r.status_code == 200:
                    logger.info("HQ connection OK")
        except Exception as e:
            logger.warning("HQ connect check failed: {}", e)

    async def upload(self, packet: dict[str, Any]) -> bool:
        """Upload a single packet to HQ."""
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{self.base_url}/receiver/upload",
                    json=packet,
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=10.0,
                )
                return r.status_code in (200, 201)
        except Exception as e:
            logger.warning("HQ upload failed: {}", e)
            return False
