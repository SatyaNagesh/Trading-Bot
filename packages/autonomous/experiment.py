"""Experiment Manager — formal experiment lifecycle with state machine."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class ExperimentStatus(str, Enum):
    PROPOSED = "proposed"
    RUNNING = "running"
    VALIDATING = "validating"
    PAPER_TESTING = "paper_testing"
    LEARNING = "learning"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    ARCHIVED = "archived"


EXPERIMENT_TRANSITIONS: dict[ExperimentStatus, list[ExperimentStatus]] = {
    ExperimentStatus.PROPOSED: [ExperimentStatus.RUNNING, ExperimentStatus.REJECTED],
    ExperimentStatus.RUNNING: [ExperimentStatus.VALIDATING, ExperimentStatus.REJECTED],
    ExperimentStatus.VALIDATING: [ExperimentStatus.PAPER_TESTING, ExperimentStatus.REJECTED],
    ExperimentStatus.PAPER_TESTING: [ExperimentStatus.LEARNING, ExperimentStatus.REJECTED],
    ExperimentStatus.LEARNING: [ExperimentStatus.PROMOTED, ExperimentStatus.REJECTED],
    ExperimentStatus.PROMOTED: [ExperimentStatus.ARCHIVED],
    ExperimentStatus.REJECTED: [ExperimentStatus.ARCHIVED],
    ExperimentStatus.ARCHIVED: [],
}


class Experiment:
    def __init__(
        self,
        hypothesis: str,
        strategy_id: str,
        parameters: dict[str, Any] | None = None,
    ):
        self.id = str(uuid4())
        self.hypothesis = hypothesis
        self.strategy_id = strategy_id
        self.parameters = parameters or {}
        self.status = ExperimentStatus.PROPOSED
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at
        self.validation_results: dict[str, Any] = {}
        self.paper_trading_results: dict[str, Any] = {}
        self.observation_results: dict[str, Any] = {}
        self.final_decision: str | None = None
        self.metadata: dict[str, Any] = {}

    def transition(self, to: ExperimentStatus) -> None:
        if to not in EXPERIMENT_TRANSITIONS.get(self.status, []):
            allowed = [s.value for s in EXPERIMENT_TRANSITIONS.get(self.status, [])]
            raise ValueError(
                f"Cannot transition from {self.status.value} to {to.value}. Allowed: {allowed}"
            )
        self.status = to
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "hypothesis": self.hypothesis,
            "strategy_id": self.strategy_id,
            "status": self.status.value,
            "parameters": self.parameters,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "final_decision": self.final_decision,
        }


class ExperimentManager:
    def __init__(self):
        self._experiments: dict[str, Experiment] = {}

    def create(
        self,
        hypothesis: str,
        strategy_id: str,
        parameters: dict[str, Any] | None = None,
    ) -> Experiment:
        exp = Experiment(hypothesis=hypothesis, strategy_id=strategy_id, parameters=parameters)
        self._experiments[exp.id] = exp
        return exp

    def get(self, exp_id: str) -> Experiment | None:
        return self._experiments.get(exp_id)

    def transition(self, exp_id: str, to: ExperimentStatus) -> Experiment:
        exp = self._experiments.get(exp_id)
        if not exp:
            raise KeyError(f"Experiment {exp_id} not found")
        exp.transition(to)
        return exp

    def list(self, status: ExperimentStatus | None = None) -> list[Experiment]:
        exps = list(self._experiments.values())
        if status:
            exps = [e for e in exps if e.status == status]
        return sorted(exps, key=lambda e: e.created_at, reverse=True)

    def count(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self._experiments.values():
            s = e.status.value
            counts[s] = counts.get(s, 0) + 1
        return counts

    def summary(self) -> dict[str, Any]:
        return {
            "total": len(self._experiments),
            "by_status": self.count(),
            "promoted": sum(
                1 for e in self._experiments.values() if e.status == ExperimentStatus.PROMOTED
            ),
            "rejected": sum(
                1 for e in self._experiments.values() if e.status == ExperimentStatus.REJECTED
            ),
            "active": sum(
                1
                for e in self._experiments.values()
                if e.status
                in (
                    ExperimentStatus.RUNNING,
                    ExperimentStatus.VALIDATING,
                    ExperimentStatus.PAPER_TESTING,
                    ExperimentStatus.LEARNING,
                )
            ),
        }
