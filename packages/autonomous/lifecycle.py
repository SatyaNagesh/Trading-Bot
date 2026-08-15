"""Strategy Lifecycle — state machine tracking every strategy from conception to retirement."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any


class StrategyStage(str, Enum):
    CONCEIVED = "conceived"
    GENERATING = "generating"
    BACKTESTING = "backtesting"
    VALIDATING = "validating"
    REVIEWED = "reviewed"
    PAPER_TRADING = "paper_trading"
    LIVE_READY = "live_ready"
    OPTIMIZING = "optimizing"
    DEGRADED = "degraded"
    RETIRED = "retired"


STRATEGY_TRANSITIONS: dict[StrategyStage, list[StrategyStage]] = {
    StrategyStage.CONCEIVED: [StrategyStage.GENERATING, StrategyStage.RETIRED],
    StrategyStage.GENERATING: [StrategyStage.BACKTESTING, StrategyStage.RETIRED],
    StrategyStage.BACKTESTING: [StrategyStage.VALIDATING, StrategyStage.RETIRED],
    StrategyStage.VALIDATING: [StrategyStage.REVIEWED, StrategyStage.RETIRED],
    StrategyStage.REVIEWED: [StrategyStage.PAPER_TRADING, StrategyStage.RETIRED],
    StrategyStage.PAPER_TRADING: [
        StrategyStage.LIVE_READY,
        StrategyStage.DEGRADED,
        StrategyStage.RETIRED,
    ],
    StrategyStage.LIVE_READY: [
        StrategyStage.OPTIMIZING,
        StrategyStage.DEGRADED,
        StrategyStage.RETIRED,
    ],
    StrategyStage.OPTIMIZING: [
        StrategyStage.PAPER_TRADING,
        StrategyStage.LIVE_READY,
        StrategyStage.DEGRADED,
        StrategyStage.RETIRED,
    ],
    StrategyStage.DEGRADED: [
        StrategyStage.PAPER_TRADING,
        StrategyStage.OPTIMIZING,
        StrategyStage.RETIRED,
    ],
    StrategyStage.RETIRED: [],
}


class StrategyLifecycle:
    def __init__(self):
        self._strategies: dict[str, dict[str, Any]] = {}

    def register(self, strategy_id: str, name: str) -> str:
        now = datetime.now(timezone.utc).isoformat()
        self._strategies[strategy_id] = {
            "id": strategy_id,
            "name": name,
            "stage": StrategyStage.CONCEIVED,
            "created_at": now,
            "updated_at": now,
            "trade_count": 0,
            "win_rate": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "total_return": 0.0,
            "health": "unknown",
            "experiment_ids": [],
            "degradation_reasons": [],
        }
        return strategy_id

    def transition(self, strategy_id: str, to: StrategyStage) -> dict[str, Any]:
        s = self._strategies.get(strategy_id)
        if not s:
            raise KeyError(f"Strategy {strategy_id} not found")
        current = s["stage"]
        if to not in STRATEGY_TRANSITIONS.get(current, []):
            allowed = [st.value for st in STRATEGY_TRANSITIONS.get(current, [])]
            raise ValueError(
                f"Cannot transition from {current.value} to {to.value}. Allowed: {allowed}"
            )
        s["stage"] = to
        s["updated_at"] = datetime.now(timezone.utc).isoformat()
        return s

    def update_metrics(self, strategy_id: str, metrics: dict[str, Any]) -> dict[str, Any]:
        s = self._strategies.get(strategy_id)
        if not s:
            raise KeyError(f"Strategy {strategy_id} not found")
        for k, v in metrics.items():
            if k in (
                "trade_count",
                "win_rate",
                "sharpe_ratio",
                "max_drawdown",
                "total_return",
                "health",
            ):
                s[k] = v
        s["updated_at"] = datetime.now(timezone.utc).isoformat()
        return s

    def mark_degraded(self, strategy_id: str, reason: str) -> dict[str, Any]:
        s = self._strategies.get(strategy_id)
        if not s:
            raise KeyError(f"Strategy {strategy_id} not found")
        s["degradation_reasons"].append(reason)
        self.transition(strategy_id, StrategyStage.DEGRADED)
        return s

    def link_experiment(self, strategy_id: str, experiment_id: str) -> None:
        s = self._strategies.get(strategy_id)
        if not s:
            raise KeyError(f"Strategy {strategy_id} not found")
        if experiment_id not in s["experiment_ids"]:
            s["experiment_ids"].append(experiment_id)

    def get(self, strategy_id: str) -> dict[str, Any] | None:
        return self._strategies.get(strategy_id)

    def list(self, stage: StrategyStage | None = None) -> list[dict[str, Any]]:
        items = list(self._strategies.values())
        if stage:
            items = [s for s in items if s["stage"] == stage]
        return sorted(items, key=lambda s: s["updated_at"], reverse=True)

    def summary(self) -> dict[str, Any]:
        if not self._strategies:
            return {"total": 0, "by_stage": {}}
        counts: dict[str, int] = {}
        for s in self._strategies.values():
            st = s["stage"].value
            counts[st] = counts.get(st, 0) + 1
        return {
            "total": len(self._strategies),
            "by_stage": counts,
            "degraded": counts.get(StrategyStage.DEGRADED.value, 0),
            "retired": counts.get(StrategyStage.RETIRED.value, 0),
            "paper_trading": counts.get(StrategyStage.PAPER_TRADING.value, 0),
        }
