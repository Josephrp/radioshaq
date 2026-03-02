"""Vendored dependencies from nanobot and vibe projects."""

# Re-export key components for convenient access
from shakods.vendor.nanobot.bus.events import InboundMessage, OutboundMessage
from shakods.vendor.nanobot.bus.queue import MessageBus
from shakods.vendor.nanobot.tools.registry import ToolRegistry
from shakods.vendor.vibe.middleware import (
    ConversationContext,
    MiddlewareAction,
    MiddlewarePipeline,
    MiddlewareResult,
)

__all__ = [
    "InboundMessage",
    "OutboundMessage",
    "MessageBus",
    "ToolRegistry",
    "ConversationContext",
    "MiddlewareAction",
    "MiddlewarePipeline",
    "MiddlewareResult",
]
