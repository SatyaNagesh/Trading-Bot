"""Workflow Engine — DAG-based pipeline execution with orchestration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from packages.core.logging import get_logger

logger = get_logger("workflow")


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class StepResult:
    step_id: str
    status: StepStatus
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class WorkflowStep(ABC):
    def __init__(self, step_id: str, depends_on: list[str] | None = None):
        self.step_id = step_id
        self.depends_on = depends_on or []
        self.status = StepStatus.PENDING
        self.result: dict[str, Any] = {}

    @abstractmethod
    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        ...


class Workflow:
    def __init__(self, name: str):
        self.name = name
        self.steps: dict[str, WorkflowStep] = {}
        self.status = WorkflowStatus.PENDING
        self.context: dict[str, Any] = {}
        self.created_at = datetime.now(timezone.utc)

    def add_step(self, step: WorkflowStep) -> "Workflow":
        self.steps[step.step_id] = step
        return self

    def resolve_dag(self) -> list[str]:
        visited = set()
        order: list[str] = []

        def dfs(step_id: str):
            if step_id in visited:
                return
            visited.add(step_id)
            step = self.steps.get(step_id)
            if step:
                for dep in step.depends_on:
                    dfs(dep)
                order.append(step_id)

        for step_id in self.steps:
            dfs(step_id)
        return order

    async def run(self, context: dict[str, Any] | None = None) -> list[StepResult]:
        self.status = WorkflowStatus.RUNNING
        if context:
            self.context.update(context)
        order = self.resolve_dag()
        results: list[StepResult] = []

        for step_id in order:
            step = self.steps[step_id]
            deps_failed = any(
                r.status == StepStatus.FAILED
                for r in results
                if r.step_id in step.depends_on
            )
            if deps_failed:
                step.status = StepStatus.SKIPPED
                results.append(StepResult(step_id, StepStatus.SKIPPED))
                continue

            step.status = StepStatus.RUNNING
            try:
                output = await step.execute(self.context)
                step.status = StepStatus.SUCCESS
                step.result = output
                self.context[step_id] = output
                results.append(StepResult(step_id, StepStatus.SUCCESS, output))
                logger.info("step_completed", workflow=self.name, step=step_id)
            except Exception as e:
                step.status = StepStatus.FAILED
                results.append(StepResult(step_id, StepStatus.FAILED, error=str(e)))
                logger.error("step_failed", workflow=self.name, step=step_id, error=str(e))
                self.status = WorkflowStatus.FAILED
                return results

        self.status = WorkflowStatus.SUCCESS
        return results
