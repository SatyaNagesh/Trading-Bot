"""Broker Gateway — abstraction layer for pluggable brokers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from packages.core.exceptions import BrokerError
from packages.core.logging import get_logger
from packages.domain.models import Order, OrderStatus, Bar

logger = get_logger("broker_gateway")


@dataclass
class BrokerConfig:
    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""
    base_url: str = ""
    mode: str = "paper"


class BaseBroker(ABC):
    def __init__(self, config: BrokerConfig):
        self.config = config

    @abstractmethod
    async def place_order(self, order: Order) -> OrderStatus:
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        ...

    @abstractmethod
    async def get_positions(self) -> list[dict]:
        ...

    @abstractmethod
    async def get_account(self) -> dict:
        ...

    @abstractmethod
    async def get_historical_data(self, symbol: str, start: date, end: date) -> list[Bar]:
        ...


class SimulatedBroker(BaseBroker):
    async def place_order(self, order: Order) -> OrderStatus:
        logger.info("simulated_order", symbol=order.symbol, side=order.side.value, qty=order.quantity)
        return OrderStatus.FILLED

    async def cancel_order(self, order_id: str) -> bool:
        return True

    async def get_positions(self) -> list[dict]:
        return []

    async def get_account(self) -> dict:
        return {"buying_power": 1_000_000, "equity": 1_000_000, "mode": "simulated"}

    async def get_historical_data(self, symbol: str, start: date, end: date) -> list[Bar]:
        from packages.market.data_pipeline import fetch_bars
        return await fetch_bars(symbol, start, end)


class AlpacaBroker(BaseBroker):
    async def place_order(self, order: Order) -> OrderStatus:
        logger.info("alpaca_place_order", symbol=order.symbol, side=order.side.value)
        try:
            import httpx
            headers = {
                "APCA-API-KEY-ID": self.config.api_key,
                "APCA-API-SECRET-KEY": self.config.api_secret,
            }
            payload = {
                "symbol": order.symbol.replace(".NS", ""),
                "qty": order.quantity,
                "side": order.side.value.lower(),
                "type": "market",
                "time_in_force": "day",
            }
            base = self.config.base_url or "https://paper-api.alpaca.markets"
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{base}/v2/orders", headers=headers, json=payload, timeout=10)
                if resp.status_code in (200, 201):
                    return OrderStatus.SUBMITTED
                return OrderStatus.REJECTED
        except Exception as e:
            logger.error("alpaca_order_error", error=str(e))
            return OrderStatus.REJECTED

    async def cancel_order(self, order_id: str) -> bool:
        return True

    async def get_positions(self) -> list[dict]:
        return []

    async def get_account(self) -> dict:
        return {"broker": "alpaca", "mode": "paper"}

    async def get_historical_data(self, symbol: str, start: date, end: date) -> list[Bar]:
        raise NotImplementedError("Use the market data pipeline")


def create_broker(config: BrokerConfig) -> BaseBroker:
    if config.mode == "zerodha":
        from packages.broker.zerodha import ZerodhaBroker
        return ZerodhaBroker(config)
    elif config.mode == "alpaca":
        return AlpacaBroker(config)
    elif config.mode == "angel":
        from packages.broker.angel import AngelOneBroker
        return AngelOneBroker(config)
    else:
        return SimulatedBroker(config)
