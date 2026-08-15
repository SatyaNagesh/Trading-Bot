"""System Health Monitor — tracks component health and detects anomalies across the autonomous system."""

from datetime import datetime, timezone
from typing import Any


class SystemHealthMonitor:
    def __init__(self):
        self._component_health: dict[str, dict[str, Any]] = {}
        self._alerts: list[dict[str, Any]] = []
        self._check_count = 0

    def register_component(self, name: str, expected_interval_seconds: float = 300) -> None:
        self._component_health[name] = {
            "name": name,
            "status": "unknown",
            "last_heartbeat": None,
            "expected_interval_seconds": expected_interval_seconds,
            "missed_heartbeats": 0,
            "total_checks": 0,
            "error_count": 0,
        }

    def heartbeat(self, component: str) -> None:
        ch = self._component_health.get(component)
        if ch:
            now = datetime.now(timezone.utc)
            if ch["last_heartbeat"]:
                elapsed = (now - datetime.fromisoformat(ch["last_heartbeat"])).total_seconds()
                if elapsed > ch["expected_interval_seconds"] * 2:
                    ch["missed_heartbeats"] += 1
            ch["last_heartbeat"] = now.isoformat()
            ch["status"] = "healthy"
            ch["total_checks"] += 1

    def record_error(self, component: str, error: str) -> None:
        ch = self._component_health.get(component)
        if ch:
            ch["error_count"] += 1
            ch["status"] = "degraded"
        self._alerts.append(
            {
                "component": component,
                "type": "error",
                "message": error,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def check(self) -> dict[str, Any]:
        self._check_count += 1
        now = datetime.now(timezone.utc)
        issues = []

        for name, ch in self._component_health.items():
            if ch["last_heartbeat"]:
                elapsed = (now - datetime.fromisoformat(ch["last_heartbeat"])).total_seconds()
                threshold = ch["expected_interval_seconds"] * 3
                if elapsed > threshold:
                    ch["status"] = "stale"
                    issues.append(f"{name}: no heartbeat for {elapsed:.0f}s")

                if ch["missed_heartbeats"] > 3:
                    ch["status"] = "critical"
                    issues.append(f"{name}: {ch['missed_heartbeats']} missed heartbeats")

        return {
            "check_id": self._check_count,
            "timestamp": now.isoformat(),
            "healthy": len(issues) == 0,
            "issues": issues,
            "component_count": len(self._component_health),
            "components": {
                name: {
                    "status": ch["status"],
                    "last_heartbeat": ch["last_heartbeat"],
                    "error_count": ch["error_count"],
                    "missed_heartbeats": ch["missed_heartbeats"],
                }
                for name, ch in self._component_health.items()
            },
        }

    def get_alerts(self, component: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        results = list(self._alerts)
        if component:
            results = [a for a in results if a["component"] == component]
        return sorted(results, key=lambda a: a["timestamp"], reverse=True)[:limit]

    def summary(self) -> dict[str, Any]:
        total = len(self._component_health)
        healthy = sum(1 for ch in self._component_health.values() if ch["status"] == "healthy")
        degraded = sum(1 for ch in self._component_health.values() if ch["status"] == "degraded")
        critical = sum(1 for ch in self._component_health.values() if ch["status"] == "critical")
        stale = sum(1 for ch in self._component_health.values() if ch["status"] == "stale")
        return {
            "health_checks": self._check_count,
            "components": {
                "total": total,
                "healthy": healthy,
                "degraded": degraded,
                "critical": critical,
                "stale": stale,
            },
            "total_alerts": len(self._alerts),
        }
