"""Mistral OAuth / API key handling (oauth-cli-kit pattern)."""

from __future__ import annotations

import os
from typing import Any

from loguru import logger


class MistralOAuthManager:
    """
    Mistral API authentication.
    Uses MISTRAL_API_KEY from env by default; can integrate oauth-cli-kit for OAuth flow.
    """

    def __init__(
        self,
        api_key: str | None = None,
        oauth_config: dict[str, Any] | None = None,
    ):
        self._api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        self._oauth_config = oauth_config or {}

    def get_api_key(self) -> str | None:
        """Return the Mistral API key (env or configured)."""
        return self._api_key

    def set_api_key(self, key: str) -> None:
        """Set API key (e.g. after OAuth exchange)."""
        self._api_key = key

    def has_credentials(self) -> bool:
        """True if API key is available."""
        return bool(self._api_key)

    def get_access_token_for_llm(self) -> str | None:
        """Return token/key for LiteLLM / Mistral client (same as API key here)."""
        return self._api_key

    async def refresh_if_needed(self) -> bool:
        """
        Refresh OAuth token if using OAuth; no-op when using API key.
        Returns True if credentials are valid.
        """
        if self._api_key:
            return True
        if self._oauth_config:
            # Placeholder: oauth-cli-kit exchange could go here
            logger.warning("OAuth config set but no token; set MISTRAL_API_KEY or complete OAuth flow")
        return False
