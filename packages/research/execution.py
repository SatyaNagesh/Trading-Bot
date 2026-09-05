"""Uniform hypothetical execution for the tournament.

Every candidate is executed through the exact same model:

* The strategy's ``target[t]`` (decided with data at-or-before ``t``) is filled
  at the **next** bar's close, i.e. we hold ``position_exec[t] = target[t-1]``.
  This guarantees no same-bar look-ahead: you act only on completed bars.
* A single **notional** trading model: position is a fraction of equity in
  ``{-1,0,1}``; each time the intended position changes we pay
  ``turnover * (slippage + commission)`` where ``turnover = |Δposition|``.
  Round-trip cost therefore = ``2*(slippage+commission)`` for a full
  long->flat->long cycle, identical for all candidates.

Using *fraction of equity* (not share-count) makes every candidate comparable
regardless of price level, and costs scale with the actual notional traded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class ExecutionResult:
    strategy_name: str
    close: pd.Series
    ts: pd.Series
    target: pd.Series
    position_exec: pd.Series
    gross_returns: pd.Series
    net_returns: pd.Series
    equity: pd.Series
    costs_total: float
    trades: list[dict[str, Any]] = field(default_factory=list)


def _trade_list(ts, position_exec, close, gross_returns, net_returns):
    """Reconstruct a list of round-trip trades from the executed position series."""
    trades = []
    pos = 0
    entry_price = None
    entry_idx = None
    p = position_exec.to_numpy()
    cl = close.to_numpy()
    times = list(ts)
    for i in range(len(p)):
        if p[i] != pos:
            if pos != 0:
                # close existing position
                trades.append(
                    {
                        "side": "long" if pos > 0 else "short",
                        "entry_time": str(times[entry_idx]),
                        "exit_time": str(times[i]),
                        "entry_price": float(entry_price),
                        "exit_price": float(cl[i]),
                        "pnl_pct": float(
                            (cl[i] / entry_price - 1) * pos * 100
                            if entry_price
                            else 0.0
                        ),
                        "bars_held": i - entry_idx,
                    }
                )
            entry_price = cl[i]
            entry_idx = i
            pos = p[i]
    # close open position at end
    if pos != 0 and entry_price is not None:
        last = len(cl) - 1
        trades.append(
            {
                "side": "long" if pos > 0 else "short",
                "entry_time": str(times[entry_idx]),
                "exit_time": str(times[last]),
                "entry_price": float(entry_price),
                "exit_price": float(cl[last]),
                "pnl_pct": float((cl[last] / entry_price - 1) * pos * 100)
                if entry_price
                else 0.0,
                "bars_held": last - entry_idx,
            }
        )
    return trades


def execute(
    close: pd.Series,
    ts,
    target: pd.Series,
    slippage: float = 0.001,
    commission: float = 0.0005,
) -> ExecutionResult:
    """Execute an intended-position series under the uniform no-look-ahead model.

    Parameters
    ----------
    close : pd.Series
        Close prices aligned to `ts`.
    ts : iterable of timestamps
        Bar timestamps (same length as `close`).
    target : pd.Series
        Intended position over {-1,0,1}, decided causally.
    slippage, commission : float
        Per-unit-value (per side) execution costs.
    """
    close = close.astype(float)
    target = target.astype(float).fillna(0.0).clip(-1, 1)

    # Fill at next bar's close -> one-bar execution lag, strictly causal.
    position_exec = target.shift(1).fillna(0.0).clip(-1, 1)

    # Simple one-bar close-to-close gross return, scaled by held position.
    cc_return = close.pct_change().fillna(0.0)
    gross_returns = position_exec * cc_return

    # Turnover-based costs (per-side slippage+commission on each unit changed).
    delta_pos = position_exec.diff().abs().fillna(position_exec.abs())
    cost_rate = slippage + commission
    per_bar_cost = delta_pos * cost_rate
    costs_total = float(per_bar_cost.sum())
    net_returns = gross_returns - per_bar_cost

    equity = (1.0 + net_returns).cumprod()
    trades = _trade_list(ts, position_exec, close, gross_returns, net_returns)

    return ExecutionResult(
        strategy_name=str(getattr(target, "name", "?")),
        close=close,
        ts=pd.Series(list(ts)),
        target=target,
        position_exec=position_exec,
        gross_returns=gross_returns,
        net_returns=net_returns,
        equity=equity,
        costs_total=costs_total,
        trades=trades,
    )
