"""Unit tests for callsign repository and WhitelistAgent."""

from __future__ import annotations

import pytest

from radioshaq.callsign import get_callsign_repository, CallsignRegistryRepositoryImpl
from radioshaq.specialized.whitelist_agent import WhitelistAgent


@pytest.mark.unit
def test_get_callsign_repository_returns_none_when_db_is_none() -> None:
    """get_callsign_repository(None) returns None."""
    assert get_callsign_repository(None) is None


@pytest.mark.unit
def test_get_callsign_repository_returns_none_when_db_missing_methods() -> None:
    """get_callsign_repository(obj) returns None when obj lacks required methods."""
    class IncompleteDB:
        pass
    assert get_callsign_repository(IncompleteDB()) is None

    class OnlyList:
        async def list_registered_callsigns(self):
            return []
    assert get_callsign_repository(OnlyList()) is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_callsign_repository_impl_delegates_to_db() -> None:
    """CallsignRegistryRepositoryImpl delegates list/register/unregister/is_registered to db."""
    recorded = []

    class MockDB:
        async def list_registered_callsigns(self):
            recorded.append("list")
            return [{"callsign": "K5ABC", "id": 1}]

        async def register_callsign(self, callsign: str, source: str = "api", preferred_bands: list | None = None):
            recorded.append(("register", callsign, source))
            return 1

        async def unregister_callsign(self, callsign: str):
            recorded.append(("unregister", callsign))
            return True

        async def is_callsign_registered(self, callsign: str):
            recorded.append(("is_registered", callsign))
            return True

        async def update_callsign_last_band(self, callsign: str, band: str):
            recorded.append(("update_last_band", callsign, band))
            return True

        async def update_callsign_preferred_bands(self, callsign: str, preferred_bands: list):
            recorded.append(("update_preferred_bands", callsign, preferred_bands))
            return True

    db = MockDB()
    repo = CallsignRegistryRepositoryImpl(db)
    assert repo is not None

    out = await repo.list_registered()
    assert out == [{"callsign": "K5ABC", "id": 1}]
    assert "list" in recorded

    row_id = await repo.register("k5abc", source="api")
    assert row_id == 1
    assert ("register", "K5ABC", "api") in [(r[0], r[1], r[2]) for r in recorded if len(r) == 3]

    removed = await repo.unregister(" W1XYZ ")
    assert removed is True
    assert any(r[0] == "unregister" and r[1] == "W1XYZ" for r in recorded if len(r) == 2)

    ok = await repo.is_registered("  k5abc  ")
    assert ok is True
    assert any(r[0] == "is_registered" and r[1] == "K5ABC" for r in recorded if len(r) == 2)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_callsign_repository_update_last_band_and_list_includes_bands() -> None:
    """update_last_band and update_preferred_bands delegate to db; list_registered returns preferred_bands and last_band."""
    recorded = []
    listed = [{"callsign": "W1ABC", "id": 1, "last_band": None, "preferred_bands": None}]

    class MockDB:
        async def list_registered_callsigns(self):
            return list(listed)

        async def register_callsign(self, callsign: str, source: str = "api", preferred_bands: list | None = None):
            return 1

        async def unregister_callsign(self, callsign: str):
            return True

        async def is_callsign_registered(self, callsign: str):
            return True

        async def update_callsign_last_band(self, callsign: str, band: str):
            recorded.append(("last_band", callsign, band))
            for r in listed:
                if r.get("callsign") == callsign:
                    r["last_band"] = band
                    break
            return True

        async def update_callsign_preferred_bands(self, callsign: str, preferred_bands: list):
            recorded.append(("preferred_bands", callsign, preferred_bands))
            for r in listed:
                if r.get("callsign") == callsign:
                    r["preferred_bands"] = preferred_bands
                    break
            return True

    db = MockDB()
    repo = CallsignRegistryRepositoryImpl(db)
    await repo.update_last_band("W1ABC", "40m")
    assert ("last_band", "W1ABC", "40m") in recorded
    out = await repo.list_registered()
    assert len(out) == 1
    assert out[0].get("last_band") == "40m"
    await repo.update_preferred_bands("W1ABC", ["40m", "2m"])
    assert any(r[0] == "preferred_bands" and r[1] == "W1ABC" for r in recorded)
    out2 = await repo.list_registered()
    assert out2[0].get("preferred_bands") == ["40m", "2m"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_whitelist_agent_no_request_text_returns_message() -> None:
    """WhitelistAgent with empty request_text returns approved=False and message_for_user."""
    agent = WhitelistAgent(repository=None, llm_client=None)
    result = await agent.execute({"description": ""})
    assert result["approved"] is False
    assert "message_for_user" in result
    assert "gated" in result["message_for_user"].lower() or "request" in result["message_for_user"].lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_whitelist_agent_no_repository_returns_error() -> None:
    """WhitelistAgent with no repository returns approved=False and no_repository message."""
    agent = WhitelistAgent(repository=None, llm_client=None)
    result = await agent.execute({"request_text": "I need access for messaging.", "callsign": "K5ABC"})
    assert result["approved"] is False
    assert result.get("error") == "no_repository" or "not available" in result.get("message_for_user", "").lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_whitelist_agent_name_and_capabilities() -> None:
    """WhitelistAgent has name whitelist and whitelist capabilities."""
    agent = WhitelistAgent(repository=None, llm_client=None)
    assert agent.name == "whitelist"
    assert "whitelist" in agent.capabilities
    assert "whitelist_evaluation" in agent.capabilities
