"""Message bus queue implementation (vendored from nanobot).

Provides async message queuing for inbound and outbound messages
between channels and the orchestrator.
"""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Any

from loguru import logger

from shakods.vendor.nanobot.bus.events import InboundMessage, OutboundMessage, SystemMessage


class MessageBus:
    """Async message bus for routing messages between components.
    
    This implements a pub/sub pattern with separate queues for:
    - Inbound messages (from channels to orchestrator)
    - Outbound messages (from orchestrator to channels)
    - System messages (internal coordination)
    
    Example:
        bus = MessageBus()
        
        # Publish inbound message
        await bus.publish_inbound(InboundMessage(...))
        
        # Consume in orchestrator
        msg = await bus.consume_inbound()
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        inbound_timeout: float | None = None,
        outbound_timeout: float | None = None,
    ):
        self._inbound: asyncio.Queue[InboundMessage] = asyncio.Queue(maxsize=max_size)
        self._outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue(maxsize=max_size)
        self._system: asyncio.Queue[SystemMessage] = asyncio.Queue(maxsize=max_size)
        self._inbound_timeout = inbound_timeout
        self._outbound_timeout = outbound_timeout
        self._stats = {
            "inbound_published": 0,
            "inbound_consumed": 0,
            "outbound_published": 0,
            "outbound_consumed": 0,
            "system_published": 0,
            "system_consumed": 0,
            "dropped": 0,
        }
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
    
    async def publish_inbound(self, message: InboundMessage) -> bool:
        """Publish an inbound message.
        
        Args:
            message: The inbound message to publish
            
        Returns:
            True if published successfully, False if queue full
        """
        try:
            self._inbound.put_nowait(message)
            self._stats["inbound_published"] += 1
            
            # Notify subscribers
            for queue in self._subscribers.get("inbound", []):
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    pass
                    
            logger.debug(f"Published inbound message from {message.channel}:{message.sender_id}")
            return True
        except asyncio.QueueFull:
            self._stats["dropped"] += 1
            logger.warning(f"Inbound queue full, dropping message from {message.channel}")
            return False
    
    async def consume_inbound(self) -> InboundMessage:
        """Consume an inbound message.
        
        Returns:
            The next inbound message
            
        Raises:
            asyncio.TimeoutError: If timeout configured and no message received
        """
        if self._inbound_timeout:
            msg = await asyncio.wait_for(
                self._inbound.get(),
                timeout=self._inbound_timeout,
            )
        else:
            msg = await self._inbound.get()
            
        self._stats["inbound_consumed"] += 1
        return msg
    
    async def publish_outbound(self, message: OutboundMessage) -> bool:
        """Publish an outbound message.
        
        Args:
            message: The outbound message to publish
            
        Returns:
            True if published successfully, False if queue full
        """
        try:
            self._outbound.put_nowait(message)
            self._stats["outbound_published"] += 1
            
            # Notify subscribers
            for queue in self._subscribers.get("outbound", []):
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    pass
                    
            logger.debug(f"Published outbound message to {message.channel}:{message.chat_id}")
            return True
        except asyncio.QueueFull:
            self._stats["dropped"] += 1
            logger.warning(f"Outbound queue full, dropping message to {message.channel}")
            return False
    
    async def consume_outbound(self) -> OutboundMessage:
        """Consume an outbound message.
        
        Returns:
            The next outbound message
            
        Raises:
            asyncio.TimeoutError: If timeout configured and no message received
        """
        if self._outbound_timeout:
            msg = await asyncio.wait_for(
                self._outbound.get(),
                timeout=self._outbound_timeout,
            )
        else:
            msg = await self._outbound.get()
            
        self._stats["outbound_consumed"] += 1
        return msg
    
    async def publish_system(self, message: SystemMessage) -> bool:
        """Publish a system message for internal coordination.
        
        Args:
            message: The system message to publish
            
        Returns:
            True if published successfully
        """
        try:
            self._system.put_nowait(message)
            self._stats["system_published"] += 1
            return True
        except asyncio.QueueFull:
            self._stats["dropped"] += 1
            logger.warning("System queue full, dropping message")
            return False
    
    async def consume_system(self) -> SystemMessage:
        """Consume a system message."""
        msg = await self._system.get()
        self._stats["system_consumed"] += 1
        return msg
    
    def subscribe(self, queue_type: str, queue: asyncio.Queue) -> None:
        """Subscribe to a message type.
        
        Args:
            queue_type: 'inbound', 'outbound', or 'system'
            queue: Queue to receive messages
        """
        if queue_type not in self._subscribers:
            self._subscribers[queue_type] = []
        self._subscribers[queue_type].append(queue)
    
    def unsubscribe(self, queue_type: str, queue: asyncio.Queue) -> None:
        """Unsubscribe from a message type."""
        if queue_type in self._subscribers:
            self._subscribers[queue_type] = [
                q for q in self._subscribers[queue_type] if q is not queue
            ]
    
    def get_stats(self) -> dict[str, Any]:
        """Get message bus statistics."""
        return {
            **self._stats,
            "inbound_queue_size": self._inbound.qsize(),
            "outbound_queue_size": self._outbound.qsize(),
            "system_queue_size": self._system.qsize(),
        }
    
    def clear(self) -> None:
        """Clear all queues."""
        for queue in [self._inbound, self._outbound, self._system]:
            while not queue.empty():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
