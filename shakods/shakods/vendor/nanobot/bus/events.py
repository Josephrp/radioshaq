"""Event types for the message bus (vendored from nanobot).

This module defines the core message types used for communication
between channels and the orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class InboundMessage:
    """Message received from a chat channel or external source.
    
    Attributes:
        channel: Source channel (whatsapp, sms, radio, system, etc.)
        sender_id: User identifier (phone number, callsign, etc.)
        chat_id: Chat/channel identifier
        content: Message text
        timestamp: When message was received
        media: Media URLs or data
        metadata: Channel-specific data (frequency, signal strength, etc.)
        session_key_override: Optional session key override
    """
    
    channel: str  # whatsapp, sms, radio_rx, radio_tx, system, cli
    sender_id: str  # User identifier (phone, callsign, etc.)
    chat_id: str  # Chat/channel identifier
    content: str  # Message text
    timestamp: datetime = field(default_factory=datetime.now)
    media: list[str] = field(default_factory=list)  # Media URLs
    metadata: dict[str, Any] = field(default_factory=dict)  # Channel-specific data
    session_key_override: str | None = None  # Optional session key
    
    @property
    def session_key(self) -> str:
        """Unique key for session identification."""
        return self.session_key_override or f"{self.channel}:{self.chat_id}"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "channel": self.channel,
            "sender_id": self.sender_id,
            "chat_id": self.chat_id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "media": self.media,
            "metadata": self.metadata,
            "session_key": self.session_key,
        }


@dataclass
class OutboundMessage:
    """Message to send to a chat channel or external destination.
    
    Attributes:
        channel: Destination channel
        chat_id: Target chat/channel identifier
        content: Message text
        reply_to: Message ID to reply to
        media: Media attachments
        metadata: Channel-specific metadata
    """
    
    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "channel": self.channel,
            "chat_id": self.chat_id,
            "content": self.content,
            "reply_to": self.reply_to,
            "media": self.media,
            "metadata": self.metadata,
        }


@dataclass
class SystemMessage:
    """Internal system message for orchestrator coordination."""
    
    message_type: str  # task_complete, upstream_event, error, etc.
    source: str  # Component that sent the message
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 5  # 1-10, lower = higher priority
