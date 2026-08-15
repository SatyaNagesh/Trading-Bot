"""Alert Engine — degradation, regime, and performance alerts."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from packages.analytics.degradation import DegradationDetector, StrategyHealth
from packages.analytics.regime_observer import RegimeObserver
from packages.analytics.strategy_tracker import StrategyTracker


class AlertSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertCategory(str, Enum):
    DEGRADATION = "degradation"
    REGIME = "regime"
    PERFORMANCE = "performance"
    HEALTH = "health"
    MILESTONE = "milestone"


class AlertEngine:
    def __init__(
        self,
        tracker: StrategyTracker | None = None,
        detector: DegradationDetector | None = None,
        regime_observer: RegimeObserver | None = None,
    ):
        self.tracker = tracker
        self.detector = detector
        self.regime_observer = regime_observer
        self._alerts: list[dict[str, Any]] = []
        self._last_regime: str | None = None
        self._milestone_thresholds: dict[str, float] = {
            "total_trades": [10, 50, 100, 500, 1000],
            "win_rate": [40.0, 50.0, 60.0, 70.0, 80.0],
            "sharpe_ratio": [0.5, 1.0, 1.5, 2.0, 3.0],
        }

    def check_all(self) -> list[dict[str, Any]]:
        new_alerts: list[dict[str, Any]] = []
        new_alerts.extend(self.check_degradation_alerts())
        new_alerts.extend(self.check_regime_alerts())
        new_alerts.extend(self.check_performance_alerts())
        self._alerts.extend(new_alerts)
        return new_alerts

    def check_degradation_alerts(self) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        if not self.detector:
            return alerts
        history = self.detector.degradation_history(limit=10)
        for entry in history:
            if self._already_seen(entry) or self._in_list(entry, alerts):
                continue
            to_health = entry.get("to", "")
            severity = self._health_to_severity(to_health)
            alerts.append(
                self._alert(
                    category=AlertCategory.DEGRADATION,
                    severity=severity,
                    message=(
                        f"Strategy {entry['strategy_id']} transitioned from "
                        f"{entry['from']} to {entry['to']}: {', '.join(entry['reasons'])}"
                    ),
                    source="DegradationDetector",
                    data=entry,
                )
            )
        return alerts

    def check_regime_alerts(self) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        if not self.regime_observer:
            return alerts
        current = self.regime_observer.current_regime.value
        if self._last_regime is None:
            self._last_regime = current
            return alerts
        if current != self._last_regime:
            severity = AlertSeverity.MEDIUM if current == "crisis" else AlertSeverity.LOW
            alerts.append(
                self._alert(
                    category=AlertCategory.REGIME,
                    severity=severity,
                    message=f"Market regime changed: {self._last_regime} -> {current}",
                    source="RegimeObserver",
                    data={"from": self._last_regime, "to": current},
                )
            )
            self._last_regime = current
        return alerts

    def check_performance_alerts(self) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        if not self.tracker:
            return alerts
        for sid, perf in self.tracker._strategies.items():
            life = perf.lifetime()
            alerts.extend(self._check_milestones(sid, life))
            degrading, warnings = perf.is_degrading()
            if degrading:
                alert_id = f"degrading-{sid}"
                if not self._has_recent_alert(alert_id, hours=24):
                    alerts.append(
                        self._alert(
                            category=AlertCategory.PERFORMANCE,
                            severity=AlertSeverity.MEDIUM,
                            message=f"Strategy {sid} is degrading: {'; '.join(warnings)}",
                            source="StrategyTracker.is_degrading",
                            data={"strategy_id": sid, "warnings": warnings},
                            alert_id=alert_id,
                        )
                    )
        return alerts

    def _check_milestones(self, strategy_id: str, life: dict[str, Any]) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        for metric, thresholds in self._milestone_thresholds.items():
            value = life.get(metric, 0)
            for threshold in thresholds:
                ms_id = f"milestone-{strategy_id}-{metric}-{threshold}"
                if value >= threshold and not self._has_recent_alert(ms_id, hours=72):
                    severity = self._milestone_severity(metric, threshold)
                    alerts.append(
                        self._alert(
                            category=AlertCategory.MILESTONE,
                            severity=severity,
                            message=f"Strategy {strategy_id} reached {metric}={value:.1f} (threshold: {threshold})",
                            source=f"milestone:{metric}",
                            data={
                                "strategy_id": strategy_id,
                                "metric": metric,
                                "value": value,
                                "threshold": threshold,
                            },
                            alert_id=ms_id,
                        )
                    )
        return alerts

    def alerts(
        self,
        level: AlertSeverity | None = None,
        category: AlertCategory | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        result = list(reversed(self._alerts))
        if level:
            severity_order = [s.value for s in AlertSeverity]
            min_idx = severity_order.index(level.value)
            result = [a for a in result if severity_order.index(a["severity"]) >= min_idx]
        if category:
            result = [a for a in result if a["category"] == category.value]
        return result[:limit]

    def clear_alerts(self) -> None:
        self._alerts.clear()

    def alert_count(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for a in self._alerts:
            cat = a["category"]
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def _already_seen(self, entry: dict[str, Any]) -> bool:
        for a in self._alerts:
            if a.get("data") == entry:
                return True
        return False

    def _in_list(self, entry: dict[str, Any], alert_list: list[dict[str, Any]]) -> bool:
        for a in alert_list:
            if a.get("data") == entry:
                return True
        return False

    def _has_recent_alert(self, alert_id: str, hours: int) -> bool:
        cutoff = datetime.now(timezone.utc).timestamp() - hours * 3600
        for a in reversed(self._alerts):
            if a.get("id") == alert_id:
                ts = a.get("timestamp", 0)
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts).timestamp()
                    except (ValueError, TypeError):
                        ts = 0
                if ts > cutoff:
                    return True
        return False

    @staticmethod
    def _alert(
        category: AlertCategory,
        severity: AlertSeverity,
        message: str,
        source: str = "",
        data: dict | None = None,
        alert_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "id": alert_id or str(uuid4()),
            "category": category.value,
            "severity": severity.value,
            "message": message,
            "source": source,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _health_to_severity(health: str) -> AlertSeverity:
        return {
            StrategyHealth.WATCHLIST.value: AlertSeverity.LOW,
            StrategyHealth.DEGRADED.value: AlertSeverity.HIGH,
            StrategyHealth.RETIRED.value: AlertSeverity.CRITICAL,
        }.get(health, AlertSeverity.INFO)

    @staticmethod
    def _milestone_severity(metric: str, threshold: float) -> AlertSeverity:
        if threshold >= 1000:
            return AlertSeverity.CRITICAL
        if threshold >= 100:
            return AlertSeverity.HIGH
        if threshold >= 50:
            return AlertSeverity.MEDIUM
        return AlertSeverity.LOW
