"""Per-callsign memory system for RadioShaq.

Provides:
- Core memory blocks (user, identity, ideaspace) - always in context
- Conversation history (last N turns + today, whichever is wider)
- Daily summaries (last 7 in context)
- Hindsight integration (retain, recall, reflect) per callsign bank
"""

from radioshaq.memory.context_builder import build_memory_context
from radioshaq.memory.manager import MemoryManager
from radioshaq.memory.hindsight import aretain_exchange, recall, reflect, retain_exchange

__all__ = [
    "MemoryManager",
    "aretain_exchange",
    "build_memory_context",
    "recall",
    "reflect",
    "retain_exchange",
]
