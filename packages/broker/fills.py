"""Fill aggregation and reconciliation."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from packages.core.logging import get_logger

logger = get_logger("fill_reconciliation")


@dataclass
class Fill:
    id: str = field(default_factory=lambda: str(uuid4()))
    order_id: str = ""
    symbol: str = ""
    side: str = ""
    quantity: int = 0
    price: Decimal = Decimal("0")
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    venue: str = ""


class FillAggregator:
    def __init__(self):
        self.fills: dict[str, list[Fill]] = {}

    def add_fill(self, fill: Fill) -> None:
        self.fills.setdefault(fill.order_id, []).append(fill)
        logger.debug("fill_recorded", order=fill.order_id, qty=fill.quantity)

    def total_filled(self, order_id: str) -> int:
        return sum(f.quantity for f in self.fills.get(order_id, []))

    def average_price(self, order_id: str) -> Decimal:
        fills = self.fills.get(order_id, [])
        if not fills:
            return Decimal("0")
        total_value = sum(f.quantity * float(f.price) for f in fills)
        total_qty = sum(f.quantity for f in fills)
        return Decimal(str(total_value / max(total_qty, 1)))

    def reconcile(self, order: dict, fills: list[Fill]) -> dict:
        expected = order.get("quantity", 0)
        filled = sum(f.quantity for f in fills)
        avg_price = self.average_price(order.get("id", ""))
        return {
            "order_id": order.get("id", ""),
            "expected_quantity": expected,
            "filled_quantity": filled,
            "remaining": expected - filled,
            "average_price": float(avg_price),
            "status": "filled" if filled >= expected else "partial" if filled > 0 else "unfilled",
            "n_fills": len(fills),
        }


aggregator = FillAggregator()
