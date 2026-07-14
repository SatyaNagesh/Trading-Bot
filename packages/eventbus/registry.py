"""Event type registry with schema validation."""

from dataclasses import dataclass, field
from typing import Any, Callable
from packages.core.logging import get_logger

logger = get_logger("event_registry")


@dataclass
class EventSchema:
    event_type: str
    version: str = "1.0"
    required_fields: list[str] = field(default_factory=list)
    optional_fields: list[str] = field(default_factory=list)
    description: str = ""
    handler: Callable | None = None


class EventRegistry:
    def __init__(self):
        self._schemas: dict[str, EventSchema] = {}

    def register(self, schema: EventSchema) -> None:
        self._schemas[schema.event_type] = schema
        logger.info("event_registered", type=schema.event_type, version=schema.version)

    def get(self, event_type: str) -> EventSchema | None:
        return self._schemas.get(event_type)

    def validate(self, event_type: str, payload: dict) -> dict:
        schema = self._schemas.get(event_type)
        if not schema:
            logger.warning("unknown_event_type", type=event_type)
            return {"valid": False, "error": f"Unknown event type: {event_type}"}
        missing = [f for f in schema.required_fields if f not in payload]
        if missing:
            return {"valid": False, "error": f"Missing required fields: {missing}"}
        return {"valid": True}

    def list_schemas(self) -> list[dict]:
        return [
            {"type": s.event_type, "version": s.version, "description": s.description}
            for s in self._schemas.values()
        ]


registry = EventRegistry()

registry.register(EventSchema(
    event_type="hypothesis.created",
    required_fields=["id", "title", "keywords"],
    description="A new research hypothesis was created",
))
registry.register(EventSchema(
    event_type="strategy.validated",
    required_fields=["id", "name", "sharpe"],
    description="A strategy passed validation",
))
registry.register(EventSchema(
    event_type="backtest.completed",
    required_fields=["id", "strategy_id", "total_return", "sharpe"],
    description="A backtest run completed",
))
registry.register(EventSchema(
    event_type="order.filled",
    required_fields=["order_id", "symbol", "side", "quantity", "price"],
    description="An order was fully filled",
))
registry.register(EventSchema(
    event_type="portfolio.rebalanced",
    required_fields=["portfolio_id", "trades"],
    description="Portfolio rebalancing executed",
))
