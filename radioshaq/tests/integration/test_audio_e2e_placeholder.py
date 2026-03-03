"""Placeholder for end-to-end audio pipeline tests.

Run when API and (optionally) audio devices are available.
Full e2e: Listen → ASR → Trigger → Confirm → TX flow.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="E2E audio test placeholder; enable when env has API + audio")
def test_audio_pipeline_e2e_placeholder() -> None:
    """Placeholder: full audio loop integration test."""
    # 1. Start monitoring (or inject audio)
    # 2. Simulate or inject speech
    # 3. Assert transcript appears and (if confirm_first) pending response created
    # 4. Approve pending via API
    # 5. Assert TX was triggered (mock or real rig)
    assert True
