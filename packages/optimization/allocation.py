"""Strategy Allocator — capital allocation from performance metrics."""

import math

from packages.analytics.strategy_tracker import StrategyTracker
from packages.analytics.degradation import DegradationDetector, StrategyHealth


class StrategyAllocator:
    def __init__(
        self,
        tracker: StrategyTracker | None = None,
        detector: DegradationDetector | None = None,
    ):
        self.tracker = tracker
        self.detector = detector

    def equal_weight(self, strategy_ids: list[str]) -> dict[str, float]:
        if not strategy_ids:
            return {}
        weight = round(1.0 / len(strategy_ids), 6)
        return {sid: weight for sid in strategy_ids}

    def performance_weighted(self, strategy_ids: list[str]) -> dict[str, float]:
        if not strategy_ids:
            return {}
        if not self.tracker:
            return self.equal_weight(strategy_ids)
        scores: dict[str, float] = {}
        for sid in strategy_ids:
            perf = self.tracker.get(sid)
            if perf is None:
                scores[sid] = 0.0
                continue
            life = perf.lifetime()
            sharpe = life.get("sharpe_ratio", 0) or 0.0
            wr = (life.get("win_rate", 0) or 0.0) / 100.0
            pf = min(life.get("profit_factor", 0) or 0.0, 10.0)
            dd = life.get("max_drawdown", 0) or 0.0
            score = sharpe * 3.0 + wr * 2.0 + pf * 2.0 - dd * 2.0 + perf.stability_score * 1.0
            scores[sid] = max(0.0, score)

        total = sum(scores.values())
        if total <= 0 or not math.isfinite(total):
            return self.equal_weight(list(scores.keys()))
        return {k: round(v / total, 6) for k, v in scores.items()}

    def sharpe_weighted(self, strategy_ids: list[str]) -> dict[str, float]:
        if not strategy_ids:
            return {}
        if not self.tracker:
            return self.equal_weight(strategy_ids)
        scores: dict[str, float] = {}
        for sid in strategy_ids:
            perf = self.tracker.get(sid)
            if perf is None:
                scores[sid] = 0.0
                continue
            life = perf.lifetime()
            sharpe = life.get("sharpe_ratio", 0)
            scores[sid] = max(0.0, sharpe)
        return self._normalize(scores)

    def risk_parity(self, strategy_ids: list[str]) -> dict[str, float]:
        if not strategy_ids:
            return {}
        if not self.tracker:
            return self.equal_weight(strategy_ids)
        scores: dict[str, float] = {}
        for sid in strategy_ids:
            perf = self.tracker.get(sid)
            if perf is None:
                scores[sid] = 0.0
                continue
            life = perf.lifetime()
            dd = life.get("max_drawdown", 0.0)
            score = 1.0 / (1.0 + dd * 5.0)
            scores[sid] = max(0.0, score)
        return self._normalize(scores)

    def health_filtered(self, strategy_ids: list[str]) -> list[str]:
        if not self.detector:
            return list(strategy_ids)
        return [
            sid
            for sid in strategy_ids
            if self.detector.get_health(sid)
            not in (StrategyHealth.DEGRADED, StrategyHealth.RETIRED)
        ]

    def allocate(
        self,
        strategy_ids: list[str],
        method: str = "performance",
    ) -> dict[str, float]:
        filtered = self.health_filtered(strategy_ids)

        if not filtered:
            return {sid: 0.0 for sid in strategy_ids}

        method_map = {
            "equal": self.equal_weight,
            "performance": self.performance_weighted,
            "sharpe": self.sharpe_weighted,
            "risk_parity": self.risk_parity,
        }
        allocator = method_map.get(method, self.performance_weighted)
        result = allocator(filtered)

        for sid in strategy_ids:
            if sid not in result:
                result[sid] = 0.0

        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))

    @staticmethod
    def _normalize(scores: dict[str, float]) -> dict[str, float]:
        total = sum(scores.values())
        if total <= 0 or not math.isfinite(total):
            return {k: 0.0 for k in scores}
        return {k: round(v / total, 6) for k, v in scores.items()}
