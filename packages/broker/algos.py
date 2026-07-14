"""Execution algorithms — TWAP, VWAP, Iceberg order scheduling."""

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from packages.core.logging import get_logger
from packages.domain.models import Order, Side, OrderType, OrderStatus

logger = get_logger("execution_algos")


@dataclass
class Slice:
    quantity: int
    price: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    filled: bool = False


class TWAPAlgo:
    def __init__(self, total_quantity: int, slices: int = 10):
        self.total = total_quantity
        self.slices = slices
        self.slice_size = max(1, total_quantity // slices)
        self.completed: list[Slice] = []

    def next_slice(self, current_price: float) -> Slice | None:
        remaining = self.total - sum(s.quantity for s in self.completed)
        if remaining <= 0:
            return None
        qty = min(self.slice_size, remaining)
        sl = Slice(quantity=qty, price=current_price)
        self.completed.append(sl)
        logger.debug("twap_slice", qty=qty, price=current_price)
        return sl

    def progress(self) -> float:
        return sum(s.quantity for s in self.completed) / max(self.total, 1)


class VWAPAlgo:
    def __init__(self, total_quantity: int, volume_profile: list[float] | None = None):
        self.total = total_quantity
        self.volume_profile = volume_profile or [1.0 / 10] * 10
        self.index = 0
        self.completed: list[Slice] = []

    def next_slice(self, current_price: float) -> Slice | None:
        if self.index >= len(self.volume_profile):
            return None
        weight = self.volume_profile[self.index]
        qty = max(1, int(self.total * weight))
        sl = Slice(quantity=qty, price=current_price)
        self.completed.append(sl)
        self.index += 1
        logger.debug("vwap_slice", qty=qty, weight=weight)
        return sl


class IcebergAlgo:
    def __init__(self, total_quantity: int, visible_size: int = 100):
        self.total = total_quantity
        self.visible = visible_size
        self.completed: list[Slice] = []

    def next_slice(self, current_price: float) -> Slice | None:
        remaining = self.total - sum(s.quantity for s in self.completed)
        if remaining <= 0:
            return None
        qty = min(self.visible, remaining)
        sl = Slice(quantity=qty, price=current_price)
        self.completed.append(sl)
        logger.debug("iceberg_slice", qty=qty, visible=self.visible)
        return sl
