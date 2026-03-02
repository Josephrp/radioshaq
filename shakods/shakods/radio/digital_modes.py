"""FLDIGI digital modes interface via XML-RPC."""

from __future__ import annotations

import asyncio
import xmlrpc.client
from dataclasses import dataclass

from loguru import logger


@dataclass
class DigitalTransmission:
    """Digital mode transmission configuration."""

    mode: str
    frequency: float
    text: str
    rsid: bool = True


class FLDIGIInterface:
    """
    Interface to FLDIGI digital modem software via XML-RPC.

    FLDIGI must be running with XML-RPC server enabled (default port 7362).
    """

    def __init__(self, host: str = "localhost", port: int = 7362):
        self.host = host
        self.port = port
        self._proxy: xmlrpc.client.ServerProxy | None = None
        self._connected = False

    async def connect(self) -> None:
        """Connect to FLDIGI XML-RPC server."""
        url = f"http://{self.host}:{self.port}/RPC2"
        self._proxy = xmlrpc.client.ServerProxy(url, allow_none=True)
        try:
            version = await asyncio.to_thread(self._proxy.main.get_version)
            self._connected = True
            logger.info("Connected to FLDIGI at %s (version: %s)", url, version)
        except Exception as e:
            self._proxy = None
            raise ConnectionError(f"Failed to connect to FLDIGI at {url}: {e}") from e

    async def set_modem(self, mode: str) -> None:
        """Set digital modem mode (PSK31, RTTY, FT8, etc.)."""
        if not self._proxy:
            raise RuntimeError("Not connected to FLDIGI")
        await asyncio.to_thread(self._proxy.modem.set_by_name, mode)
        logger.debug("FLDIGI modem set to %s", mode)

    async def transmit_text(self, text: str, delay: float = 0.5) -> None:
        """Transmit text in current digital mode."""
        if not self._proxy:
            raise RuntimeError("Not connected to FLDIGI")
        await asyncio.to_thread(self._proxy.text.clear_tx)
        await asyncio.to_thread(self._proxy.text.add_tx, text)
        await asyncio.to_thread(self._proxy.main.tx)
        while await asyncio.to_thread(self._proxy.main.get_trx_status) == "tx":
            await asyncio.sleep(delay)
        await asyncio.to_thread(self._proxy.main.rx)

    async def receive_text(self, timeout: float = 10.0) -> str:
        """Receive text from digital mode."""
        if not self._proxy:
            raise RuntimeError("Not connected to FLDIGI")
        loop = asyncio.get_running_loop()
        start = loop.time()
        received = ""
        while (loop.time() - start) < timeout:
            rx_data = await asyncio.to_thread(self._proxy.text.get_rx)
            if rx_data and rx_data != received:
                received = rx_data
                if await asyncio.to_thread(self._proxy.main.get_trx_status) == "rx":
                    break
            await asyncio.sleep(0.1)
        return received

    def get_trx_status(self) -> str:
        """Get current TX/RX status (sync, for quick checks)."""
        if not self._proxy:
            return "unknown"
        return self._proxy.main.get_trx_status()
