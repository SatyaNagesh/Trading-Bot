"""Experiment design framework — structured experiment lifecycle."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from packages.core.logging import get_logger

logger = get_logger("experiment")


class ExperimentStatus(Enum):
    DESIGNED = "designed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


@dataclass
class ExperimentConfig:
    name: str
    hypothesis_id: str
    description: str = ""
    symbols: list[str] = field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    metrics: list[str] = field(default_factory=lambda: ["sharpe", "sortino", "max_dd", "win_rate"])
    min_confidence: float = 0.95


class ExperimentDesigner:
    def __init__(self):
        self.experiments: dict[str, ExperimentConfig] = {}

    def design(self, config: ExperimentConfig) -> str:
        exp_id = str(uuid4())
        config.name = config.name or f"exp_{exp_id[:8]}"
        self.experiments[exp_id] = config
        logger.info("experiment_designed", id=exp_id, name=config.name)
        return exp_id

    def get(self, exp_id: str) -> ExperimentConfig | None:
        return self.experiments.get(exp_id)

    def list(self) -> list[dict]:
        return [
            {"id": eid, "name": exp.name, "hypothesis": exp.hypothesis_id}
            for eid, exp in self.experiments.items()
        ]


def compare_strategies(results: list[dict]) -> dict:
    if not results:
        return {"error": "No results to compare"}
    best = max(results, key=lambda r: r.get("sharpe", 0))
    return {
        "best_strategy": best.get("name", "unknown"),
        "best_sharpe": best.get("sharpe", 0),
        "n_strategies": len(results),
        "results": results,
    }
