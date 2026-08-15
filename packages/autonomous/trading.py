"""Continuous Paper Trader — wraps PaperTradingLoop with strategy lifecycle awareness."""

from datetime import datetime, timezone
from typing import Any, Callable

from packages.trading.loop import PaperTradingLoop
from packages.optimization import SignalOptimizer, StrategyAllocator
from packages.analytics.observation import ObservationLoop


class ContinuousPaperTrader:
    def __init__(
        self,
        paper_loop: PaperTradingLoop,
        signal_optimizer: SignalOptimizer | None = None,
        allocator: StrategyAllocator | None = None,
        observation: ObservationLoop | None = None,
    ):
        self.paper_loop = paper_loop
        self.signal_optimizer = signal_optimizer
        self.allocator = allocator
        self.observation = observation
        self._trade_count = 0
        self._cycle_count = 0
        self._last_run: str | None = None
        self._on_trade: list[Callable] = []
        self._strategy_trades: dict[str, list[dict[str, Any]]] = {}

    def register_on_trade(self, fn: Callable) -> None:
        self._on_trade.append(fn)

    async def run_cycle(self, market_data: list[Any]) -> dict[str, Any]:
        self._cycle_count += 1
        now = datetime.now(timezone.utc).isoformat()
        self._last_run = now

        signals = await self.paper_loop.run(market_data)

        strategy_signals: dict[str, list[Any]] = {}
        for sig in signals:
            strategy_signals.setdefault(getattr(sig, "strategy_id", "default"), []).append(sig)

        for strategy_id, sigs in strategy_signals.items():
            self._strategy_trades.setdefault(strategy_id, [])
            for sig in sigs:
                self._trade_count += 1
                self._strategy_trades[strategy_id].append(
                    {
                        "signal_id": getattr(sig, "id", str(id(sig))),
                        "timestamp": now,
                        "direction": getattr(sig, "direction", "unknown"),
                        "confidence": getattr(sig, "confidence", 0.0),
                    }
                )

        for fn in self._on_trade:
            fn(signals, now)

        return {
            "cycle": self._cycle_count,
            "timestamp": now,
            "signals_generated": len(signals),
            "strategies_active": len(strategy_signals),
            "total_trades": self._trade_count,
        }

    def get_strategy_trades(self, strategy_id: str) -> list[dict[str, Any]]:
        return self._strategy_trades.get(strategy_id, [])

    def get_all_trades(self) -> dict[str, list[dict[str, Any]]]:
        return dict(self._strategy_trades)

    def summary(self) -> dict[str, Any]:
        return {
            "total_trades": self._trade_count,
            "cycles_completed": self._cycle_count,
            "last_run": self._last_run,
            "strategies_with_trades": len(self._strategy_trades),
            "trades_per_strategy": {
                sid: len(trades) for sid, trades in self._strategy_trades.items()
            },
        }
