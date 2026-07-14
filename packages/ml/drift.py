"""Drift detection — data drift and concept drift monitoring."""

import numpy as np
from scipy.stats import ks_2samp, wasserstein_distance

from packages.core.logging import get_logger

logger = get_logger("drift_detection")


def detect_data_drift(reference: np.ndarray, current: np.ndarray, threshold: float = 0.05) -> dict:
    if len(reference) < 10 or len(current) < 10:
        return {"drift_detected": False, "error": "Insufficient samples"}
    stat, p_value = ks_2samp(reference, current)
    drift = bool(p_value < threshold)
    wass_dist = float(wasserstein_distance(reference, current))
    return {
        "drift_detected": drift,
        "test": "ks",
        "statistic": round(float(stat), 4),
        "p_value": round(float(p_value), 4),
        "wasserstein_distance": round(wass_dist, 4),
        "threshold": threshold,
        "reference_mean": round(float(np.mean(reference)), 4),
        "current_mean": round(float(np.mean(current)), 4),
    }


def detect_concept_drift(
    predicted: np.ndarray,
    actual: np.ndarray,
    window: int = 20,
    threshold: float = 0.1,
) -> dict:
    if len(predicted) != len(actual) or len(predicted) < window:
        return {"drift_detected": False, "error": "Insufficient aligned data"}
    errors = np.abs(predicted - actual)
    rolling_error = np.array([
        np.mean(errors[max(0, i - window):i])
        for i in range(1, len(errors) + 1)
    ])
    baseline_error = np.mean(errors[:window])
    current_error = rolling_error[-1] if len(rolling_error) else 0
    drift = current_error > baseline_error * (1 + threshold)
    return {
        "drift_detected": bool(drift),
        "baseline_error": round(float(baseline_error), 4),
        "current_error": round(float(current_error), 4),
        "threshold_multiplier": 1 + threshold,
        "drift_magnitude": round(float(current_error / max(baseline_error, 1e-10)), 4),
    }


def multivariate_drift(reference: np.ndarray, current: np.ndarray) -> dict:
    results = {}
    if reference.ndim == 1:
        reference = reference.reshape(-1, 1)
    if current.ndim == 1:
        current = current.reshape(-1, 1)
    for i in range(reference.shape[1]):
        results[f"dim_{i}"] = detect_data_drift(reference[:, i], current[:, i])
    n_drifted = sum(1 for r in results.values() if r.get("drift_detected"))
    return {"features": results, "n_drifted": n_drifted, "total_features": reference.shape[1]}
