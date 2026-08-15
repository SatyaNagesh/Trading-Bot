"""Strategy Degradation Detection — automatic detection of degrading strategy performance."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from packages.analytics.strategy_tracker import StrategyTracker


class StrategyHealth(str, Enum):
    ACTIVE = "ACTIVE"
    WATCHLIST = "WATCHLIST"
    DEGRADED = "DEGRADED"
    RETIRED = "RETIRED"


class DegradationDetector:
    def __init__(self, tracker: StrategyTracker, threshold: float = 0.2):
        self.tracker = tracker
        self.threshold = threshold
        self._health_states: dict[str, StrategyHealth] = {}
        self._degradation_log: list[dict[str, Any]] = []

    def _detect_sharpe_fall(self, perf) -> bool:
        life = perf.lifetime()
        rec = perf.recent()
        l_sharpe = life.get("sharpe_ratio", 0)
        r_sharpe = rec.get("sharpe_ratio", 0)
        if l_sharpe > 0 and r_sharpe < l_sharpe * (1 - self.threshold):
            return True
        return False

    def _detect_drawdown_rise(self, perf) -> bool:
        life = perf.lifetime()
        rec = perf.recent()
        l_dd = life.get("max_drawdown", 0)
        r_dd = rec.get("max_drawdown", 0)
        if l_dd > 0 and r_dd > l_dd * (1 + self.threshold):
            return True
        return False

    def _detect_win_rate_fall(self, perf) -> bool:
        life = perf.lifetime()
        rec = perf.recent()
        l_wr = life.get("win_rate", 0)
        r_wr = rec.get("win_rate", 0)
        if l_wr > 0 and r_wr < l_wr * (1 - self.threshold):
            return True
        return False

    def _detect_expectancy_fall(self, perf) -> bool:
        life = perf.lifetime()
        rec = perf.recent()
        l_exp = life.get("expectancy", 0)
        r_exp = rec.get("expectancy", 0)
        if l_exp > 0 and r_exp < l_exp * (1 - self.threshold):
            return True
        return False

    def _detect_market_drift(self, perf) -> bool:
        life = perf.lifetime()
        rec = perf.recent()
        if life.get("total_trades", 0) < 10:
            return False
        l_pf = life.get("profit_factor", 0)
        r_pf = rec.get("profit_factor", 0)
        if l_pf > 1.5 and r_pf < 1.0:
            return True
        return False

    def evaluate(self, strategy_id: str) -> tuple[StrategyHealth, list[str]]:
        perf = self.tracker.get(strategy_id)
        if perf is None:
            return StrategyHealth.ACTIVE, []

        failures = []
        if self._detect_sharpe_fall(perf):
            failures.append("sharpe_fall")
        if self._detect_drawdown_rise(perf):
            failures.append("drawdown_rise")
        if self._detect_win_rate_fall(perf):
            failures.append("win_rate_fall")
        if self._detect_expectancy_fall(perf):
            failures.append("expectancy_fall")
        if self._detect_market_drift(perf):
            failures.append("market_drift")

        current = self._health_states.get(strategy_id, StrategyHealth.ACTIVE)
        new_health = self._determine_health(current, failures)
        self._health_states[strategy_id] = new_health

        if new_health != current:
            self._degradation_log.append(
                {
                    "strategy_id": strategy_id,
                    "from": current.value,
                    "to": new_health.value,
                    "reasons": failures,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        return new_health, failures

    def _determine_health(self, current: StrategyHealth, failures: list[str]) -> StrategyHealth:
        if current == StrategyHealth.RETIRED:
            return StrategyHealth.RETIRED
        fail_count = len(failures)
        if fail_count >= 4:
            return StrategyHealth.RETIRED
        if fail_count >= 3:
            return StrategyHealth.DEGRADED
        if fail_count >= 1:
            return StrategyHealth.WATCHLIST
        return StrategyHealth.ACTIVE

    def evaluate_all(self) -> dict[str, tuple[StrategyHealth, list[str]]]:
        results = {}
        for sid in self.tracker._strategies:
            results[sid] = self.evaluate(sid)
        return results

    def get_health(self, strategy_id: str) -> StrategyHealth:
        return self._health_states.get(strategy_id, StrategyHealth.ACTIVE)

    def get_degraded_strategies(self) -> list[tuple[str, StrategyHealth, list[str]]]:
        results = []
        for sid, health in self._health_states.items():
            if health in (
                StrategyHealth.WATCHLIST,
                StrategyHealth.DEGRADED,
                StrategyHealth.RETIRED,
            ):
                _, failures = self.evaluate(sid)
                results.append((sid, health, failures))
        return results

    def degradation_history(self, limit: int = 100) -> list[dict[str, Any]]:
        return list(reversed(self._degradation_log))[:limit]

    def health_summary(self) -> dict[str, int]:
        summary = {h.value: 0 for h in StrategyHealth}
        for health in self._health_states.values():
            if health.value in summary:
                summary[health.value] += 1
        return summary
