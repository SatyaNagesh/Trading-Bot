"""Advanced Backtest — walk-forward analysis, Monte Carlo simulation, multi-asset."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Callable

import numpy as np

from packages.backtesting.engine import BacktestEngine
from packages.backtesting.report import BacktestReport, compute_metrics
from packages.core.logging import get_logger
from packages.domain.models import Bar, Signal

logger = get_logger("advanced_backtest")


@dataclass
class WalkForwardWindow:
    train_start: date
    train_end: date
    test_start: date
    test_end: date


class WalkForwardAnalyzer:
    def __init__(self, bars: list[Bar], window_size: int = 252, step_size: int = 63):
        self.bars = bars
        self.window_size = window_size
        self.step_size = step_size
        self.dates = sorted(set(b.date for b in bars))
        self.windows = self._build_windows()

    def _build_windows(self) -> list[WalkForwardWindow]:
        windows = []
        for i in range(0, len(self.dates) - self.window_size, self.step_size):
            train_end_idx = i + self.window_size
            test_end_idx = min(train_end_idx + self.step_size, len(self.dates))
            windows.append(WalkForwardWindow(
                train_start=self.dates[i],
                train_end=self.dates[train_end_idx - 1],
                test_start=self.dates[train_end_idx],
                test_end=self.dates[test_end_idx - 1],
            ))
        return windows

    def run(self, strategy: Callable[[Bar, Any], list[Signal]], initial_capital: float = 1_000_000) -> dict:
        results = []
        for w in self.windows:
            train_bars = [b for b in self.bars if w.train_start <= b.date <= w.train_end]
            test_bars = [b for b in self.bars if w.test_start <= b.date <= w.test_end]
            engine = BacktestEngine(initial_capital=Decimal(str(initial_capital)))
            engine.run(train_bars, strategy)
            engine.run(test_bars, strategy)
            metrics = engine.metrics()
            results.append({
                "train_start": w.train_start.isoformat(),
                "test_end": w.test_end.isoformat(),
                "sharpe": metrics["sharpe_ratio"],
                "sortino": metrics["sortino_ratio"],
                "total_return": metrics["total_return_pct"],
                "max_drawdown": metrics["max_drawdown_pct"],
            })
        sharpe_values = [r["sharpe"] for r in results]
        return {
            "windows": results,
            "mean_sharpe": float(np.mean(sharpe_values)),
            "std_sharpe": float(np.std(sharpe_values)),
            "min_sharpe": float(np.min(sharpe_values)),
            "max_sharpe": float(np.max(sharpe_values)),
        }


class MonteCarloSimulator:
    def __init__(self, bars: list[Bar], n_simulations: int = 1000, horizon_days: int = 252):
        self.returns = np.diff(np.log(np.array([float(b.close) for b in bars]) + 1e-10))
        self.n = n_simulations
        self.horizon = horizon_days

    def run(self, initial_capital: float = 1_000_000) -> dict:
        mu = np.mean(self.returns)
        sigma = np.std(self.returns)
        paths = np.zeros((self.n, self.horizon + 1))
        paths[:, 0] = initial_capital
        for t in range(1, self.horizon + 1):
            noise = np.random.normal(0, sigma, self.n)
            paths[:, t] = paths[:, t - 1] * (1 + mu + noise)
        final_values = paths[:, -1]
        var_95 = float(np.percentile(final_values, 5))
        cvar_95 = float(np.mean(final_values[final_values <= var_95]))
        return {
            "initial_capital": initial_capital,
            "mean_final": float(np.mean(final_values)),
            "median_final": float(np.median(final_values)),
            "std_final": float(np.std(final_values)),
            "var_95": var_95,
            "cvar_95": cvar_95,
            "prob_loss": float(np.mean(final_values < initial_capital)),
            "prob_double": float(np.mean(final_values >= initial_capital * 2)),
        }


class MultiAssetBacktest:
    def __init__(self):
        self.engines: dict[str, BacktestEngine] = {}

    def add_asset(self, symbol: str, initial_capital: float = 1_000_000):
        self.engines[symbol] = BacktestEngine(initial_capital=Decimal(str(initial_capital)))

    def run(
        self,
        bars: dict[str, list[Bar]],
        strategies: dict[str, Callable],
    ):
        for symbol, engine in self.engines.items():
            symbol_bars = bars.get(symbol, [])
            strategy = strategies.get(symbol)
            if strategy:
                engine.run(symbol_bars, strategy)

    def portfolio_metrics(self) -> dict:
        total_pnl = Decimal("0")
        total_capital = Decimal("0")
        asset_metrics = {}
        for symbol, engine in self.engines.items():
            m = engine.metrics()
            asset_metrics[symbol] = m
            total_pnl += Decimal(str(m.get("total_return_pnl", 0)))
            total_capital += engine.initial_capital
        portfolio_return_pct = float((total_pnl / total_capital) * 100) if total_capital else 0
        return {
            "assets": asset_metrics,
            "portfolio_return_pct": round(portfolio_return_pct, 2),
            "n_assets": len(self.engines),
        }
