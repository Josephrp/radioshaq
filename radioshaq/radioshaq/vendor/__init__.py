"""Vendored dependencies from nanobot and vibe projects."""

# Re-export key components for convenient access
from radioshaq.vendor.nanobot.bus.events import InboundMessage, OutboundMessage
from radioshaq.vendor.nanobot.bus.queue import MessageBus
from radioshaq.vendor.nanobot.tools.registry import ToolRegistry
from radioshaq.vendor.vibe.middleware import (
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
