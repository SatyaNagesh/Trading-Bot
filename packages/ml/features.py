"""Feature store — centralized feature computation and retrieval."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from packages.core.logging import get_logger
from packages.domain.models import Bar

logger = get_logger("feature_store")


@dataclass
class FeatureDefinition:
    name: str
    function: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    category: str = "technical"
    version: str = "1.0"


class FeatureStore:
    def __init__(self):
        self.registry: dict[str, FeatureDefinition] = {}
        self._cache: dict[str, np.ndarray] = {}

    def register(self, feature: FeatureDefinition) -> None:
        self.registry[feature.name] = feature
        logger.info("feature_registered", name=feature.name)

    def compute(self, name: str, bars: list[Bar]) -> np.ndarray | None:
        closes = np.array([float(b.close) for b in bars])
        highs = np.array([float(b.high) for b in bars])
        lows = np.array([float(b.low) for b in bars])
        volumes = np.array([float(b.volume) for b in bars])
        if name == "returns":
            return np.diff(closes) / closes[:-1]
        elif name == "log_returns":
            return np.diff(np.log(closes + 1e-10))
        elif name == "volume_ma_20":
            return pd.Series(volumes).rolling(20).mean().values
        elif name == "high_low_ratio":
            return (highs - lows) / closes
        elif name == "spread":
            return (highs - lows) / ((highs + lows) / 2 + 1e-10)
        return None

    def compute_batch(self, names: list[str], bars: list[Bar]) -> dict[str, np.ndarray]:
        return {n: self.compute(n, bars) for n in names if self.compute(n, bars) is not None}


_feature_store = FeatureStore()
_feature_store.register(FeatureDefinition("returns", category="derived"))
_feature_store.register(FeatureDefinition("log_returns", category="derived"))
_feature_store.register(FeatureDefinition("volume_ma_20", category="liquidity"))
_feature_store.register(FeatureDefinition("high_low_ratio", category="volatility"))
_feature_store.register(FeatureDefinition("spread", category="microstructure"))
