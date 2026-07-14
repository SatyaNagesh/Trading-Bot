"""Tests for technical indicators."""

import pandas as pd
import numpy as np

from packages.indicators.api import sma, ema, rsi, macd, bb, atr


def test_sma():
    data = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    result = sma(data, 3)
    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == 2.0
    assert result.iloc[-1] == 9.0


def test_ema():
    data = pd.Series([10, 20, 30, 40, 50])
    result = ema(data, 3)
    assert len(result) == 5
    assert pd.isna(result.iloc[0])
    assert result.iloc[-1] > 30


def test_rsi():
    data = pd.Series([45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59])
    result = rsi(data, 5)
    assert len(result) == 15
    assert not result.isna().all()


def test_macd():
    data = pd.Series([10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25])
    result = macd(data)
    assert "macd" in result.columns
    assert "signal" in result.columns
    assert "histogram" in result.columns


def test_bb():
    data = pd.Series([10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20])
    result = bb(data, 3)
    assert "upper" in result.columns
    assert "lower" in result.columns
    assert all(result["upper"] >= result["middle"])


def test_atr():
    high = pd.Series([11, 12, 13, 14, 15])
    low = pd.Series([9, 10, 11, 12, 13])
    close = pd.Series([10, 11, 12, 13, 14])
    result = atr(high, low, close, 3)
    assert len(result) == 5
