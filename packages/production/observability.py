"""Observability — operational health dashboard with live metrics."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class MetricPoint:
    name: str
    value: float
    timestamp: str
    labels: dict[str, str] = field(default_factory=dict)


class MetricCollector:
    def __init__(self, max_points_per_metric: int = 1000):
        self._metrics: dict[str, deque[MetricPoint]] = {}
        self._max = max_points_per_metric
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}

    def increment(self, name: str, amount: int = 1, labels: dict[str, str] | None = None) -> None:
        self._counters[name] = self._counters.get(name, 0) + amount
        self._record(name, float(self._counters[name]), labels)

    def gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        self._gauges[name] = value
        self._record(name, value, labels)

    def timing(self, name: str, duration_ms: float, labels: dict[str, str] | None = None) -> None:
        self._record(f"{name}_ms", duration_ms, labels)

    def _record(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        if name not in self._metrics:
            self._metrics[name] = deque(maxlen=self._max)
        self._metrics[name].append(
            MetricPoint(
                name=name,
                value=value,
                timestamp=datetime.now(timezone.utc).isoformat(),
                labels=labels or {},
            )
        )

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0.0)

    def get_series(self, name: str, limit: int = 100) -> list[MetricPoint]:
        if name not in self._metrics:
            return []
        return list(self._metrics[name])[-limit:]

    def snapshot(self) -> dict[str, Any]:
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "series_counts": {k: len(v) for k, v in self._metrics.items()},
        }

    def reset(self) -> None:
        self._metrics.clear()
        self._counters.clear()
        self._gauges.clear()


class OperationalDashboard:
    def __init__(self, metrics: MetricCollector | None = None):
        self.metrics = metrics or MetricCollector()
        self._extra_data: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._extra_data[key] = value

    def update_trading(self, trade_count: int, open_positions: int, pnl: float) -> None:
        self.metrics.gauge("trade_count", trade_count)
        self.metrics.gauge("open_positions", open_positions)
        self.metrics.gauge("current_pnl", pnl)

    def update_system(self, cpu_pct: float, ram_mb: float, uptime_hours: float) -> None:
        self.metrics.gauge("cpu_pct", cpu_pct)
        self.metrics.gauge("ram_mb", ram_mb)
        self.metrics.gauge("uptime_hours", uptime_hours)

    def update_strategies(self, total: int, active: int, degraded: int) -> None:
        self.metrics.gauge("strategies_total", total)
        self.metrics.gauge("strategies_active", active)
        self.metrics.gauge("strategies_degraded", degraded)

    def update_experiments(self, total: int, running: int, promoted: int) -> None:
        self.metrics.gauge("experiments_total", total)
        self.metrics.gauge("experiments_running", running)
        self.metrics.gauge("experiments_promoted", promoted)

    def update_alerts(self, active_count: int, critical_count: int) -> None:
        self.metrics.gauge("alerts_active", active_count)
        self.metrics.gauge("alerts_critical", critical_count)

    def update_scheduler(self, cycle_count: int, is_running: bool) -> None:
        self.metrics.gauge("scheduler_cycles", cycle_count)
        self.metrics.gauge("scheduler_running", 1.0 if is_running else 0.0)

    def update_database(self, total_entries: int, checkpoint_count: int) -> None:
        self.metrics.gauge("db_entries", total_entries)
        self.metrics.gauge("db_checkpoints", checkpoint_count)

    def render(self) -> str:
        s = self.metrics.snapshot()
        gauges = s["gauges"]
        extra = self._extra_data

        lines = [
            "╔══════════════════════════════════════╗",
            "║     QUANTLAB OPERATIONAL DASHBOARD   ║",
            "╚══════════════════════════════════════╝",
            "",
        ]

        lines.append("── Trading ──")
        lines.append(f"  Trades:          {gauges.get('trade_count', 0):>8.0f}")
        lines.append(f"  Open Positions:  {gauges.get('open_positions', 0):>8.0f}")
        lines.append(f"  Current PnL:     {gauges.get('current_pnl', 0):>10.2f}")
        lines.append("")

        lines.append("── System ──")
        lines.append(f"  CPU:             {gauges.get('cpu_pct', 0):>8.1f}%")
        lines.append(f"  RAM:             {gauges.get('ram_mb', 0):>8.0f} MB")
        lines.append(f"  Uptime:          {gauges.get('uptime_hours', 0):>8.1f} h")
        lines.append("")

        lines.append("── Strategies ──")
        lines.append(f"  Total:           {gauges.get('strategies_total', 0):>8.0f}")
        lines.append(f"  Active:          {gauges.get('strategies_active', 0):>8.0f}")
        lines.append(f"  Degraded:        {gauges.get('strategies_degraded', 0):>8.0f}")
        lines.append("")

        lines.append("── Experiments ──")
        lines.append(f"  Total:           {gauges.get('experiments_total', 0):>8.0f}")
        lines.append(f"  Running:         {gauges.get('experiments_running', 0):>8.0f}")
        lines.append(f"  Promoted:        {gauges.get('experiments_promoted', 0):>8.0f}")
        lines.append("")

        lines.append("── Alerts ──")
        lines.append(f"  Active:          {gauges.get('alerts_active', 0):>8.0f}")
        lines.append(f"  Critical:        {gauges.get('alerts_critical', 0):>8.0f}")
        lines.append("")

        lines.append("── Scheduler ──")
        lines.append(f"  Cycles:          {gauges.get('scheduler_cycles', 0):>8.0f}")
        lines.append(
            f"  Running:         {'Yes' if gauges.get('scheduler_running', 0) else 'No':>8}"
        )
        lines.append("")

        lines.append("── Database ──")
        lines.append(f"  Entries:         {gauges.get('db_entries', 0):>8.0f}")
        lines.append(f"  Checkpoints:     {gauges.get('db_checkpoints', 0):>8.0f}")
        lines.append("")

        for k, v in extra.items():
            lines.append(f"── {k} ──")
            if isinstance(v, dict):
                for sk, sv in v.items():
                    lines.append(f"  {sk}: {sv}")
            else:
                lines.append(f"  {v}")
            lines.append("")

        lines.append(f"  Last updated: {datetime.now(timezone.utc).isoformat()}")
        lines.append("")

        return "\n".join(lines)
