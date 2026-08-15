"""Health Monitor — continuous system health checks for paper trading."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from packages.core.logging import get_logger

logger = get_logger("health_monitor")


@dataclass
class HealthStatus:
    broker_connected: bool = True
    market_data_available: bool = True
    execution_latency_ms: float = 0.0
    api_failures: int = 0
    risk_engine_healthy: bool = True
    portfolio_integrity: bool = True
    data_freshness_seconds: float = 0.0
    system_exceptions: int = 0
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    trading_paused: bool = False


class HealthMonitor:
    def __init__(self, max_api_failures: int = 5, max_data_age_seconds: int = 300):
        self.status = HealthStatus()
        self.max_api_failures = max_api_failures
        self.max_data_age = timedelta(seconds=max_data_age_seconds)
        self._alerts: list[dict] = []

    def check_broker(self, connected: bool) -> None:
        self.status.broker_connected = connected
        self.status.last_checked = datetime.now(timezone.utc)
        if not connected:
            self._alert("critical", "Broker disconnected")
            self._pause_trading("Broker connection lost")

    def check_market_data(self, available: bool) -> None:
        self.status.market_data_available = available
        if not available:
            self._alert("warning", "Market data unavailable")

    def check_execution_latency(self, latency_ms: float, threshold_ms: float = 5000) -> None:
        self.status.execution_latency_ms = latency_ms
        if latency_ms > threshold_ms:
            self._alert("warning", f"High execution latency: {latency_ms:.0f}ms")

    def check_api_failure(self) -> None:
        self.status.api_failures += 1
        if self.status.api_failures >= self.max_api_failures:
            self._alert("critical", f"API failure threshold reached: {self.status.api_failures}")
            self._pause_trading("API failure threshold exceeded")

    def check_risk_engine(self, healthy: bool) -> None:
        self.status.risk_engine_healthy = healthy
        if not healthy:
            self._alert("critical", "Risk engine unhealthy")
            self._pause_trading("Risk engine failure")

    def check_portfolio_integrity(self, verified: bool) -> None:
        self.status.portfolio_integrity = verified
        if not verified:
            self._alert("critical", "Portfolio integrity check failed")
            self._pause_trading("Portfolio accounting mismatch")

    def check_data_freshness(self, age_seconds: float) -> None:
        self.status.data_freshness_seconds = age_seconds
        if age_seconds > self.max_data_age.total_seconds():
            self._alert("warning", f"Stale market data: {age_seconds:.0f}s old")
            self._pause_trading("Market data stale")

    def check_system_exception(self) -> None:
        self.status.system_exceptions += 1
        if self.status.system_exceptions >= 3:
            self._alert("critical", f"System exceptions: {self.status.system_exceptions}")
            self._pause_trading("Too many system exceptions")

    def all_healthy(self) -> bool:
        return (
            self.status.broker_connected
            and self.status.market_data_available
            and self.status.risk_engine_healthy
            and self.status.portfolio_integrity
            and not self.status.trading_paused
        )

    def resume_trading(self) -> None:
        self.status.trading_paused = False
        self.status.api_failures = 0
        self.status.system_exceptions = 0
        logger.info("trading_resumed", reason="Manual resume")

    def _pause_trading(self, reason: str) -> None:
        if not self.status.trading_paused:
            self.status.trading_paused = True
            logger.warning("trading_paused", reason=reason)

    def _alert(self, severity: str, message: str) -> None:
        self._alerts.append(
            {
                "severity": severity,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        log_fn = logger.warning if severity == "warning" else logger.error
        log_fn("health_alert", severity=severity, message=message)

    def recent_alerts(self, limit: int = 20) -> list[dict]:
        return list(reversed(self._alerts))[:limit]

    def report(self) -> dict:
        return {
            "healthy": self.all_healthy(),
            "trading_paused": self.status.trading_paused,
            "broker_connected": self.status.broker_connected,
            "market_data_available": self.status.market_data_available,
            "execution_latency_ms": self.status.execution_latency_ms,
            "api_failures": self.status.api_failures,
            "risk_engine_healthy": self.status.risk_engine_healthy,
            "portfolio_integrity": self.status.portfolio_integrity,
            "data_freshness_seconds": self.status.data_freshness_seconds,
            "system_exceptions": self.status.system_exceptions,
            "recent_alerts": len(self._alerts),
            "last_checked": self.status.last_checked.isoformat(),
        }
