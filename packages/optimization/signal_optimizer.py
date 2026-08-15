"""Signal Optimizer — regime gating, health gating, confidence calibration."""

from typing import Callable

from packages.analytics.degradation import DegradationDetector, StrategyHealth
from packages.analytics.regime_observer import RegimeObserver, MarketRegime
from packages.analytics.strategy_tracker import StrategyTracker
from packages.domain.models import Bar, MarketContext, Signal, SignalDirection

REGIME_COMPATIBILITY: dict[str, list[str]] = {
    "trend_following": ["trending", "breakout", "low_volatility"],
    "mean_reversion": ["mean_reverting", "sideways"],
    "breakout": ["breakout", "trending", "high_volatility"],
    "momentum": ["trending", "breakout"],
    "volatility_arb": ["high_volatility", "crisis"],
    "scalping": ["sideways", "low_volatility", "mean_reverting"],
}


class SignalOptimizer:
    def __init__(
        self,
        regime_observer: RegimeObserver | None = None,
        degradation_detector: DegradationDetector | None = None,
        strategy_tracker: StrategyTracker | None = None,
        regime_map: dict[str, list[str]] | None = None,
        min_confidence: float = 0.0,
    ):
        self.regime_observer = regime_observer
        self.detector = degradation_detector
        self.tracker = strategy_tracker
        self.regime_map = regime_map or REGIME_COMPATIBILITY
        self.min_confidence = min_confidence
        self._stats: dict[str, int] = {
            "total_signals": 0,
            "suppressed_health": 0,
            "suppressed_regime": 0,
            "suppressed_confidence": 0,
            "confidence_calibrated": 0,
        }
        self._confidence_history: dict[str, list[float]] = {}

    def wrap(
        self, strategy_fn: Callable[[Bar, MarketContext], list[Signal]]
    ) -> Callable[[Bar, MarketContext], list[Signal]]:
        def wrapped(bar: Bar, ctx: MarketContext) -> list[Signal]:
            raw_signals = strategy_fn(bar, ctx)
            return self.optimize(raw_signals, ctx)

        return wrapped

    def optimize(self, signals: list[Signal], ctx: MarketContext) -> list[Signal]:
        optimized: list[Signal] = []
        for signal in signals:
            self._stats["total_signals"] += 1
            result = self._optimize_one(signal, ctx)
            if result is not None:
                optimized.append(result)
        return optimized

    def _optimize_one(self, signal: Signal, ctx: MarketContext) -> Signal | None:
        sid = signal.strategy_id

        if not self._check_health(sid, signal):
            return None

        if not self._check_regime(sid, signal):
            return None

        if signal.confidence < self.min_confidence and signal.direction != SignalDirection.NEUTRAL:
            self._stats["suppressed_confidence"] += 1
            return None

        return self._calibrate_confidence(signal)

    def _check_health(self, strategy_id: str, signal: Signal) -> bool:
        if not self.detector:
            return True
        health = self.detector.get_health(strategy_id)
        if health in (StrategyHealth.DEGRADED, StrategyHealth.RETIRED):
            self._stats["suppressed_health"] += 1
            return False
        return True

    def _check_regime(self, strategy_id: str, signal: Signal) -> bool:
        if not self.regime_observer:
            return True
        current = self.regime_observer.current_regime
        if current == MarketRegime.UNKNOWN:
            return True
        strategy_type = self._detect_strategy_type(signal)
        compatible = self.regime_map.get(strategy_type, [])
        if compatible and current.value not in compatible:
            self._stats["suppressed_regime"] += 1
            return False
        return True

    def _detect_strategy_type(self, signal: Signal) -> str:
        if signal.direction == SignalDirection.NEUTRAL:
            return "neutral"
        reasons_lower = " ".join(r.lower() for r in signal.reason)
        if "trend" in reasons_lower or "momentum" in reasons_lower:
            return "trend_following"
        if "revers" in reasons_lower or "mean" in reasons_lower:
            return "mean_reversion"
        if "breakout" in reasons_lower or "break" in reasons_lower:
            return "breakout"
        if "volatil" in reasons_lower:
            return "volatility_arb"
        if "scalp" in reasons_lower or "fast" in reasons_lower:
            return "scalping"
        return "trend_following"

    def _calibrate_confidence(self, signal: Signal) -> Signal:
        if signal.direction == SignalDirection.NEUTRAL:
            return signal
        if not self.tracker:
            return signal
        perf = self.tracker.get(signal.strategy_id)
        if not perf:
            return signal
        life = perf.lifetime()
        total = life.get("total_trades", 0)
        if total < 5:
            return signal
        win_rate = life.get("win_rate", 0) / 100.0
        sharpe = max(0, life.get("sharpe_ratio", 0))
        sharpe_norm = min(1.0, sharpe / 3.0)
        performance_factor = 0.5 + win_rate * 0.3 + sharpe_norm * 0.2
        original = signal.confidence
        signal.confidence = round(original * performance_factor, 4)
        signal.confidence = max(0.0, min(1.0, signal.confidence))
        if sid := signal.strategy_id:
            if sid not in self._confidence_history:
                self._confidence_history[sid] = []
            self._confidence_history[sid].append(original)
        if abs(signal.confidence - original) > 0.001:
            self._stats["confidence_calibrated"] += 1
        return signal

    def reset_stats(self) -> None:
        for k in self._stats:
            self._stats[k] = 0

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)
