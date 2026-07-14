"""LangGraph-based agent orchestration for the Agent Framework."""

from typing import Any

from packages.agents.base import BaseAgent, AgentContext, AgentResult
from packages.core.logging import get_logger

logger = get_logger("orchestrator")


class AgentOrchestrator:
    def __init__(self):
        self.agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self.agents[agent.agent_id] = agent
        logger.info("agent_registered", agent_id=agent.agent_id, name=agent.name)

    def get(self, agent_id: str) -> BaseAgent | None:
        return self.agents.get(agent_id)

    async def run_sequential(
        self,
        pipeline: list[tuple[str, Any]],
        context: AgentContext | None = None,
    ) -> list[AgentResult]:
        if context is None:
            context = AgentContext(session_id="orchestrator")
        results = []
        for agent_id, input_data in pipeline:
            agent = self.agents.get(agent_id)
            if not agent:
                logger.error("agent_not_found", agent_id=agent_id)
                results.append(AgentResult(success=False, error=f"Agent {agent_id} not found"))
                continue
            if context.current_step >= context.max_steps:
                logger.warning("max_steps_reached", agent_id=agent_id)
                break
            result = await agent.run(context, input_data)
            results.append(result)
            context.memory.append(f"{agent_id}: {result.output}")
        return results

    async def run_parallel(
        self,
        tasks: list[tuple[str, Any]],
        context: AgentContext | None = None,
    ) -> list[AgentResult]:
        if context is None:
            context = AgentContext(session_id="orchestrator")
        import asyncio
        coros = []
        for agent_id, input_data in tasks:
            agent = self.agents.get(agent_id)
            if not agent:
                coros.append(self._not_found(agent_id))
            else:
                coros.append(agent.run(context, input_data))
        return await asyncio.gather(*coros)

    async def _not_found(self, agent_id: str) -> AgentResult:
        return AgentResult(success=False, error=f"Agent {agent_id} not found")

    async def run_workflow(
        self,
        graph: dict[str, list[str]],
        start: str,
        inputs: dict[str, Any],
        context: AgentContext | None = None,
    ) -> dict[str, AgentResult]:
        if context is None:
            context = AgentContext(session_id="workflow")
        results: dict[str, AgentResult] = {}
        queue = [start]
        visited = set()

        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            agent = self.agents.get(node)
            if not agent:
                results[node] = AgentResult(success=False, error=f"Agent {node} not found")
                continue
            input_data = inputs.get(node, {})
            result = await agent.run(context, input_data)
            results[node] = result
            context.memory.append(f"{node}: {result.output}")
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    queue.append(neighbor)
        return results
