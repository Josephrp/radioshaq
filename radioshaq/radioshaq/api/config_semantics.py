"""Config API semantics: runtime overrides vs. active runtime.

Runtime configuration overrides (audio, llm, memory, per-role overrides) are stored
only in FastAPI app state (e.g. request.app.state.audio_config_override). They are
merged into GET responses so the UI shows the intended values, but:

- get_config(request) returns app.state.config, the Config instance created at
  lifespan startup. It is not modified by PATCH.
- Orchestrator, agents (voice_rx, radio_tx, etc.), and all components that take
  config at construction receive that startup Config (or a subset like config.audio).
  They never read the overlay dictionaries.

Therefore: changes made via PATCH /config/audio, /config/llm, etc. do NOT affect
active agents or the orchestrator until the process is restarted. After restart,
the application loads config from file/env again; runtime overlays are not
persisted to disk unless the application explicitly supports a "save" action.

Clients should treat config returned by GET as "what will apply after restart"
when overrides are present, and show a "Restart required" notice when appropriate.
"""

CONFIG_APPLIES_AFTER_RESTART = "restart"
"""Value for _meta.config_applies_after in config API responses."""

X_CONFIG_EFFECTIVE_AFTER = "X-Config-Effective-After"
"""Response header set on config PATCH to indicate when changes take effect."""
