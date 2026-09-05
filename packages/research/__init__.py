"""Strategy research tournament framework for QuantLab AI.

Provides the causal feature set, uniform no-look-ahead execution, a full metric
suite, chronological walk-forward, regime breakdown, Monte Carlo, cost/slippage
stress and parameter-neighborhood robustness used to evaluate candidate
strategies on an equal footing.
"""

__all__ = [
    "features",
    "strategy",
    "execution",
    "metrics",
    "candidates",
    "evaluation",
]
