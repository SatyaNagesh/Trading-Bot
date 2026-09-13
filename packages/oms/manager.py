"""Order Management System — complete order lifecycle tracking."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from packages.domain.models import Order, OrderStatus, OrderType, Side, TimeInForce
from packages.core.exceptions import OrderRejectedError
from packages.core.logging import get_logger

logger = get_logger("oms")

ORDER_LIFECYCLE: dict[OrderStatus, list[OrderStatus]] = {
    OrderStatus.CREATED: [OrderStatus.VALIDATED, OrderStatus.REJECTED, OrderStatus.CANCELLED],
    OrderStatus.VALIDATED: [OrderStatus.SUBMITTED, OrderStatus.REJECTED, OrderStatus.CANCELLED],
    OrderStatus.SUBMITTED: [
        OrderStatus.PENDING,
        OrderStatus.ACCEPTED,
        OrderStatus.REJECTED,
        OrderStatus.CANCELLED,
    ],
    OrderStatus.PENDING: [OrderStatus.ACCEPTED, OrderStatus.REJECTED, OrderStatus.CANCELLED],
    OrderStatus.ACCEPTED: [
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.EXPIRED,
    ],
    OrderStatus.PARTIALLY_FILLED: [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.EXPIRED],
    OrderStatus.FILLED: [],
    OrderStatus.CANCELLED: [],
    OrderStatus.REJECTED: [],
    OrderStatus.EXPIRED: [],
}


class OrderManager:
    def __init__(self):
        self._orders: dict[str, Order] = {}
        self._transitions: list[dict] = []

    def create_order(
        self,
        strategy_id: str,
        portfolio_id: str,
        symbol: str,
        side: Side,
        order_type: OrderType = OrderType.MARKET,
        quantity: int = 0,
        price: Decimal | None = None,
        stop_price: Decimal | None = None,
        time_in_force: TimeInForce = TimeInForce.DAY,
    ) -> Order:
        order = Order(
            id=str(uuid4()),
            strategy_id=strategy_id,
            portfolio_id=portfolio_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            status=OrderStatus.CREATED,
            created_at=datetime.now(timezone.utc),
        )
        self._orders[order.id] = order
        self._log_transition(order.id, None, OrderStatus.CREATED, "Order created")
        logger.info("order_created", id=order.id, symbol=symbol, side=side.value, qty=quantity)
        return order

    def get_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        active_statuses = {
            OrderStatus.CREATED,
            OrderStatus.VALIDATED,
            OrderStatus.SUBMITTED,
            OrderStatus.PENDING,
            OrderStatus.ACCEPTED,
            OrderStatus.PARTIALLY_FILLED,
        }
        orders = [o for o in self._orders.values() if o.status in active_statuses]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return sorted(orders, key=lambda o: o.created_at, reverse=True)

    def get_all_orders(self, strategy_id: str | None = None) -> list[Order]:
        orders = list(self._orders.values())
        if strategy_id:
            orders = [o for o in orders if o.strategy_id == strategy_id]
        return sorted(orders, key=lambda o: o.created_at, reverse=True)

    def transition(self, order_id: str, new_status: OrderStatus, reason: str = "") -> Order:
        order = self._orders.get(order_id)
        if not order:
            raise OrderRejectedError(f"Order {order_id} not found")

        allowed = ORDER_LIFECYCLE.get(order.status, [])
        if new_status not in allowed:
            raise OrderRejectedError(
                f"Invalid transition {order.status.value} -> {new_status.value} for order {order_id}"
            )

        old_status = order.status
        # Fill bookkeeping for FILLED / PARTIALLY_FILLED is owned by
        # update_fill(); REJECTED / CANCELLED terminal states carry no
        # additional bookkeeping here.
        order.status = new_status
        order.updated_at = datetime.now(timezone.utc)
        self._log_transition(order_id, old_status, new_status, reason)
        logger.info(
            "order_transition",
            id=order_id,
            from_status=old_status.value,
            to_status=new_status.value,
            reason=reason,
        )
        return order

    def update_fill(self, order_id: str, filled_qty: int, fill_price: float) -> Order:
        order = self._orders.get(order_id)
        if not order:
            raise OrderRejectedError(f"Order {order_id} not found")

        order.filled_quantity += filled_qty
        total_value = (
            float(order.average_fill_price or 0) * (order.filled_quantity - filled_qty)
            + fill_price * filled_qty
        )
        order.average_fill_price = total_value / max(order.filled_quantity, 1)

        if order.filled_quantity >= order.quantity:
            self.transition(
                order_id, OrderStatus.FILLED, f"Filled {order.filled_quantity}/{order.quantity}"
            )
        else:
            if order.status != OrderStatus.PARTIALLY_FILLED:
                self.transition(
                    order_id, OrderStatus.PARTIALLY_FILLED, f"Partial fill {filled_qty}"
                )
            order.updated_at = datetime.now(timezone.utc)

        return order

    def reject(self, order_id: str, reason: str = "") -> Order:
        return self.transition(order_id, OrderStatus.REJECTED, reason)

    def cancel(self, order_id: str, reason: str = "") -> Order:
        return self.transition(order_id, OrderStatus.CANCELLED, reason)

    def expire(self, order_id: str, reason: str = "") -> Order:
        return self.transition(order_id, OrderStatus.EXPIRED, reason)

    def validate(self, order_id: str) -> Order:
        return self.transition(order_id, OrderStatus.VALIDATED, "Risk validation passed")

    def submit(self, order_id: str) -> Order:
        return self.transition(order_id, OrderStatus.SUBMITTED, "Submitted to broker")

    def pending(self, order_id: str) -> Order:
        return self.transition(order_id, OrderStatus.PENDING, "Pending broker acknowledgment")

    def accept(self, order_id: str) -> Order:
        return self.transition(order_id, OrderStatus.ACCEPTED, "Accepted by broker")

    def order_count(self) -> dict[str, int]:
        counts: dict[str, int] = {s.value: 0 for s in OrderStatus}
        for o in self._orders.values():
            s = o.status.value
            counts[s] = counts.get(s, 0) + 1
        return counts

    def transition_log(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._transitions))[:limit]

    def _log_transition(
        self, order_id: str, from_status: OrderStatus | None, to_status: OrderStatus, reason: str
    ) -> None:
        self._transitions.append(
            {
                "order_id": order_id,
                "from": from_status.value if from_status else None,
                "to": to_status.value,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
