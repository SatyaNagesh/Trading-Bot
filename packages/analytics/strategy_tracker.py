"""Strategy Performance Tracking — per-strategy analytics with trend detection."""

from decimal import Decimal
from typing import Any

import numpy as np

from packages.domain.models import Trade
from packages.analytics.engine import TradeAnalytics


class StrategyPerformance:
    def __init__(self, strategy_id: str, trades: list[Trade] | None = None):
        self.strategy_id = strategy_id
        self._all_trades: list[Trade] = list(trades or [])
        self._confidence_scores: list[float] = []
        self._regime_performance: dict[str, float] = {}
        self._symbol_performance: dict[str, float] = {}

    def add_trade(self, trade: Trade) -> None:
        self._all_trades.append(trade)

    def add_trades(self, trades: list[Trade]) -> None:
        self._all_trades.extend(trades)

    def record_confidence(self, confidence: float) -> None:
        self._confidence_scores.append(confidence)

    @property
    def trade_count(self) -> int:
        return len([t for t in self._all_trades if t.exit_time is not None])

    @property
    def closed_trades(self) -> list[Trade]:
        return [t for t in self._all_trades if t.exit_time is not None and t.pnl != Decimal("0")]

    def lifetime(self) -> dict[str, Any]:
        return TradeAnalytics(self._all_trades).summary()

    def recent(self, last_n: int = 20) -> dict[str, Any]:
        recent_trades = sorted(
            [t for t in self._all_trades if t.exit_time],
            key=lambda t: t.exit_time or t.entry_time,
            reverse=True,
        )[:last_n]
        return TradeAnalytics(recent_trades).summary()

    def by_symbol(self, symbol: str) -> dict[str, Any]:
        symbol_trades = [t for t in self._all_trades if t.symbol == symbol]
        return TradeAnalytics(symbol_trades).summary()

    def by_regime(self, regime: str) -> dict[str, Any]:
        regime_trades = [
            t
            for t in self._all_trades
            if hasattr(t, "entry_reason") and regime.lower() in t.entry_reason.lower()
        ]
        return TradeAnalytics(regime_trades).summary()

    @property
    def confidence_trend(self) -> dict[str, Any]:
        if len(self._confidence_scores) < 2:
            return {"mean": 0.0, "trend": "stable", "values": self._confidence_scores}
        values = self._confidence_scores
        half = len(values) // 2
        recent_avg = sum(values[half:]) / len(values[half:]) if values[half:] else 0
        early_avg = sum(values[:half]) / len(values[:half]) if values[:half] else 0
        diff = recent_avg - early_avg
        trend = "rising" if diff > 0.05 else "falling" if diff < -0.05 else "stable"
        return {"mean": sum(values) / len(values), "trend": trend, "values": values}

    @property
    def drawdown_trend(self) -> dict[str, Any]:
        lifetimes = []
        for i in range(1, len(self._all_trades) + 1):
            segment = TradeAnalytics(self._all_trades[:i])
            lifetimes.append(segment.max_drawdown)
        if len(lifetimes) < 2:
            return {"current": 0.0, "trend": "stable"}
        recent = lifetimes[-min(5, len(lifetimes)) :]
        trend = (
            "rising"
            if recent[-1] > recent[0] * 1.1
            else "falling"
            if recent[-1] < recent[0] * 0.9
            else "stable"
        )
        return {"current": lifetimes[-1], "trend": trend}

    @property
    def stability_score(self) -> float:
        if len(self._all_trades) < 5:
            return 1.0
        analytics = TradeAnalytics(self._all_trades)
        returns = analytics.returns_series
        if len(returns) < 2:
            return 1.0
        cv = np.std(returns) / abs(np.mean(returns)) if np.mean(returns) != 0 else float("inf")
        if cv == float("inf"):
            return 0.0
        score = max(0, min(1, 1.0 - cv))
        return round(score, 4)

    def performance_summary(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "total_trades": self.trade_count,
            "lifetime": self.lifetime(),
            "recent": self.recent(),
            "confidence_trend": self.confidence_trend,
            "drawdown_trend": self.drawdown_trend,
            "stability_score": self.stability_score,
        }

    def is_degrading(self, threshold: float = 0.2) -> tuple[bool, list[str]]:
        warnings = []
        life = self.lifetime()
        rec = self.recent()

        if rec.get("sharpe_ratio", 0) < life.get("sharpe_ratio", 0) * (1 - threshold):
            warnings.append(
                f"Sharpe falling: {rec.get('sharpe_ratio', 0):.2f} vs {life.get('sharpe_ratio', 0):.2f}"
            )
        if rec.get("win_rate", 0) < life.get("win_rate", 0) * (1 - threshold):
            warnings.append(
                f"Win rate falling: {rec.get('win_rate', 0):.1f}% vs {life.get('win_rate', 0):.1f}%"
            )
        if (
            rec.get("max_drawdown", 0) > life.get("max_drawdown", 0) * (1 + threshold)
            and life.get("max_drawdown", 0) > 0
        ):
            warnings.append(
                f"Drawdown rising: {rec.get('max_drawdown', 0):.2f} vs {life.get('max_drawdown', 0):.2f}"
            )
        if rec.get("expectancy", 0) < life.get("expectancy", 0) * (1 - threshold):
            warnings.append(
                f"Expectancy falling: {rec.get('expectancy', 0):.2f} vs {life.get('expectancy', 0):.2f}"
            )

        degrading = len(warnings) >= 2
        return degrading, warnings


class StrategyTracker:
    def __init__(self):
        self._strategies: dict[str, StrategyPerformance] = {}

    def register(self, strategy_id: str) -> StrategyPerformance:
        if strategy_id not in self._strategies:
            self._strategies[strategy_id] = StrategyPerformance(strategy_id)
        return self._strategies[strategy_id]

    def get(self, strategy_id: str) -> StrategyPerformance | None:
        return self._strategies.get(strategy_id)

    def record_trade(self, trade: Trade) -> None:
        perf = self.register(trade.strategy_id)
        perf.add_trade(trade)

    def all_summaries(self) -> dict[str, dict[str, Any]]:
        return {sid: perf.performance_summary() for sid, perf in self._strategies.items()}

    def strategy_count(self) -> int:
        return len(self._strategies)

    def degrading_strategies(self, threshold: float = 0.2) -> list[tuple[str, list[str]]]:
        results = []
        for sid, perf in self._strategies.items():
            is_bad, warnings = perf.is_degrading(threshold)
            if is_bad:
                results.append((sid, warnings))
        return sorted(results, key=lambda x: len(x[1]), reverse=True)

    def top_strategies(self, n: int = 5) -> list[tuple[str, float]]:
        scored = []
        for sid, perf in self._strategies.items():
            s = perf.lifetime()
            score = (
                s.get("sharpe_ratio", 0) * 0.4
                + (s.get("win_rate", 0) / 100) * 0.3
                + perf.stability_score * 0.3
            )
            scored.append((sid, score))
        return sorted(scored, key=lambda x: x[1], reverse=True)[:n]
