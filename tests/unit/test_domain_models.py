"""Tests for domain models."""

from datetime import date, datetime
from decimal import Decimal

from packages.domain.models import (
    Bar, BacktestConfig,
)


class TestBar:
    def test_create_bar(self):
        bar = Bar(
            timestamp=datetime(2024, 1, 2),
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("99"),
            close=Decimal("103"),
            volume=1000000,
            symbol="RELIANCE",
        )
        assert bar.symbol == "RELIANCE"
        assert bar.spread == Decimal("6")
        assert bar.return_pct == 3.0

    def test_bar_spread(self):
        bar = Bar(
            timestamp=datetime(2024, 1, 2),
            open=Decimal("100"), high=Decimal("110"),
            low=Decimal("90"), close=Decimal("105"),
            volume=1000, symbol="TEST",
        )
        assert bar.spread == Decimal("20")


class TestBacktestConfig:
    def test_default_config(self):
        config = BacktestConfig(
            initial_capital=Decimal("1000000"),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        assert config.initial_capital == Decimal("1000000")
        assert config.commission == Decimal("0.0005")

    def test_custom_config(self):
        config = BacktestConfig(
            initial_capital=Decimal("500000"),
            commission=Decimal("0.001"),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        assert config.initial_capital == Decimal("500000")
        assert config.commission == Decimal("0.001")
