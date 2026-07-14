"""Built-in agent implementations."""

from typing import Any

from packages.agents.base import BaseAgent, AgentContext, AgentResult
from packages.core.logging import get_logger
from packages.domain.models import Hypothesis, HypothesisStatus

logger = get_logger("agents")


class ResearchAgent(BaseAgent):
    async def run(self, context: AgentContext, input_data: Any) -> AgentResult:
        logger.info("research_agent_run", input=type(input_data).__name__)
        if isinstance(input_data, dict) and "hypothesis" in input_data:
            hypothesis = input_data["hypothesis"]
            result = {
                "status": "analyzed",
                "hypothesis": hypothesis,
                "findings": f"Research completed for: {hypothesis}",
            }
            return AgentResult(success=True, output=result)
        return AgentResult(success=False, error="Invalid input: expected dict with 'hypothesis' key")


class StrategyAgent(BaseAgent):
    async def run(self, context: AgentContext, input_data: Any) -> AgentResult:
        logger.info("strategy_agent_run")
        research_output = input_data.get("research", {})
        strategy = {
            "name": "sma_crossover",
            "parameters": {"fast_period": 20, "slow_period": 50},
            "status": "proposed",
        }
        return AgentResult(success=True, output=strategy)


class RiskAgent(BaseAgent):
    async def run(self, context: AgentContext, input_data: Any) -> AgentResult:
        logger.info("risk_agent_run")
        assessment = {
            "max_position_size": 0.02,
            "max_drawdown": 0.20,
            "var_95": 0.015,
            "approved": True,
        }
        return AgentResult(success=True, output=assessment)


class ExecutionAgent(BaseAgent):
    async def run(self, context: AgentContext, input_data: Any) -> AgentResult:
        logger.info("execution_agent_run")
        order = input_data.get("order", {})
        execution = {
            "order_id": order.get("id", "unknown"),
            "status": "simulated",
            "fill_price": order.get("price", 0),
            "quantity": order.get("quantity", 0),
        }
        return AgentResult(success=True, output=execution)


class AnalysisAgent(BaseAgent):
    async def run(self, context: AgentContext, input_data: Any) -> AgentResult:
        logger.info("analysis_agent_run")
        output = {
            "summary": "Analysis complete",
            "signals_detected": 0,
            "confidence": 0.5,
        }
        return AgentResult(success=True, output=output)
