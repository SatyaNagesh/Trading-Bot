"""Parallel backtest runner — batch evaluate candidates."""

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from time import time

from packages.backtesting.engine import BacktestEngine
from packages.domain.models import Bar, BacktestConfig
from packages.strategies.templates import StrategyTemplate


@dataclass
class CandidateResult:
    strategy_id: str
    strategy_name: str
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    volatility: float = 0.0
    expectancy: float = 0.0
    execution_time: float = 0.0


async def run_strategy(
    template: StrategyTemplate,
    symbol: str,
    bars: list[Bar],
    initial_capital: Decimal = Decimal("1000000"),
) -> CandidateResult:
    start = time()
    signal_fn = template.build_signal_fn()
    indicator_df = template.precompute_indicators(bars)

    def wrapper(bar, ctx):
        ctx.indicator_df = indicator_df
        return signal_fn(bar, ctx)

    dates = [
        b.timestamp.date() if hasattr(b.timestamp, "date") else b.timestamp
        for b in bars
        if b.timestamp
    ]
    if not dates:
        return CandidateResult(strategy_id=template.id, strategy_name=template.name)

    config = BacktestConfig(
        initial_capital=initial_capital,
        start_date=dates[0],
        end_date=dates[-1],
    )
    engine = BacktestEngine(config=config, strategy=wrapper)
    result = await engine.run({symbol: bars})
    elapsed = time() - start
    m = result.metrics or {}
    trades = engine.trades or []
    pnls = [float(t.pnl) for t in trades] if trades else [0]
    expectancy = sum(pnls) / len(pnls) if pnls else 0.0

    return CandidateResult(
        strategy_id=template.id,
        strategy_name=template.name,
        total_return=m.get("total_return", 0),
        sharpe_ratio=m.get("sharpe", 0),
        sortino_ratio=m.get("sortino", 0),
        max_drawdown=m.get("max_drawdown", 0),
        win_rate=m.get("win_rate", 0),
        profit_factor=m.get("profit_factor", 0),
        total_trades=m.get("total_trades", 0),
        volatility=float(np.std(pnls)) if len(pnls) > 1 else 0.0,
        expectancy=round(expectancy, 2),
        execution_time=round(elapsed, 3),
    )


import numpy as np


async def run_batch(
    templates: list[StrategyTemplate],
    symbol: str,
    bars: list[Bar],
    initial_capital: Decimal = Decimal("1000000"),
    max_concurrent: int = 4,
) -> list[CandidateResult]:
    sem = asyncio.Semaphore(max_concurrent)

    async def bounded_run(t: StrategyTemplate) -> CandidateResult:
        async with sem:
            return await run_strategy(t, symbol, bars, initial_capital)

    tasks = [bounded_run(t) for t in templates]
    return await asyncio.gather(*tasks)
