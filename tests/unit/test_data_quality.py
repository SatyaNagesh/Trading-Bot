"""Tests for data quality checks."""

from datetime import datetime
from decimal import Decimal

from packages.market.data_quality import check_gaps, check_outliers
from packages.domain.models import Bar


def _bar(close: float, day: int) -> Bar:
    return Bar(
        timestamp=datetime(2024, 1, day),
        open=Decimal(str(close)),
        high=Decimal(str(close + 1)),
        low=Decimal(str(close - 1)),
        close=Decimal(str(close)),
        volume=1000000,
        symbol="TEST",
    )


def test_no_gaps():
    bars = [_bar(100, i) for i in range(1, 11)]
    warnings = check_gaps(bars, "TEST")
    assert len(warnings) == 0


def test_detects_gap():
    bars = [_bar(100, 1), _bar(100, 2), _bar(100, 10)]
    warnings = check_gaps(bars, "TEST")
    assert len(warnings) == 1
    assert "gap" in warnings[0]


def test_outlier_detection():
    bars = [_bar(100, i) for i in range(1, 30)]
    bars.append(_bar(200, 30))
    warnings = check_outliers(bars, "TEST")
    assert len(warnings) >= 1
