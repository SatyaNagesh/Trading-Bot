"""CEO, CTO, and Documentation agents."""

from packages.agents.base import BaseAgent, AgentContext, AgentResult
from packages.core.logging import get_logger

logger = get_logger("agents_v2")


class CEOAgent(BaseAgent):
    async def run(self, context: AgentContext, input_data: dict) -> AgentResult:
        logger.info("ceo_agent_run")
        tasks = input_data.get("tasks", [])
        agents = input_data.get("available_agents", [])
        prioritized = sorted(tasks, key=lambda t: t.get("priority", 0), reverse=True)
        assignments = {}
        for i, task in enumerate(prioritized):
            if i < len(agents):
                assignments[task.get("id", f"task_{i}")] = agents[i]
        return AgentResult(
            success=True,
            output={
                "assignments": assignments,
                "order": [t.get("name") for t in prioritized],
            },
        )


class CTOAgent(BaseAgent):
    async def run(self, context: AgentContext, input_data: dict) -> AgentResult:
        logger.info("cto_agent_run")
        health = input_data.get("health", {})
        issues = []
        for service, status in health.items():
            if not status:
                issues.append(f"{service} is unhealthy")
        return AgentResult(
            success=True,
            output={
                "healthy": len(issues) == 0,
                "issues": issues,
                "recommendations": ["scale up" for _ in issues],
            },
        )


class DocumentationAgent(BaseAgent):
    async def run(self, context: AgentContext, input_data: dict) -> AgentResult:
        logger.info("doc_agent_run")
        strategy_name = input_data.get("name", "unknown")
        sharpe = input_data.get("sharpe", 0)
        report = (
            f"# Strategy Report: {strategy_name}\n\n"
            f"## Performance\n- Sharpe Ratio: {sharpe:.2f}\n"
            f"- Total Return: {input_data.get('total_return', 0):.2f}%\n"
            f"- Max Drawdown: {input_data.get('max_drawdown', 0):.2f}%\n\n"
            f"## Generated\nAutomated report by QuantLab Documentation Agent"
        )
        return AgentResult(success=True, output={"report": report})
