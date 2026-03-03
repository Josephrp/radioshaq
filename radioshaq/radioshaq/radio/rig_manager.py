"""Rig manager for multiple radio rigs."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from radioshaq.radio.cat_control import HamlibCATControl, RigMode, RigState


class RigManager:
    """
    Manages multiple radio rigs with CAT control.

    Supports selecting and controlling one rig at a time from a pool.
    """

    def __init__(self) -> None:
        self._rigs: dict[str, HamlibCATControl] = {}
        self._active_rig: str | None = None
        self._lock = asyncio.Lock()

    def register_rig(self, name: str, cat: HamlibCATControl) -> None:
        """Register a rig by name."""
        self._rigs[name] = cat
        if self._active_rig is None:
            self._active_rig = name
        logger.debug("Registered rig %s", name)

    def unregister_rig(self, name: str) -> None:
        """Remove a rig."""
        if name in self._rigs:
            del self._rigs[name]
            if self._active_rig == name:
                self._active_rig = next(iter(self._rigs)) if self._rigs else None

    def get_rig(self, name: str | None = None) -> HamlibCATControl | None:
        """Get rig by name, or active rig if name is None."""
        if name:
            return self._rigs.get(name)
        return self._rigs.get(self._active_rig) if self._active_rig else None

    def set_active_rig(self, name: str) -> None:
        """Set the active rig for operations."""
        if name not in self._rigs:
            raise ValueError(f"Unknown rig: {name}")
        self._active_rig = name

    async def connect_all(self) -> None:
        """Connect all registered rigs."""
        for name, rig in self._rigs.items():
            try:
                await rig.connect()
            except Exception as e:
                logger.warning("Failed to connect rig %s: %s", name, e)

    async def set_frequency(self, frequency_hz: float, rig_name: str | None = None) -> None:
        """Set frequency on active or specified rig."""
        rig = self.get_rig(rig_name)
        if not rig:
            raise RuntimeError("No rig available")
        async with self._lock:
            await rig.set_frequency(frequency_hz)

    async def set_ptt(self, state: bool, rig_name: str | None = None) -> None:
        """Set PTT on active or specified rig."""
        rig = self.get_rig(rig_name)
        if not rig:
            raise RuntimeError("No rig available")
        async with self._lock:
            await rig.set_ptt(state)

    async def set_mode(self, mode: RigMode | str, rig_name: str | None = None) -> None:
        """Set mode on active or specified rig."""
        rig = self.get_rig(rig_name)
        if not rig:
            raise RuntimeError("No rig available")
        async with self._lock:
            await rig.set_mode(mode)

    async def get_state(self, rig_name: str | None = None) -> RigState | None:
        """Get state of active or specified rig."""
        rig = self.get_rig(rig_name)
        if not rig:
            return None
        async with self._lock:
            return await rig.get_state()

    async def is_ptt_active(self, rig_name: str | None = None) -> bool:
        """Return True if PTT is currently active on the rig."""
        state = await self.get_state(rig_name)
        return state.ptt if state else False

    def list_rigs(self) -> list[str]:
        """List registered rig names."""
        return list(self._rigs.keys())
