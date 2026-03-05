"""Radio-format exit: wrap final response for voice/TTS with call signs and sign-off."""

from __future__ import annotations


def format_response_for_radio(
    message: str,
    caller_callsign: str | None = None,
    station_callsign: str | None = None,
    style: str = "over",
    max_content_words: int = 80,
) -> str:
    """
    Wrap a reply in standard radio format for voice/TTS.

    Format: "{station} de {caller} {content} Over." or "... K" when style is prosign.
    If station or caller is missing, only the content (and optional sign-off) is returned.

    Args:
        message: The core reply text (may be truncated to max_content_words).
        caller_callsign: Other station's callsign (who we're replying to).
        station_callsign: Our station callsign.
        style: "over" | "prosign" | "none".
        max_content_words: Max words from message to include (keeps radio traffic short).

    Returns:
        Formatted string suitable for TTS/radio.
    """
    if not message or not message.strip():
        message = "Standing by."
    content = message.strip()
    if max_content_words > 0:
        words = content.split()
        if len(words) > max_content_words:
            content = " ".join(words[:max_content_words])
            if not content.endswith(".") and not content.endswith("!"):
                content += "."
    station = (station_callsign or "").strip().upper() or None
    caller = (caller_callsign or "").strip().upper() or None

    if style == "prosign":
        sign_off = " K"
    elif style == "over":
        sign_off = " Over."
    else:
        sign_off = ""

    if station and caller:
        return f"{station} de {caller} {content}{sign_off}"
    if station:
        return f"{station} {content}{sign_off}"
    if caller:
        return f"{caller} {content}{sign_off}"
    return content + sign_off
