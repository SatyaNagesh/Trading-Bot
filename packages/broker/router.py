"""Smart order router — routes orders across simulated venues."""

from dataclasses import dataclass
from packages.core.logging import get_logger

logger = get_logger("smart_order_router")


@dataclass
class Venue:
    name: str
    latency_ms: float = 10.0
    fill_probability: float = 0.95
    spread: float = 0.001
    available: bool = True


class SmartOrderRouter:
    def __init__(self):
        self.venues: list[Venue] = [
            Venue("NSE", latency_ms=5, fill_probability=0.98, spread=0.0005),
            Venue("BSE", latency_ms=8, fill_probability=0.95, spread=0.0008),
            Venue("SIMULATED", latency_ms=1, fill_probability=1.0, spread=0.001),
        ]

    def best_venue(self, quantity: int, is_aggressive: bool = False) -> Venue:
        sorted_venues = sorted(
            self.venues, key=lambda v: v.latency_ms if is_aggressive else v.spread
        )
        for v in sorted_venues:
            if v.available:
                logger.info("router_selected_venue", venue=v.name, qty=quantity)
                return v
        return self.venues[-1]

    def route(self, order: dict) -> dict:
        venue = self.best_venue(order.get("quantity", 1), order.get("aggressive", False))
        return {
            "venue": venue.name,
            "latency_ms": venue.latency_ms,
            "estimated_spread": venue.spread,
            "fill_probability": venue.fill_probability,
            "order": order,
        }


router = SmartOrderRouter()
