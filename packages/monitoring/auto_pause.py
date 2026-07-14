"""Auto-pausing — automatic strategy halt on threshold breaches."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from packages.core.logging import get_logger

logger = get_logger("auto_pause")


class PauseReason(Enum):
    DRAWDOWN = "drawdown"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    SHARPE_DROP = "sharpe_drop"
    VOLATILITY_SPIKE = "volatility_spike"
    MANUAL = "manual"


@dataclass
class PauseEvent:
    strategy_id: str = ""
    reason: PauseReason = PauseReason.MANUAL
    detail: str = ""
    threshold: float = 0.0
    actual_value: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resumed: bool = False


class PauseManager:
    def __init__(self):
        self.events: list[PauseEvent] = {}

    def check_and_pause(
        self,
        strategy_id: str,
        current_drawdown: float,
        consecutive_losses: int,
        sharpe_drop_ratio: float,
        thresholds: dict[str, float] | None = None,
    ) -> PauseEvent | None:
        t = thresholds or {}
        dd_max = t.get("max_drawdown", 25)
        losses_max = t.get("max_consecutive_losses", 5)
        sharpe_max_drop = t.get("max_sharpe_drop", 0.5)
        if current_drawdown > dd_max:
            return self._pause(strategy_id, PauseReason.DRAWDOWN, f"Drawdown {current_drawdown:.1f}% > {dd_max}%", dd_max, current_drawdown)
        if consecutive_losses >= losses_max:
            return self._pause(strategy_id, PauseReason.CONSECUTIVE_LOSSES, f"{consecutive_losses} consecutive losses", losses_max, consecutive_losses)
        if sharpe_drop_ratio > sharpe_max_drop:
            return self._pause(strategy_id, PauseReason.SHARPE_DROP, f"Sharpe drop ratio {sharpe_drop_ratio:.2f}", sharpe_max_drop, sharpe_drop_ratio)
        return None

    def _pause(self, strategy_id: str, reason: PauseReason, detail: str, threshold: float, actual: float) -> PauseEvent:
        event = PauseEvent(strategy_id=strategy_id, reason=reason, detail=detail, threshold=threshold, actual_value=actual)
        self.events[event.timestamp.isoformat() + strategy_id] = event
        logger.warning("strategy_paused", strategy=strategy_id, reason=reason.value)
        return event

    def resume(self, strategy_id: str) -> bool:
        for event in self.events.values():
            if event.strategy_id == strategy_id and not event.resumed:
                event.resumed = True
                logger.info("strategy_resumed", strategy=strategy_id)
                return True
        return False
