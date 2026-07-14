"""Live P&L tracker — real-time portfolio tracking."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from packages.core.logging import get_logger

logger = get_logger("live_pnl")


@dataclass
class PnLRecord:
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    equity: float = 0.0
    cash: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    drawdown: float = 0.0


class LivePnLTracker:
    def __init__(self, initial_capital: float = 1_000_000):
        self.initial_capital = initial_capital
        self.peak_equity = initial_capital
        self.records: list[PnLRecord] = []
        self._realized = 0.0
        self._unrealized = 0.0

    def update(self, cash: float, positions_value: float) -> PnLRecord:
        equity = cash + positions_value
        self.peak_equity = max(self.peak_equity, equity)
        self._unrealized = positions_value
        record = PnLRecord(
            equity=equity,
            cash=cash,
            unrealized_pnl=self._unrealized,
            realized_pnl=self._realized,
            total_pnl=equity - self.initial_capital,
            drawdown=(self.peak_equity - equity) / max(self.peak_equity, 1) * 100,
        )
        self.records.append(record)
        return record

    def add_realized_pnl(self, pnl: float) -> None:
        self._realized += pnl

    def summary(self) -> dict:
        if not self.records:
            return {"error": "No records"}
        latest = self.records[-1]
        return {
            "initial_capital": self.initial_capital,
            "current_equity": round(latest.equity, 2),
            "total_pnl": round(latest.total_pnl, 2),
            "return_pct": round((latest.equity - self.initial_capital) / self.initial_capital * 100, 2),
            "unrealized": round(latest.unrealized_pnl, 2),
            "realized": round(latest.realized_pnl, 2),
            "current_drawdown": round(latest.drawdown, 2),
            "peak_equity": round(self.peak_equity, 2),
        }
