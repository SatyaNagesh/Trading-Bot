"""Data quality checks for market data."""

from datetime import date, datetime
from decimal import Decimal

import numpy as np

from packages.domain.models import Bar
from packages.core.exceptions import DataQualityError
from packages.core.logging import get_logger

logger = get_logger("data_quality")


def check_gaps(bars: list[Bar], symbol: str) -> list[str]:
    warnings = []
    if len(bars) < 2:
        return warnings

    dates = [b.timestamp.date() for b in bars]
    for i in range(1, len(dates)):
        diff = (dates[i] - dates[i - 1]).days
        if diff > 5:
            warnings.append(
                f"{symbol}: gap of {diff} days between {dates[i-1]} and {dates[i]}"
            )
    return warnings


def check_outliers(bars: list[Bar], symbol: str, std_threshold: float = 5.0) -> list[str]:
    warnings = []
    if len(bars) < 20:
        return warnings

    returns = [float((b.close - b.open) / b.open) for b in bars]
    mean = np.mean(returns)
    std = np.std(returns)

    for bar, ret in zip(bars, returns):
        z_score = abs(ret - mean) / std if std > 0 else 0
        if z_score > std_threshold:
            warnings.append(
                f"{symbol}: outlier return {ret:.4f} (z={z_score:.2f}) on {bar.timestamp.date()}"
            )
    return warnings


def check_corporate_actions(
    bars: list[Bar], symbol: str, price_change_threshold: float = 0.20
) -> list[str]:
    warnings = []
    if len(bars) < 2:
        return warnings

    for i in range(1, len(bars)):
        change = abs(float((bars[i].close - bars[i - 1].close) / bars[i - 1].close))
        if change > price_change_threshold:
            warnings.append(
                f"{symbol}: suspicious price change {change:.2%} on {bars[i].timestamp.date()}"
            )
    return warnings


def validate_bars(bars: list[Bar], symbol: str) -> list[str]:
    all_warnings = []
    all_warnings.extend(check_gaps(bars, symbol))
    all_warnings.extend(check_outliers(bars, symbol))
    all_warnings.extend(check_corporate_actions(bars, symbol))
    return all_warnings
