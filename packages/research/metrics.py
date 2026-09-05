"""Full performance-metric suite for the tournament (Phase 6).

Computes the complete set of requested statistics from an :class:`ExecutionResult`.
All annualizations use a per-bar ``periods_per_day`` so intraday results are
scaled consistently with the regime fix.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from packages.research.execution import ExecutionResult


def _sharpe(returns: np.ndarray, periods_per_day: int, rf: float = 0.0) -> float:
    if len(returns) < 2 or np.std(returns) == 0:
        return 0.0
    mu = returns.mean()
    sigma = returns.std(ddof=1)
    if sigma == 0:
        return 0.0
    annual_bars = 252 * periods_per_day
    rf_per_bar = (1 + rf) ** (1.0 / annual_bars) - 1.0
    return float((mu - rf_per_bar) / sigma * math.sqrt(annual_bars))


def _sortino(returns: np.ndarray, periods_per_day: int, rf: float = 0.0) -> float:
    if len(returns) < 2:
        return 0.0
    annual_bars = 252 * periods_per_day
    rf_per_bar = (1 + rf) ** (1.0 / annual_bars) - 1.0
    excess = returns - rf_per_bar
    downside = excess[excess < 0]
    if len(downside) == 0 or np.std(downside) == 0:
        return 0.0
    return float(excess.mean() / np.std(downside) * math.sqrt(annual_bars))


def _max_drawdown(equity: pd.Series):
    if len(equity) == 0:
        return 0.0
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max.replace(0, np.nan)
    return float(dd.min())


def compute_metrics(
    res: ExecutionResult, periods_per_day: int = 1
) -> dict[str, Any]:
    """Compute the complete metric dictionary for an execution result."""
    net = res.net_returns.to_numpy()
    gross = res.gross_returns.to_numpy()
    equity = res.equity
    trades = res.trades

    n_trades = len(trades)
    pnl_pcts = np.array([t["pnl_pct"] for t in trades]) if trades else np.array([])
    wins = pnl_pcts[pnl_pcts > 0] if len(pnl_pcts) else np.array([])
    losses = pnl_pcts[pnl_pcts <= 0] if len(pnl_pcts) else np.array([])

    win_rate = 100.0 * len(wins) / n_trades if n_trades else 0.0
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(abs(losses.sum())) if len(losses) else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
    expectancy = float(pnl_pcts.mean()) if n_trades else 0.0  # % per trade

    avg_trade = float(pnl_pcts.mean()) if n_trades else 0.0
    median_trade = float(np.median(pnl_pcts)) if n_trades else 0.0

    avg_holding = float(np.mean([t["bars_held"] for t in trades])) if trades else 0.0

    # turnover = total absolute position change / mean positions (fraction of equity)
    delta = res.position_exec.diff().abs().fillna(res.position_exec.abs())
    gross_turnover = float(delta.sum())
    avg_pos = float(res.position_exec.abs().mean()) if len(res.position_exec) else 0.0
    turnover = gross_turnover / len(res.position_exec)  # per bar

    # costs as % of total notional traded
    notional_traded = gross_turnover  # in equity units
    cost_pct = (res.costs_total / notional_traded * 100) if notional_traded > 0 else 0.0

    net_total = float((equity.iloc[-1] - 1.0) * 100)
    gross_total = float((1.0 + gross).prod() - 1.0) * 100

    return {
        "signals": int((res.target != 0).sum()),
        "trades": n_trades,
        "win_rate_pct": round(win_rate, 2),
        "avg_trade_pct": round(avg_trade, 4),
        "median_trade_pct": round(median_trade, 4),
        "gross_return_pct": round(gross_total, 4),
        "net_return_pct": round(net_total, 4),
        "profit_factor": round(profit_factor, 4),
        "expectancy_pct": round(expectancy, 4),
        "max_drawdown_pct": round(_max_drawdown(equity) * 100, 4),
        "sharpe": round(_sharpe(net, periods_per_day), 4),
        "sortino": round(_sortino(net, periods_per_day), 4),
        "turnover_per_bar": round(turnover, 5),
        "avg_holding_bars": round(avg_holding, 2),
        "costs_total": round(res.costs_total, 5),
        "cost_pct_of_notional": round(cost_pct, 4),
    }
