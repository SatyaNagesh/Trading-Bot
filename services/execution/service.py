"""Execution Engine — order management and execution simulation."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from packages.broker.gateway import create_broker, BrokerConfig
from packages.core.logging import get_logger
from packages.domain.models import Order, OrderStatus, OrderType, Side
from packages.knowledge.graph import create_entity, find_entities

logger = get_logger("execution_service")


async def submit_order(
    symbol: str,
    side: str,
    quantity: int,
    order_type: str = "MARKET",
    price: float | None = None,
    strategy_id: str = "",
) -> dict:
    order = Order(
        strategy_id=strategy_id,
        portfolio_id="default",
        symbol=symbol,
        side=Side(side.upper()),
        order_type=OrderType(order_type.upper()),
        quantity=quantity,
        price=Decimal(str(price)) if price else None,
    )
    broker = create_broker(BrokerConfig())
    status = await broker.place_order(order)
    props = {
        "symbol": order.symbol,
        "side": order.side.value,
        "quantity": order.quantity,
        "order_type": order.order_type.value,
        "status": status.value,
        "strategy_id": order.strategy_id,
    }
    result = await create_entity("Order", props)
    logger.info("order_submitted", symbol=symbol, side=side)
    return result


async def list_orders(strategy_id: str | None = None) -> list[dict]:
    filters = {"strategy_id": strategy_id} if strategy_id else None
    return await find_entities("Order", filters)


async def simulate_order_book(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "bids": [{"price": 100.5, "quantity": 1000}, {"price": 100.0, "quantity": 2000}],
        "asks": [{"price": 101.0, "quantity": 1500}, {"price": 101.5, "quantity": 1000}],
        "spread": 0.5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
