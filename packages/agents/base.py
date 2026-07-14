"""Base agent class for QuantLab AI Agent Framework."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from packages.core.logging import get_logger

logger = get_logger("agent_base")


class AgentError(Exception):
    pass


@dataclass
class AgentContext:
    session_id: str
    strategy_id: str | None = None
    state: dict[str, Any] = field(default_factory=dict)
    memory: list[str] = field(default_factory=list)
    max_steps: int = 25
    current_step: int = 0


@dataclass
class AgentResult:
    success: bool
    output: Any = None
    error: str | None = None
    steps_taken: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    def __init__(self, agent_id: str, name: str, description: str = ""):
        self.agent_id = agent_id
        self.name = name
        self.description = description

    @abstractmethod
    async def run(self, context: AgentContext, input_data: Any) -> AgentResult:
        ...

    async def think(self, context: AgentContext, prompt: str) -> str:
        logger.debug("agent_think", agent=self.agent_id, step=context.current_step)
        return ""

    async def act(self, context: AgentContext, decision: str) -> Any:
        context.current_step += 1
        return None
