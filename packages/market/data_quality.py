"""Data quality checks for market data."""

import numpy as np
import pandas as pd

from packages.domain.models import Bar
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
            warnings.append(f"{symbol}: gap of {diff} days between {dates[i - 1]} and {dates[i]}")
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


# ---------------------------------------------------------------------------
# DataFrame-level quality validation for the historical dataset store.
# ---------------------------------------------------------------------------

NSE_TZ = "Asia/Kolkata"
MARKET_OPEN = (9, 15)
MARKET_CLOSE = (15, 30)


def _status_fail(blocked: bool, detail: str) -> dict:
    return {"status": "FAIL" if blocked else "WARN", "detail": detail}


def check_monotonic(df: pd.DataFrame) -> dict:
    if df.index.is_monotonic_increasing:
        return {"status": "PASS", "detail": "index strictly/NON-monotonic increasing"}
    bad = int((df.index.to_series().diff() < pd.Timedelta(0)).sum())
    return _status_fail(True, f"index not monotonic ({bad} out-of-order rows)")


def check_duplicates(df: pd.DataFrame) -> dict:
    dup = int(df.index.duplicated().sum())
    if dup == 0:
        return {"status": "PASS", "detail": "no duplicate timestamps"}
    return _status_fail(True, f"{dup} duplicate timestamps")


def check_missing(df: pd.DataFrame, timeframe: str) -> dict:
    n = len(df)
    if n < 2:
        return _status_fail(True, "fewer than 2 bars")
    span = df.index[-1] - df.index[0]
    if timeframe == "d1d":
        expected = pd.bdate_range(df.index[0], df.index[-1])
        missing = len(expected) - n
        ratio = missing / len(expected)
        if missing <= 0:
            return {"status": "PASS", "detail": "no missing business days"}
        detail = f"{missing} missing business days ({ratio:.1%}; NSE holidays expected)"
        return {"status": "WARN", "detail": detail} if ratio < 0.10 else _status_fail(True, detail)
    expected_interval = pd.Timedelta(minutes=1) if timeframe == "1m" else pd.Timedelta(minutes=15)
    idx = df.index.to_series()
    same_day = idx.shift(1).dt.date == idx.dt.date
    gaps = idx.diff().dropna()
    within_session = gaps[same_day[1:].values]
    big = int((within_session > expected_interval * 2).sum())
    detail = f"{big} within-session gaps > {expected_interval*2}"
    return {"status": "WARN", "detail": detail} if big else {"status": "PASS", "detail": detail}


def check_ohlc_relationship(df: pd.DataFrame) -> dict:
    bad = int(
        (
            (df["high"] < df[["open", "close"]].max(axis=1))
            | (df["low"] > df[["open", "close"]].min(axis=1))
            | (df["low"] > df["high"])
        ).sum()
    )
    if bad == 0:
        return {"status": "PASS", "detail": "high>=max(o,c), low<=min(o,c), low<=high"}
    return _status_fail(True, f"{bad} rows violate OHLC ordering (high>=max(o,c) & low<=min(o,c))")


def check_prices_positive(df: pd.DataFrame) -> dict:
    bad = int((df[["open", "high", "low", "close"]] <= 0).any(axis=1).sum())
    if bad == 0:
        return {"status": "PASS", "detail": "all OHLC prices positive"}
    return _status_fail(True, f"{bad} rows with zero/negative prices")


def check_volume(df: pd.DataFrame, timeframe: str) -> dict:
    if "volume" not in df.columns:
        return {"status": "PASS", "detail": "no volume column"}
    neg = int((df["volume"] < 0).sum())
    zero = int((df["volume"] == 0).sum())
    if neg:
        return _status_fail(True, f"{neg} rows with negative volume")
    detail = f"{zero} zero-volume rows"
    return {"status": "WARN", "detail": detail} if zero else {"status": "PASS", "detail": "volume>0"}


def check_timezone(df: pd.DataFrame) -> dict:
    tz = getattr(df.index, "tz", None)
    if tz is not None and str(tz) == NSE_TZ:
        return {"status": "PASS", "detail": f"tz={tz}"}
    if tz is not None:
        return _status_fail(True, f"wrong timezone: {tz} (expected {NSE_TZ})")
    return _status_fail(True, "index is timezone-naive")


