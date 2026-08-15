"""Autonomous Scheduler — orchestrates timed execution of research, trading, and learning cycles."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4


@dataclass
class ScheduleConfig:
    research_interval_hours: float = 4.0
    paper_trading_interval_minutes: float = 15.0
    learning_interval_hours: float = 1.0
    reporting_interval_hours: float = 6.0
    health_check_interval_minutes: float = 5.0
    max_candidates_per_cycle: int = 500
    max_paper_positions: int = 10
    degradation_threshold_sharpe: float = 0.5
    min_trades_for_analysis: int = 20
    max_active_experiments: int = 5


class AutonomousScheduler:
    def __init__(self, config: ScheduleConfig | None = None):
        self.config = config or ScheduleConfig()
        self._cycle_id: str | None = None
        self._started_at: str | None = None
        self._cycle_count = 0
        self._last_research: str | None = None
        self._last_learning: str | None = None
        self._last_report: str | None = None
        self._is_running = False
        self._hooks: dict[str, list[Callable]] = {
            "on_cycle_start": [],
            "on_cycle_end": [],
            "on_error": [],
        }

    def register_hook(self, event: str, fn: Callable) -> None:
        if event in self._hooks:
            self._hooks[event].append(fn)

    def start(self) -> str:
        self._cycle_id = str(uuid4())
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._is_running = True
        self._cycle_count = 0
        return self._cycle_id

    def stop(self) -> None:
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    def next_cycle(self) -> str:
        if not self._is_running:
            raise RuntimeError("Scheduler is not running")
        self._cycle_count += 1
        cycle_id = str(uuid4())
        for fn in self._hooks.get("on_cycle_start", []):
            try:
                fn(cycle_id, self._cycle_count)
            except Exception:
                pass
        return cycle_id

    def mark_research_done(self) -> None:
        self._last_research = datetime.now(timezone.utc).isoformat()

    def mark_learning_done(self) -> None:
        self._last_learning = datetime.now(timezone.utc).isoformat()

    def mark_report_done(self) -> None:
        self._last_report = datetime.now(timezone.utc).isoformat()

    def status(self) -> dict[str, Any]:
        return {
            "is_running": self._is_running,
            "cycle_id": self._cycle_id,
            "cycle_count": self._cycle_count,
            "started_at": self._started_at,
            "last_research": self._last_research,
            "last_learning": self._last_learning,
            "last_report": self._last_report,
            "config": {
                "research_interval_hours": self.config.research_interval_hours,
                "paper_trading_interval_minutes": self.config.paper_trading_interval_minutes,
                "learning_interval_hours": self.config.learning_interval_hours,
                "reporting_interval_hours": self.config.reporting_interval_hours,
                "health_check_interval_minutes": self.config.health_check_interval_minutes,
                "max_candidates_per_cycle": self.config.max_candidates_per_cycle,
                "max_active_experiments": self.config.max_active_experiments,
            },
        }
