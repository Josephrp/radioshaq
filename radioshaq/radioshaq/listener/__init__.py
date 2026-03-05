"""Background listeners: band listener, voice listener, relay delivery."""

from radioshaq.listener.band_listener import run_band_listener

__all__ = ["run_band_listener", "run_relay_delivery_worker", "run_voice_listener"]


def __getattr__(name: str):
    """Lazy-import relay_delivery and voice_listener so band_listener can be imported alone (e.g. in tests)."""
    if name == "run_relay_delivery_worker":
        from radioshaq.listener.relay_delivery import run_relay_delivery_worker
        return run_relay_delivery_worker
    if name == "run_voice_listener":
        from radioshaq.listener.voice_listener import run_voice_listener
        return run_voice_listener
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
