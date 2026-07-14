"""Multi-currency portfolio support — FX conversion and cross-currency allocation."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from packages.core.logging import get_logger

logger = get_logger("multi_currency")


@dataclass
class FXPosition:
    symbol: str
    currency: str
    quantity: int
    local_price: Decimal
    fx_rate: Decimal = Decimal("1.0")
    base_currency: str = "USD"


class MultiCurrencyPortfolio:
    def __init__(self, base_currency: str = "USD"):
        self.base = base_currency
        self.positions: dict[str, FXPosition] = {}
        self.fx_rates: dict[str, Decimal] = {
            "USD": Decimal("1.0"), "INR": Decimal("0.012"), "EUR": Decimal("1.08"),
            "GBP": Decimal("1.27"), "JPY": Decimal("0.0067"),
        }

    def add_position(self, pos: FXPosition) -> None:
        self.positions[pos.symbol] = pos
        logger.debug("fx_position_added", symbol=pos.symbol, currency=pos.currency)

    def base_value(self, pos: FXPosition) -> Decimal:
        rate = self.fx_rates.get(pos.currency, Decimal("1.0"))
        return pos.local_price * pos.quantity * rate

    def total_value(self) -> Decimal:
        return sum(self.base_value(p) for p in self.positions.values())

    def allocation_by_currency(self) -> dict[str, float]:
        total = self.total_value()
        if total == 0:
            return {}
        alloc = {}
        for p in self.positions.values():
            bv = self.base_value(p)
            alloc[p.currency] = alloc.get(p.currency, 0) + float(bv / total)
        return {k: round(v * 100, 2) for k, v in alloc.items()}

    def summary(self) -> dict:
        return {
            "base_currency": self.base,
            "total_value": float(self.total_value()),
            "n_positions": len(self.positions),
            "currency_allocation": self.allocation_by_currency(),
        }