def check_session_alignment(df: pd.DataFrame, timeframe: str) -> dict:
    if timeframe == "d1d":
        weekend = int((df.index.dayofweek >= 5).sum())
        if weekend == 0:
            return {"status": "PASS", "detail": "no weekend bars"}
        return _status_fail(
            False,
            f"{weekend} weekend bars (documented NSE special sessions; kept if volume>0)",
        )
    outside = int(
        (
            df.index.to_series()
            .apply(
                lambda ts: (
                    ts.hour < MARKET_OPEN[0]
                    or (ts.hour == MARKET_OPEN[0] and ts.minute < MARKET_OPEN[1])
                    or ts.hour > MARKET_CLOSE[0]
                    or (ts.hour == MARKET_CLOSE[0] and ts.minute > MARKET_CLOSE[1])
                    or ts.dayofweek >= 5
                )
            )
        ).sum()
    )
    if outside == 0:
        return {"status": "PASS", "detail": "bars within NSE session (09:15-15:30 IST, weekdays)"}
    return _status_fail(False, f"{outside} bars outside NSE session hours")


def check_corporate_action_spikes(df: pd.DataFrame) -> dict:
    if len(df) < 2:
        return {"status": "PASS", "detail": "too few bars"}
    ret = df["close"].pct_change().abs()
    spikes = int((ret > 0.20).sum())
    if spikes == 0:
        return {"status": "PASS", "detail": "no >20% single-day price moves"}
    return _status_fail(False, f"{spikes} single-day |return|>20% (possible corp-action artifact)")


def validate_dataset(df: pd.DataFrame, symbol: str, timeframe: str) -> dict:
    checks = [
        ("monotonic", check_monotonic(df)),
        ("duplicates", check_duplicates(df)),
        ("missing", check_missing(df, timeframe)),
        ("ohlc_relationship", check_ohlc_relationship(df)),
        ("prices_positive", check_prices_positive(df)),
        ("volume", check_volume(df, timeframe)),
        ("timezone", check_timezone(df)),
        ("session_alignment", check_session_alignment(df, timeframe)),
        ("corporate_action_spikes", check_corporate_action_spikes(df)),
    ]
    hard_fails = [c for c, r in checks if r["status"] == "FAIL"]
    has_warn = any(r["status"] == "WARN" for _, r in checks)
    overall = "PASS" if not hard_fails and not has_warn else ("FAIL" if hard_fails else "WARN")
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "bars": int(len(df)),
        "overall": overall,
        "checks": [{"check": name, **result} for name, result in checks],
    }


def quarantine_rows(df: pd.DataFrame, timeframe: str) -> tuple[pd.DataFrame, list[dict]]:
    """Remove unvalidatable bars from a stored frame and report what was removed.

    Policy
      * d1d: any zero-volume row is quarantined (market-wide flat stubs /
        non-trading-day artifacts); zero volume cannot be validated as a trade.
      * all timeframes: non-positive prices and OHLC-order violations are
        quarantined as unvalidatable rows.
    Weekend bars with real volume (documented special sessions) are KEPT.
    """
    removed: list[dict] = []
    mask = pd.Series(True, index=df.index)
    if timeframe == "d1d":
        zv = df.index[df["volume"] == 0]
        if len(zv):
            mask = mask & ~df.index.isin(zv)
            removed.extend(
                {"ts": str(ts), "reason": "zero-volume stub (quarantined)"} for ts in zv
            )
    nonpos = (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
    bad_ohlc = (
        (df["high"] < df[["open", "close"]].max(axis=1))
        | (df["low"] > df[["open", "close"]].min(axis=1))
        | (df["low"] > df["high"])
    )
    for flag, reason in ((nonpos, "non-positive price"), (bad_ohlc, "OHLC ordering violation")):
        bad_ts = df.index[flag & mask]
        if len(bad_ts):
            mask = mask & ~df.index.isin(bad_ts)
            removed.extend({"ts": str(ts), "reason": reason} for ts in bad_ts)
    if not removed:
        return df, removed
    return df[mask].copy(), removed
