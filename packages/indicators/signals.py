"""Signal generator with confidence scoring."""

from typing import Any

from packages.domain.models import Signal, SignalDirection
from packages.core.logging import get_logger

logger = get_logger("signal_generator")


class SignalGenerator:
    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id

    def long(self, confidence: float = 0.5, reason: list[str] | None = None, **extra: Any) -> Signal:
        return Signal(
            strategy_id=self.strategy_id,
            direction=SignalDirection.LONG,
            confidence=min(max(confidence, 0), 1),
            reason=reason or [],
            indicator_values=extra,
        )

    def short(self, confidence: float = 0.5, reason: list[str] | None = None, **extra: Any) -> Signal:
        return Signal(
            strategy_id=self.strategy_id,
            direction=SignalDirection.SHORT,
            confidence=min(max(confidence, 0), 1),
            reason=reason or [],
            indicator_values=extra,
        )

    def neutral(self) -> Signal:
        return Signal(
            strategy_id=self.strategy_id,
            direction=SignalDirection.NEUTRAL,
            confidence=0.0,
        )


def compute_signal_confidence(
    indicator_strength: float,
    regime_weight: float = 1.0,
    conviction: float = 1.0,
) -> float:
    raw = indicator_strength * regime_weight * conviction
    return max(0.0, min(1.0, raw))
