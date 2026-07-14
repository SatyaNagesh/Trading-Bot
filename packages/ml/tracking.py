"""MLflow experiment tracking integration."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from packages.core.logging import get_logger

logger = get_logger("mlflow_tracking")


@dataclass
class MLExperiment:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    model_type: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ExperimentTracker:
    def __init__(self):
        self.experiments: dict[str, MLExperiment] = {}

    def start(self, name: str, model_type: str, parameters: dict[str, Any] | None = None) -> str:
        exp = MLExperiment(name=name, model_type=model_type, parameters=parameters or {})
        self.experiments[exp.id] = exp
        logger.info("experiment_started", name=name, id=exp.id)
        return exp.id

    def log_metric(self, exp_id: str, key: str, value: float) -> None:
        exp = self.experiments.get(exp_id)
        if exp:
            exp.metrics[key] = value

    def log_params(self, exp_id: str, params: dict[str, Any]) -> None:
        exp = self.experiments.get(exp_id)
        if exp:
            exp.parameters.update(params)

    def get(self, exp_id: str) -> MLExperiment | None:
        return self.experiments.get(exp_id)

    def best_by_metric(self, metric: str = "sharpe") -> MLExperiment | None:
        valid = [e for e in self.experiments.values() if metric in e.metrics]
        if not valid:
            return None
        return max(valid, key=lambda e: e.metrics[metric])

    def list(self) -> list[dict]:
        return [
            {"id": e.id, "name": e.name, "model": e.model_type, "metrics": e.metrics}
            for e in self.experiments.values()
        ]


tracker = ExperimentTracker()
