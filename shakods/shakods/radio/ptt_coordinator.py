"""PTT coordination for half-duplex operation.

This module provides safety-critical coordination for radio transmissions,
preventing keying over existing transmissions and managing half-duplex state.
"""

from __future__ import annotations

import asyncio
from enum import Enum, auto
from typing import Any, Awaitable, Callable

from loguru import logger


class RadioState(Enum):
    """Radio state machine for half-duplex coordination."""

    RX = auto()  # Receiving
    RX_PROCESSING = auto()  # Processing received audio
    TX_PENDING = auto()  # Response queued, awaiting confirmation
    TX_ACTIVE = auto()  # Currently transmitting
    TX_COOLDOWN = auto()  # Post-transmission cooldown


class PTTCoordinator:
    """
    Coordinates PTT state to prevent keying over existing transmissions
    and manages half-duplex state machine.

    This is a safety-critical component that ensures:
    1. We never transmit while someone else is transmitting
    2. We respect cooldown periods between transmissions
    3. Operators can emergency break-in to abort automated transmissions

    Example:
        coordinator = PTTCoordinator(rig_manager, cooldown_ms=500)

        # Request permission to transmit
        if await coordinator.request_transmit():
            await coordinator.begin_transmit()
            # ... transmit audio ...
            await coordinator.end_transmit()

        # Emergency break-in (operator manually keys PTT)
        await coordinator.break_in()
    """

    def __init__(
        self,
        rig_manager: Any,
        cooldown_ms: int = 500,
        break_in_enabled: bool = True,
        max_wait_seconds: float = 5.0,
    ):
        """
        Initialize PTT coordinator.

        Args:
            rig_manager: Rig manager with is_ptt_active() and set_ptt() methods
            cooldown_ms: Cooldown period after transmission in milliseconds
            break_in_enabled: Whether emergency break-in is allowed
            max_wait_seconds: Maximum time to wait for channel clearance
        """
        self.rig_manager = rig_manager
        self.cooldown_ms = cooldown_ms
        self.break_in_enabled = break_in_enabled
        self.max_wait_seconds = max_wait_seconds

        self._state = RadioState.RX
        self._state_lock = asyncio.Lock()
        self._break_in_event = asyncio.Event()
        self._state_change_callbacks: list[Callable[[RadioState, RadioState], Awaitable[None]]] = []

    async def get_state(self) -> RadioState:
        """Get current radio state."""
        async with self._state_lock:
            return self._state

    def add_state_change_callback(
        self,
        callback: Callable[[RadioState, RadioState], Awaitable[None]],
    ) -> None:
        """
        Add callback for state changes.

        Args:
            callback: Async function called with (old_state, new_state)
        """
        self._state_change_callbacks.append(callback)

    def remove_state_change_callback(
        self,
        callback: Callable[[RadioState, RadioState], Awaitable[None]],
    ) -> None:
        """Remove a state change callback."""
        if callback in self._state_change_callbacks:
            self._state_change_callbacks.remove(callback)

    async def _transition_state(self, new_state: RadioState) -> None:
        """Transition to new state and notify callbacks."""
        async with self._state_lock:
            old_state = self._state
            if old_state != new_state:
                self._state = new_state
                logger.info(f"Radio state: {old_state.name} -> {new_state.name}")

        # Notify callbacks outside lock to prevent deadlocks
        if old_state != new_state:
            for callback in self._state_change_callbacks:
                try:
                    await callback(old_state, new_state)
                except Exception as e:
                    logger.exception(f"State change callback error: {e}")

    async def request_transmit(self) -> bool:
        """
        Request permission to transmit.

        Returns:
            True if transmission is permitted, False if denied.
            Denial can occur due to:
            - Already transmitting
            - Channel busy (PTT active from another station)
            - RX processing in progress (will wait briefly)
        """
        current_state = await self.get_state()

        if current_state in (RadioState.TX_ACTIVE, RadioState.TX_PENDING):
            logger.warning("TX request denied: already transmitting")
            return False

        if current_state == RadioState.RX_PROCESSING:
            logger.info("TX requested while processing RX, waiting...")
            try:
                await asyncio.wait_for(
                    self._wait_for_state(RadioState.RX),
                    timeout=self.max_wait_seconds,
                )
            except asyncio.TimeoutError:
                logger.warning("TX request denied: RX processing timeout")
                return False

        # Check if PTT is active (someone else transmitting)
        if self.rig_manager and await self._is_ptt_active():
            logger.warning("TX request denied: channel busy (PTT active)")
            return False

        await self._transition_state(RadioState.TX_PENDING)
        return True

    async def begin_transmit(self) -> bool:
        """
        Begin actual transmission (set PTT).

        Returns:
            True if PTT was activated, False if not in TX_PENDING state
        """
        current_state = await self.get_state()
        if current_state != RadioState.TX_PENDING:
            logger.error(f"Cannot begin transmit from state: {current_state.name}")
            return False

        # Final check before keying
        if self.rig_manager and await self._is_ptt_active():
            logger.error("TX begin aborted: channel became busy")
            await self._transition_state(RadioState.RX)
            return False

        if self.rig_manager:
            await self.rig_manager.set_ptt(True)

        await self._transition_state(RadioState.TX_ACTIVE)
        logger.info("PTT activated - transmission started")
        return True

    async def end_transmit(self) -> None:
        """End transmission (release PTT) and enter cooldown."""
        current_state = await self.get_state()

        if current_state == RadioState.TX_ACTIVE:
            if self.rig_manager:
                await self.rig_manager.set_ptt(False)
            logger.info("PTT released - transmission ended")

        await self._transition_state(RadioState.TX_COOLDOWN)

        # Start cooldown task
        asyncio.create_task(self._cooldown_task())

    async def break_in(self) -> bool:
        """
        Emergency break-in: cancel any pending/processing transmission.

        Called when operator manually keys PTT or needs to abort
        an automated transmission.

        Returns:
            True if break-in was executed, False if not enabled or nothing to break
        """
        if not self.break_in_enabled:
            logger.debug("Break-in attempted but not enabled")
            return False

        current_state = await self.get_state()

        if current_state in (RadioState.TX_ACTIVE, RadioState.TX_PENDING):
            if current_state == RadioState.TX_ACTIVE and self.rig_manager:
                await self.rig_manager.set_ptt(False)
                logger.warning("Break-in: PTT released")

            await self._transition_state(RadioState.RX)
            self._break_in_event.set()
            self._break_in_event.clear()  # Reset for next use
            logger.warning("Break-in activated by operator - transmission aborted")
            return True

        return False

    async def wait_for_break_in(self, timeout: float | None = None) -> bool:
        """
        Wait for a break-in event.

        Args:
            timeout: Maximum time to wait (None = forever)

        Returns:
            True if break-in occurred, False if timeout
        """
        try:
            await asyncio.wait_for(self._break_in_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def force_rx_state(self) -> None:
        """Force state back to RX (use with caution)."""
        async with self._state_lock:
            old_state = self._state
            self._state = RadioState.RX

        if old_state != RadioState.RX:
            for callback in self._state_change_callbacks:
                try:
                    await callback(old_state, RadioState.RX)
                except Exception as e:
                    logger.exception(f"State change callback error: {e}")

    async def _is_ptt_active(self) -> bool:
        """Check if PTT is currently active."""
        if not self.rig_manager:
            return False
        try:
            return await self.rig_manager.is_ptt_active()
        except Exception as e:
            logger.warning(f"Failed to check PTT status: {e}")
            return False

    async def _cooldown_task(self) -> None:
        """Cooldown period after transmission."""
        await asyncio.sleep(self.cooldown_ms / 1000)

        current_state = await self.get_state()
        if current_state == RadioState.TX_COOLDOWN:
            await self._transition_state(RadioState.RX)
            logger.debug("TX cooldown complete - ready for RX")

    async def _wait_for_state(self, target_state: RadioState) -> None:
        """Wait for radio to reach target state."""
        while True:
            current = await self.get_state()
            if current == target_state:
                return
            await asyncio.sleep(0.05)

    def get_status(self) -> dict[str, Any]:
        """Get current coordinator status for monitoring."""
        return {
            "state": self._state.name,
            "cooldown_ms": self.cooldown_ms,
            "break_in_enabled": self.break_in_enabled,
            "max_wait_seconds": self.max_wait_seconds,
        }


class PTTGuard:
    """
    Async context manager for safe PTT operations.

    Example:
        async with PTTGuard(coordinator) as guard:
            if guard.permitted:
                # Transmit audio
                await play_audio(audio_data)
            else:
                # Handle denial
                logger.warning("Transmission not permitted")
    """

    def __init__(
        self,
        coordinator: PTTCoordinator,
        auto_release: bool = True,
    ):
        self.coordinator = coordinator
        self.auto_release = auto_release
        self.permitted = False
        self._started = False

    async def __aenter__(self) -> PTTGuard:
        """Request transmit permission on enter."""
        self.permitted = await self.coordinator.request_transmit()
        if self.permitted:
            self.permitted = await self.coordinator.begin_transmit()
            self._started = self.permitted
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """End transmission on exit."""
        if self._started and self.auto_release:
            await self.coordinator.end_transmit()


class ChannelMonitor:
    """
    Monitors channel activity and triggers callbacks.

    Useful for detecting when channel becomes busy/free
    and implementing channel access protocols.
    """

    def __init__(
        self,
        rig_manager: Any,
        check_interval_ms: float = 100.0,
    ):
        self.rig_manager = rig_manager
        self.check_interval_ms = check_interval_ms
        self._busy_callbacks: list[Callable[[], Awaitable[None]]] = []
        self._free_callbacks: list[Callable[[], Awaitable[None]]] = []
        self._monitoring = False
        self._monitor_task: asyncio.Task[None] | None = None
        self._last_state: bool | None = None

    def on_channel_busy(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Register callback for when channel becomes busy."""
        self._busy_callbacks.append(callback)

    def on_channel_free(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Register callback for when channel becomes free."""
        self._free_callbacks.append(callback)

    async def start_monitoring(self) -> None:
        """Start monitoring channel state."""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Channel monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop monitoring channel state."""
        self._monitoring = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Channel monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring:
            try:
                current_state = False
                if self.rig_manager:
                    current_state = await self.rig_manager.is_ptt_active()

                if self._last_state is not None and current_state != self._last_state:
                    if current_state:
                        # Channel became busy
                        for callback in self._busy_callbacks:
                            try:
                                await callback()
                            except Exception as e:
                                logger.exception(f"Channel busy callback error: {e}")
                    else:
                        # Channel became free
                        for callback in self._free_callbacks:
                            try:
                                await callback()
                            except Exception as e:
                                logger.exception(f"Channel free callback error: {e}")

                self._last_state = current_state

            except Exception as e:
                logger.exception(f"Channel monitor error: {e}")

            await asyncio.sleep(self.check_interval_ms / 1000)
