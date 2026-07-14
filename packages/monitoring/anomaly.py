"""Anomaly detection — strategy deviation and behavioral drift."""

import numpy as np

from packages.core.logging import get_logger

logger = get_logger("anomaly_detection")


def zscore_anomaly(values: list[float], threshold: float = 3.0) -> list[dict]:
    arr = np.array(values)
    mean = np.mean(arr)
    std = np.std(arr)
    if std == 0:
        return []
    anomalies = []
    for i, v in enumerate(values):
        z = (v - mean) / std
        if abs(z) > threshold:
            anomalies.append({"index": i, "value": v, "zscore": round(float(z), 2)})
    return anomalies


def drawdown_anomaly(equity_curve: list[float], threshold_pct: float = 5.0) -> list[dict]:
    peak = equity_curve[0]
    anomalies = []
    for i, equity in enumerate(equity_curve):
        if equity > peak:
            peak = equity
        dd = (peak - equity) / max(peak, 1) * 100
        if dd > threshold_pct:
            anomalies.append({"index": i, "equity": equity, "drawdown": round(float(dd), 2)})
    return anomalies


def sharpe_drop_anomaly(sharpe_history: list[float], window: int = 20, drop_threshold: float = 0.5) -> bool:
    if len(sharpe_history) < window * 2:
        return False
    recent = sharpe_history[-window:]
    baseline = sharpe_history[-window * 2:-window]
    baseline_mean = np.mean(baseline)
    recent_mean = np.mean(recent)
    if baseline_mean <= 0:
        return False
    drop = (baseline_mean - recent_mean) / baseline_mean
    return drop > drop_threshold


def strategy_deviation(expected_sharpe: float, actual_sharpe: float, threshold: float = 0.5) -> dict:
    deviation = abs(expected_sharpe - actual_sharpe)
    return {
        "expected_sharpe": expected_sharpe,
        "actual_sharpe": actual_sharpe,
        "deviation": round(deviation, 2),
        "flagged": deviation > threshold,
    }
