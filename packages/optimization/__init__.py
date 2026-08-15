"""Gate 6 — Signal Optimization Layer.

Sits between strategy_fn and PaperTradingLoop.process_signal().
Provides traffic gating, confidence calibration, capital allocation, and alerting.
"""

from packages.optimization.signal_optimizer import (
    SignalOptimizer,
    REGIME_COMPATIBILITY,
)
from packages.optimization.allocation import StrategyAllocator
from packages.optimization.alerts import (
    AlertEngine,
    AlertSeverity,
    AlertCategory,
)

__all__ = [
    "SignalOptimizer",
    "REGIME_COMPATIBILITY",
    "StrategyAllocator",
    "AlertEngine",
    "AlertSeverity",
    "AlertCategory",
]
