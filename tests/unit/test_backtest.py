"""Tests for backtest engine."""

from datetime import datetime, date
from decimal import Decimal

from packages.domain.models import (
    Bar, Signal, SignalDirection, BacktestConfig,
)
from packages.backtesting.engine import BacktestEngine


def _make_bar(close: float, day: int = 1) -> Bar:
    return Bar(
        timestamp=datetime(2024, 1, day),
        open=Decimal(str(close)),
        high=Decimal(str(close + 1)),
        low=Decimal(str(close - 1)),
        close=Decimal(str(close)),
        volume=1000000,
        symbol="TEST",
    )


def test_engine_initialization():
    config = BacktestConfig(
        initial_capital=Decimal("1000000"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    engine = BacktestEngine(config=config)
    assert engine.cash == Decimal("1000000")
    assert engine.current_equity == Decimal("1000000")
    assert engine.positions == {}


def test_empty_backtest():
    config = BacktestConfig(
        initial_capital=Decimal("1000000"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    engine = BacktestEngine(config=config)

    bars = {"TEST": []}
    result = engine.run(bars)
    assert result.total_trades == 0
    assert result.sharpe_ratio == 0.0


def test_backtest_buy_signal_creates_trade():
    config = BacktestConfig(
        initial_capital=Decimal("100000"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 10),
    )

    bought = False

    def buy_on_second_bar(bar, ctx):
        nonlocal bought
        if not bought and float(bar.close) > 100:
            bought = True
            return [Signal(
                strategy_id="test",
                direction=SignalDirection.LONG,
                confidence=1.0,
            )]
        return []

    engine = BacktestEngine(config=config, strategy=buy_on_second_bar)
    bars = {"TEST": [
        _make_bar(100.0, 1),
        _make_bar(101.0, 2),
        _make_bar(102.0, 3),
    ]}
    result = engine.run(bars)
    assert result.total_trades > 0
    assert result.equity_curve[-1]["equity"] > 100000
