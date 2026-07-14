"""ML Engine — model training, prediction, and feature engineering."""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from packages.core.logging import get_logger
from packages.domain.models import Bar

logger = get_logger("ml_engine")


@dataclass
class MLModel:
    name: str
    model: Any = None
    scaler: StandardScaler | None = None
    features: list[str] = field(default_factory=list)
    trained: bool = False


class MLEngine:
    def __init__(self):
        self.models: dict[str, MLModel] = {}

    def create_classifier(self, name: str, model_type: str = "rf") -> MLModel:
        if model_type == "rf":
            model = RandomForestClassifier(n_estimators=100, max_depth=5)
        elif model_type == "lr":
            model = LogisticRegression(max_iter=1000)
        else:
            raise ValueError(f"Unknown model type: {model_type}")
        ml = MLModel(name=name, model=model, scaler=StandardScaler())
        self.models[name] = ml
        return ml

    def create_regressor(self, name: str) -> MLModel:
        model = GradientBoostingRegressor(n_estimators=100, max_depth=3)
        ml = MLModel(name=name, model=model, scaler=StandardScaler())
        self.models[name] = ml
        return ml

    async def train(self, name: str, X: np.ndarray, y: np.ndarray) -> dict:
        ml = self.models.get(name)
        if not ml:
            raise ValueError(f"Model {name} not found")
        X_scaled = ml.scaler.fit_transform(X)
        ml.model.fit(X_scaled, y)
        ml.trained = True
        score = float(ml.model.score(X_scaled, y))
        logger.info("model_trained", name=name, score=round(score, 4))
        return {"name": name, "score": score, "trained": True}

    async def predict(self, name: str, X: np.ndarray) -> np.ndarray:
        ml = self.models.get(name)
        if not ml or not ml.trained:
            raise ValueError(f"Model {name} not found or not trained")
        X_scaled = ml.scaler.transform(X)
        return ml.model.predict(X_scaled)

    async def predict_proba(self, name: str, X: np.ndarray) -> np.ndarray:
        ml = self.models.get(name)
        if not ml or not ml.trained:
            raise ValueError(f"Model {name} not found or not trained")
        X_scaled = ml.scaler.transform(X)
        if hasattr(ml.model, "predict_proba"):
            return ml.model.predict_proba(X_scaled)
        return np.array([])


def compute_features(bars: list[Bar]) -> dict[str, np.ndarray]:
    closes = np.array([float(b.close) for b in bars])
    highs = np.array([float(b.high) for b in bars])
    lows = np.array([float(b.low) for b in bars])
    volumes = np.array([float(b.volume) for b in bars])

    returns = np.diff(closes) / closes[:-1]
    log_returns = np.diff(np.log(closes + 1e-10))

    features = {
        "returns": returns,
        "log_returns": log_returns,
        "volatility": _rolling_std(returns, 20),
        "volume_ratio": volumes[1:] / (volumes[:-1].mean() + 1e-10),
        "high_low_ratio": (highs - lows)[1:] / closes[:-1],
    }
    return features


def _rolling_std(arr: np.ndarray, window: int) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=float)
    for i in range(window - 1, len(arr)):
        result[i] = np.std(arr[i - window + 1 : i + 1])
    return result


def compute_targets(bars: list[Bar], horizon: int = 5) -> np.ndarray:
    closes = np.array([float(b.close) for b in bars])
    future_returns = (closes[horizon:] - closes[:-horizon]) / closes[:-horizon]
    targets = np.where(future_returns > 0, 1, 0)
    return targets
