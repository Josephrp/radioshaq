"""Agent registry for routing tasks to specialized agents."""

from __future__ import annotations

from typing import Any, Protocol

from loguru import logger


class SpecializedAgentProtocol(Protocol):
    """Protocol for agents that can be registered."""

    name: str
    description: str
    capabilities: list[str]


class AgentRegistry:
    """Registry for specialized agents with capability-based task routing."""

    def __init__(self) -> None:
        self._agents: dict[str, Any] = {}
        self._capability_index: dict[str, list[str]] = {}  # capability -> agent names

    def register_agent(self, agent: SpecializedAgentProtocol) -> None:
        """Register a specialized agent."""
        name = agent.name
        if name in self._agents:
            logger.warning("Overwriting existing agent: %s", name)
        self._agents[name] = agent
        for cap in agent.capabilities:
            self._capability_index.setdefault(cap, []).append(name)
        logger.debug("Registered agent %s with capabilities %s", name, agent.capabilities)

    def unregister_agent(self, name: str) -> bool:
        """Remove an agent by name. Returns True if removed."""
        if name not in self._agents:
            return False
        agent = self._agents[name]
        for cap in agent.capabilities:
            if cap in self._capability_index:
                self._capability_index[cap] = [
                    n for n in self._capability_index[cap] if n != name
                ]
                if not self._capability_index[cap]:
                    del self._capability_index[cap]
        del self._agents[name]
        return True

    def get_agent(self, name: str) -> Any | None:
        """Get agent by name."""
        return self._agents.get(name)

    def get_agent_for_task(self, task: dict[str, Any] | str) -> Any | None:
        """
        Find the best agent for a task based on task type, required capability, or description.

        DecomposedTask.agent can be the exact agent name from this registry (e.g. radio_tx,
        whitelist, sms, gis); pass it as task["agent"]. If agent is None, lookup uses
        capability and description below.

        Task dict may include:
        - agent: explicit agent name (e.g. radio_tx, whitelist, sms, gis)
        - capability: required capability (e.g. "voice_transmission", "frequency_monitoring")
        - transmission_type: for radio tasks (voice, digital, packet)
        - description: free-text task description for keyword matching
        """
        if isinstance(task, str):
            task = {"description": task}

        # Explicit agent name
        agent_name = task.get("agent")
        if agent_name and agent_name in self._agents:
            return self._agents[agent_name]

        # Explicit capability
        capability = task.get("capability")
        if capability and capability in self._capability_index:
            candidates = self._capability_index[capability]
            if candidates:
                return self._agents.get(candidates[0])

        # Map transmission_type to capability
        tx_type = task.get("transmission_type")
        if tx_type:
            cap_map = {
                "voice": "voice_transmission",
                "digital": "digital_mode_transmission",
                "packet": "packet_radio_transmission",
            }
            cap = cap_map.get(tx_type)
            if cap and cap in self._capability_index:
                return self._agents.get(self._capability_index[cap][0])

        # Keyword matching on description
        description = (task.get("description") or "").lower()
        if description:
            for agent in self._agents.values():
                for cap in agent.capabilities:
                    if cap.replace("_", " ") in description or cap in description:
                        return agent
                if agent.description and agent.description.lower() in description:
                    return agent

        return None

    def list_capabilities(self) -> dict[str, list[str]]:
        """Return capability -> agent names mapping."""
        return {k: list(v) for k, v in self._capability_index.items()}

    def list_agents(self) -> list[dict[str, Any]]:
        """Return list of registered agents with name, description, capabilities."""
        return [
            {
                "name": a.name,
                "description": a.description,
                "capabilities": a.capabilities,
            }
            for a in self._agents.values()
        ]
