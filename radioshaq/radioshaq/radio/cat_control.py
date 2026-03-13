"""CAT (Computer Aided Transceiver) control via hamlib or rigctld daemon."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from loguru import logger

from radioshaq.radio.modes import hamlib_mode_for

# Optional: pyhamlib for direct control (requires system hamlib)
try:
    import hamlib
    HAS_HAMLIB = True
except ImportError:
    HAS_HAMLIB = False
    hamlib = None  # type: ignore


@dataclass
class RigState:
    """Current state of a radio rig."""

    frequency: float
    mode: str
    ptt: bool
    signal_strength: int = 0
    bandwidth: int = 0


class HamlibCATControl:
    """
    CAT control via hamlib or rigctld daemon.

    When use_daemon=True, connects to rigctld via TCP (no pyhamlib required).
    When use_daemon=False, uses pyhamlib for direct serial control.
    """

    def __init__(
        self,
        rig_model: int = 1,
        port: str = "/dev/ttyUSB0",
        use_daemon: bool = False,
        daemon_host: str = "localhost",
        daemon_port: int = 4532,
    ):
        self.rig_model = rig_model
        self.port = port
        self.use_daemon = use_daemon
        self.daemon_host = daemon_host
        self.daemon_port = daemon_port
        self._rig: Any = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._connected = False

    async def connect(self) -> None:
        """Establish connection to radio."""
        if self.use_daemon:
            await self._connect_to_daemon()
        else:
            await self._connect_direct()

    async def _connect_to_daemon(self) -> None:
        """Connect to rigctld daemon via TCP."""
        self._reader, self._writer = await asyncio.open_connection(
            self.daemon_host,
            self.daemon_port,
        )
        self._connected = True
        logger.info(
            "Connected to rigctld at {}:{}", self.daemon_host, self.daemon_port
        )

    async def _connect_direct(self) -> None:
        """Connect directly via hamlib Python bindings."""
        if not HAS_HAMLIB:
            raise RuntimeError(
                "pyhamlib not installed. Use use_daemon=True with rigctld, "
                "or install pyhamlib and system hamlib."
            )
        await asyncio.to_thread(self._sync_connect_direct)
        self._connected = True
        logger.info("Connected to rig via hamlib on {}", self.port)

    def _sync_connect_direct(self) -> None:
        """Synchronous hamlib connect (runs in thread)."""
        self._rig = hamlib.Rig(self.rig_model)
        self._rig.set_conf("rig_pathname", self.port)
        self._rig.open()

    async def disconnect(self) -> None:
        """Close connection."""
        if self.use_daemon and self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._reader = None
            self._writer = None
        elif not self.use_daemon and self._rig and HAS_HAMLIB:
            await asyncio.to_thread(self._rig.close)
            self._rig = None
        self._connected = False

    async def _send_daemon_command(self, cmd: str) -> str:
        """Send command to rigctld and return response."""
        if not self._writer or not self._reader:
            raise RuntimeError("Not connected to rigctld")
        self._writer.write((cmd + "\n").encode())
        await self._writer.drain()
        line = await self._reader.readline()
        return line.decode().strip()

    async def _query_daemon(self, cmd: str) -> str:
        """Query rigctld (single-char commands like f, m, t)."""
        return await self._send_daemon_command(cmd)

    async def set_frequency(self, frequency_hz: float) -> None:
        """Set radio frequency in Hz."""
        async with self._lock:
            if self.use_daemon:
                await self._send_daemon_command(f"F {int(frequency_hz)}")
            elif self._rig and HAS_HAMLIB:
                await asyncio.to_thread(
                    self._rig.set_freq, hamlib.RIG_VFO_CURR, int(frequency_hz)
                )

    async def set_ptt(self, state: bool) -> None:
        """Set PTT (Push-to-Talk) state."""
        async with self._lock:
            if self.use_daemon:
                cmd = "T 1" if state else "T 0"
                await self._send_daemon_command(cmd)
            elif self._rig and HAS_HAMLIB:
                ptt_state = hamlib.RIG_PTT_ON if state else hamlib.RIG_PTT_OFF
                await asyncio.to_thread(
                    self._rig.set_ptt, hamlib.RIG_VFO_CURR, ptt_state
                )

    async def set_mode(self, mode: str) -> None:
        """Set radio mode."""
        mode_str = hamlib_mode_for(mode)
        async with self._lock:
            if self.use_daemon:
                await self._send_daemon_command(f"M {mode_str} 0")
            elif self._rig and HAS_HAMLIB:
                mode_id = getattr(hamlib, f"RIG_MODE_{mode_str}", hamlib.RIG_MODE_FM)
                await asyncio.to_thread(
                    self._rig.set_mode, mode_id, hamlib.RIG_VFO_CURR
                )

    async def get_state(self) -> RigState:
        """Get current rig state."""
        async with self._lock:
            if self.use_daemon:
                freq_str = await self._query_daemon("f")
                mode_str = await self._query_daemon("m")
                ptt_str = await self._query_daemon("t")
                mode_val = mode_str.split()[0] if mode_str else "FM"
                return RigState(
                    frequency=float(freq_str) if freq_str else 0.0,
                    mode=mode_val,
                    ptt=ptt_str.strip() == "1" if ptt_str else False,
                    signal_strength=0,
                    bandwidth=0,
                )
            elif self._rig and HAS_HAMLIB:
                freq = await asyncio.to_thread(
                    self._rig.get_freq, hamlib.RIG_VFO_CURR
                )
                mode_data = await asyncio.to_thread(
                    self._rig.get_mode, hamlib.RIG_VFO_CURR
                )
                mode_str = mode_data[0] if mode_data else "FM"
                return RigState(
                    frequency=freq,
                    mode=mode_str,
                    ptt=False,
                    signal_strength=0,
                    bandwidth=0,
                )
        return RigState(frequency=0.0, mode="FM", ptt=False)
