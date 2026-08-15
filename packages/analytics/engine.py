"""Trade Analytics Engine — comprehensive trade performance metrics."""

import math
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Any

import numpy as np

from packages.domain.models import Trade

TRADING_DAYS_PER_YEAR = 252
TRADING_WEEKS_PER_YEAR = 52
TRADING_MONTHS_PER_YEAR = 12


class TradeAnalytics:
    def __init__(self, trades: list[Trade]):
        self._trades = list(trades)
        self._closed = [
            t for t in self._trades if t.exit_time is not None and t.pnl != Decimal("0")
        ]

    @property
    def total_trades(self) -> int:
        return len(self._closed)

    @property
    def winning_trades(self) -> list[Trade]:
        return [t for t in self._closed if t.pnl > Decimal("0")]

    @property
    def losing_trades(self) -> list[Trade]:
        return [t for t in self._closed if t.pnl < Decimal("0")]

    @property
    def win_rate(self) -> float:
        if not self._closed:
            return 0.0
        return len(self.winning_trades) / len(self._closed) * 100

    @property
    def gross_profit(self) -> float:
        return sum(float(t.pnl) for t in self.winning_trades)

    @property
    def gross_loss(self) -> float:
        return abs(sum(float(t.pnl) for t in self.losing_trades))

    @property
    def profit_factor(self) -> float:
        if self.gross_loss == 0:
            return float("inf") if self.gross_profit > 0 else 0.0
        return self.gross_profit / self.gross_loss

    @property
    def average_win(self) -> float:
        wins = self.winning_trades
        if not wins:
            return 0.0
        return sum(float(t.pnl) for t in wins) / len(wins)

    @property
    def average_loss(self) -> float:
        losses = self.losing_trades
        if not losses:
            return 0.0
        return sum(float(t.pnl) for t in losses) / len(losses)

    @property
    def expectancy(self) -> float:
        if not self._closed:
            return 0.0
        return sum(float(t.pnl) for t in self._closed) / len(self._closed)

    @property
    def total_return(self) -> float:
        return sum(float(t.pnl) for t in self._closed)

    @property
    def returns_series(self) -> list[float]:
        return [float(t.pnl_pct if t.pnl_pct != 0 else float(t.pnl)) for t in self._closed]

    @property
    def sharpe_ratio(self) -> float:
        returns = self.returns_series
        if len(returns) < 2 or np.std(returns) == 0:
            return 0.0
        return (np.mean(returns) / np.std(returns)) * math.sqrt(TRADING_DAYS_PER_YEAR)

    @property
    def sortino_ratio(self) -> float:
        returns = self.returns_series
        if len(returns) < 2:
            return 0.0
        downside = [r for r in returns if r < 0]
        if not downside or np.std(downside) == 0:
            return 0.0
        return (np.mean(returns) / np.std(downside)) * math.sqrt(TRADING_DAYS_PER_YEAR)

    @property
    def max_drawdown(self) -> float:
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for r in self.returns_series:
            cumulative += r
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @property
    def calmar_ratio(self) -> float:
        if self.max_drawdown == 0:
            return 0.0
        annualized = self.total_return / max(len(self._closed) / TRADING_DAYS_PER_YEAR, 1)
        return annualized / self.max_drawdown

    @property
    def recovery_factor(self) -> float:
        if self.max_drawdown == 0:
            return 0.0
        return self.total_return / self.max_drawdown

    @property
    def consecutive_wins(self) -> int:
        streak = 0
        best = 0
        for t in self._closed:
            if t.pnl > 0:
                streak += 1
                best = max(best, streak)
            else:
                streak = 0
        return best

    @property
    def consecutive_losses(self) -> int:
        streak = 0
        best = 0
        for t in self._closed:
            if t.pnl <= 0:
                streak += 1
                best = max(best, streak)
            else:
                streak = 0
        return best

    @property
    def average_holding_time(self) -> timedelta:
        durations = []
        for t in self._closed:
            if t.entry_time and t.exit_time:
                durations.append(t.exit_time - t.entry_time)
        if not durations:
            return timedelta(0)
        total = sum(d.total_seconds() for d in durations)
        return timedelta(seconds=total / len(durations))

    def summary(self) -> dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "winning_trades": len(self.winning_trades),
            "losing_trades": len(self.losing_trades),
            "win_rate": round(self.win_rate, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "sortino_ratio": round(self.sortino_ratio, 4),
            "calmar_ratio": round(self.calmar_ratio, 4),
            "profit_factor": round(self.profit_factor, 4),
            "expectancy": round(self.expectancy, 4),
            "average_win": round(self.average_win, 2),
            "average_loss": round(self.average_loss, 2),
            "max_drawdown": round(self.max_drawdown, 4),
            "recovery_factor": round(self.recovery_factor, 4),
            "consecutive_wins": self.consecutive_wins,
            "consecutive_losses": self.consecutive_losses,
            "average_holding_time_seconds": self.average_holding_time.total_seconds(),
            "total_return": round(self.total_return, 2),
            "gross_profit": round(self.gross_profit, 2),
            "gross_loss": round(self.gross_loss, 2),
        }

    def rolling_summary(self, window: str = "daily") -> list[dict[str, Any]]:
        groups: dict[str, list[Trade]] = defaultdict(list)
        for t in self._closed:
            if t.exit_time is None:
                continue
            if window == "daily":
                key = t.exit_time.strftime("%Y-%m-%d")
            elif window == "weekly":
                key = t.exit_time.strftime("%Y-W%V")
            elif window == "monthly":
                key = t.exit_time.strftime("%Y-%m")
            else:
                key = t.exit_time.strftime("%Y-%m-%d")
            groups[key].append(t)

        results = []
        for period in sorted(groups.keys()):
            analytics = TradeAnalytics(groups[period])
            s = analytics.summary()
            s["period"] = period
            results.append(s)
        return results

    @staticmethod
    def combine(analytics_list: list["TradeAnalytics"]) -> dict[str, Any]:
        all_trades = []
        for a in analytics_list:
            all_trades.extend(a._closed)
        return TradeAnalytics(all_trades).summary()
