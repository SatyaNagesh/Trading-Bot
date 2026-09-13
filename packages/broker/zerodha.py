"""Zerodha Kite Connect broker implementation."""

from datetime import date

from packages.broker.gateway import BaseBroker, BrokerConfig
from packages.core.exceptions import BrokerError
from packages.core.logging import get_logger
from packages.domain.models import Order, OrderStatus, Bar

logger = get_logger("zerodha_broker")


class ZerodhaBroker(BaseBroker):
    live_capable = True

    def __init__(self, config: BrokerConfig):
        super().__init__(config)
        self.api_key = config.api_key
        self.access_token = config.access_token
        self.base_url = config.base_url or "https://api.kite.trade"
        logger.info("zerodha_broker_initialized")

    async def place_order(self, order: Order) -> OrderStatus:
        logger.info("zerodha_place_order", symbol=order.symbol, side=order.side.value)
        try:
            import httpx

            headers = {
                "X-Kite-Version": "3",
                "Authorization": f"token {self.api_key}:{self.access_token}",
            }
            payload = {
                "tradingsymbol": order.symbol,
                "exchange": "NSE",
                "transaction_type": order.side.value,
                "quantity": order.quantity,
                "order_type": "MARKET",
                "product": "CNC",
                "validity": "DAY",
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/orders",
                    headers=headers,
                    json=payload,
                    timeout=10,
                )
                if resp.status_code == 200:
                    return OrderStatus.SUBMITTED
                logger.error("zerodha_order_failed", status=resp.status_code, body=resp.text)
                return OrderStatus.REJECTED
        except ImportError as e:
            raise BrokerError(
                "httpx is not available; refusing to place a real order with Zerodha"
            ) from e
        except Exception as e:
            logger.error("zerodha_order_error", error=str(e))
            return OrderStatus.REJECTED

    async def cancel_order(self, order_id: str) -> bool:
        logger.info("zerodha_cancel_order", id=order_id)
        return True

    async def get_positions(self) -> list[dict]:
        return []

    async def get_account(self) -> dict:
        return {"broker": "zerodha", "mode": "live" if self.access_token else "paper"}

    async def get_historical_data(self, symbol: str, start: date, end: date) -> list[Bar]:
        raise NotImplementedError("Use the market data pipeline")
