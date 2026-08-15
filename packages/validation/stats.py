"""Statistical test suite and results interpretation."""

import numpy as np
from scipy import stats
from packages.core.logging import get_logger

logger = get_logger("validation")


def t_test_strategies(returns_a: np.ndarray, returns_b: np.ndarray) -> dict:
    t_stat, p_value = stats.ttest_ind(returns_a, returns_b, equal_var=False)
    return {
        "test": "welch_t_test",
        "t_statistic": round(float(t_stat), 4),
        "p_value": round(float(p_value), 4),
        "significant": bool(p_value < 0.05),
        "mean_a": round(float(np.mean(returns_a)), 4),
        "mean_b": round(float(np.mean(returns_b)), 4),
    }


def bootstrap_confidence(returns: np.ndarray, n_iterations: int = 1000, ci: float = 0.95) -> dict:
    means = np.zeros(n_iterations)
    for i in range(n_iterations):
        sample = np.random.choice(returns, size=len(returns), replace=True)
        means[i] = np.mean(sample)
    alpha = (1 - ci) / 2
    lower = float(np.percentile(means, alpha * 100))
    upper = float(np.percentile(means, (1 - alpha) * 100))
    return {
        "mean": float(np.mean(returns)),
        "ci_lower": round(lower, 4),
        "ci_upper": round(upper, 4),
        "confidence_level": ci,
        "n_iterations": n_iterations,
    }


def normality_test(returns: np.ndarray) -> dict:
    stat, p_value = stats.shapiro(returns[:5000]) if len(returns) > 5000 else stats.shapiro(returns)
    return {
        "test": "shapiro_wilk",
        "statistic": round(float(stat), 4),
        "p_value": round(float(p_value), 4),
        "normal": bool(p_value >= 0.05),
    }


def strategy_significance(
    strategy_returns: np.ndarray, benchmark_returns: np.ndarray | None = None
) -> dict:
    if benchmark_returns is None:
        benchmark_returns = np.zeros_like(strategy_returns)
    t_test = t_test_strategies(strategy_returns, benchmark_returns)
    bootstrap = bootstrap_confidence(strategy_returns)
    normal = normality_test(strategy_returns)
    info_ratio = _compute_info_ratio(strategy_returns, benchmark_returns)
    return {
        "t_test": t_test,
        "bootstrap": bootstrap,
        "normality": normal,
        "information_ratio": round(info_ratio, 4),
        "conclusion": _interpret_results(t_test, bootstrap),
    }


def _compute_info_ratio(strategy_returns: np.ndarray, benchmark_returns: np.ndarray) -> float:
    excess = strategy_returns - benchmark_returns
    if np.std(excess) == 0:
        return 0.0
    return float(np.mean(excess) / np.std(excess))


def _interpret_results(t_test: dict, bootstrap: dict) -> str:
    if t_test["significant"] and bootstrap["ci_lower"] > 0:
        return "Strategy significantly outperforms with high confidence"
    elif t_test["significant"]:
        return "Strategy shows statistically significant difference"
    else:
        return "No statistically significant difference detected"
