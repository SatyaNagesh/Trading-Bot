"""Execution Engine — reliable order execution with retries, partial fills, and recovery."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from packages.broker.gateway import BaseBroker
from packages.core.exceptions import ExecutionError, BrokerError, OrderRejectedError
from packages.core.logging import get_logger
from packages.domain.models import Order, OrderStatus, OrderType, Side, Trade
from packages.oms.manager import OrderManager

logger = get_logger("execution_engine")


class ExecutionEngine:
    def __init__(
        self,
        broker: BaseBroker,
        order_manager: OrderManager,
        max_retries: int = 3,
        retry_delay_ms: int = 500,
        execution_timeout_ms: int = 30000,
    ):
        self.broker = broker
        self.oms = order_manager
        self.max_retries = max_retries
        self.retry_delay = retry_delay_ms / 1000.0
        self.execution_timeout = execution_timeout_ms / 1000.0
        self._pending_orders: dict[str, asyncio.Task] = {}
        self._executed_order_ids: set[str] = set()

    def _check_duplicate(self, order: Order) -> None:
        if order.id in self._executed_order_ids:
            raise ExecutionError(f"Duplicate order {order.id} — already executed")
        self._executed_order_ids.add(order.id)

    async def execute(self, order: Order) -> Order:
        self._check_duplicate(order)
        self.oms.validate(order.id)
        self.oms.submit(order.id)

        for attempt in range(1, self.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    self.broker.place_order(order),
                    timeout=self.execution_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning("execution_timeout", order=order.id, attempt=attempt)
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay)
                    continue
                self.oms.reject(order.id, f"Execution timeout after {self.max_retries} attempts")
                raise ExecutionError(f"Order {order.id} timed out after {self.max_retries} retries")
            except BrokerError as e:
                logger.error("broker_error", order=order.id, error=str(e), attempt=attempt)
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
                    continue
                self.oms.reject(order.id, f"Broker error: {e}")
                raise
            except Exception as e:
                logger.error("execution_error", order=order.id, error=str(e), attempt=attempt)
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay)
                    continue
                self.oms.reject(order.id, f"Execution error: {e}")
                raise ExecutionError(f"Order {order.id} failed: {e}") from e

            if result == OrderStatus.REJECTED:
                self.oms.reject(order.id, "Rejected by broker")
                raise OrderRejectedError(f"Order {order.id} rejected by broker")

            self.oms.accept(order.id)
            return self._process_fill(order)

        self.oms.reject(order.id, "Max retries exceeded")
        raise ExecutionError(f"Order {order.id} failed after {self.max_retries} attempts")

    def _process_fill(self, order: Order) -> Order:
        if order.order_type == OrderType.MARKET:
            fill_price = float(order.price) if order.price else 0.0
            self.oms.update_fill(order.id, order.quantity, fill_price)
        return self.oms.get_order(order.id)

    def record_partial_fill(self, order_id: str, filled_qty: int, fill_price: float) -> Order:
        return self.oms.update_fill(order_id, filled_qty, fill_price)

    def order_to_trade(self, order: Order, exit_reason: str = "") -> Trade:
        return Trade(
            id=str(uuid4()),
            strategy_id=order.strategy_id,
            symbol=order.symbol,
            side=order.side,
            entry_price=Decimal(str(order.average_fill_price or order.price or 0)),
            exit_price=None
            if order.side == Side.BUY
            else Decimal(str(order.average_fill_price or order.price or 0)),
            quantity=order.filled_quantity,
            entry_time=order.created_at,
            exit_time=datetime.now(timezone.utc) if order.side == Side.SELL else None,
            entry_reason="signal",
            exit_reason=exit_reason,
        )

    async def cancel_order(self, order_id: str) -> bool:
        order = self.oms.get_order(order_id)
        if not order:
            return False
        try:
            result = await self.broker.cancel_order(order_id)
            if result:
                self.oms.cancel(order_id, "Cancelled by user")
            return result
        except BrokerError as e:
            logger.error("cancel_failed", order=order_id, error=str(e))
            return False

    async def get_order_status(self, order_id: str) -> Order | None:
        return self.oms.get_order(order_id)

    @property
    def pending_count(self) -> int:
        return len(self._pending_orders)
