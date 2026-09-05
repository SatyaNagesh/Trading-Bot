"""Strategy interface for the research tournament.

A strategy is a pure, **causal** mapping from a feature frame (columns produced
by :mod:`packages.research.features`) to a target-position series over
``{-1, 0, +1}`` meaning short / flat / long. The mapping at index ``t`` may only
use feature values at-or-before ``t`` (the features themselves are already
causal). Execution of the position is handled uniformly by the execution module
(a one-bar fill delay + identical costs for every candidate), so candidates
cannot game transaction costs or look-ahead.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class BaseStrategy(ABC):
    """Common contract for a tournament strategy candidate."""

    name: str
    params: dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    def decide(self, features: pd.DataFrame) -> pd.Series:
        """Return target position series over {-1, 0, +1} aligned to features.index.

        Must be causal: the value at t depends only on feature rows at-or-before t.
        """

    def describe(self) -> str:
        """Human-readable statement of the rule (single-line)."""
        return self.name

    def features_used(self) -> list[str]:
        """Columns of the feature frame this strategy consumes (for the docs)."""
        return []

    # --- helpers -----------------------------------------------------------
    @staticmethod
    def _cross_above(a: pd.Series, b: pd.Series) -> pd.Series:
        """1 where a crosses above b, else 0 (causal)."""
        return ((a > b) & (a.shift(1) <= b.shift(1))).astype(float)

    @staticmethod
    def _cross_below(a: pd.Series, b: pd.Series) -> pd.Series:
        return ((a < b) & (a.shift(1) >= b.shift(1))).astype(float)

    def sign(self, s: pd.Series) -> pd.Series:
        """Map boolean series -> position, aligning index and forward-filling warm-up."""
        out = s.astype(float)
        out[out.abs() < 0.5] = 0.0
        return out
