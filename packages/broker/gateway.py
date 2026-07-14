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


class ZerodhaBroker(BaseBroker):
    async def place_order(self, order: Order) -> OrderStatus:
        raise NotImplementedError("Zerodha integration pending")

    async def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError("Zerodha integration pending")

    async def get_positions(self) -> list[dict]:
        raise NotImplementedError("Zerodha integration pending")

    async def get_account(self) -> dict:
        raise NotImplementedError("Zerodha integration pending")

    async def get_historical_data(self, symbol: str, start: date, end: date) -> list[Bar]:
        raise NotImplementedError("Zerodha integration pending")


class AlpacaBroker(BaseBroker):
    async def place_order(self, order: Order) -> OrderStatus:
        raise NotImplementedError("Alpaca integration pending")

    async def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError("Alpaca integration pending")

    async def get_positions(self) -> list[dict]:
        raise NotImplementedError("Alpaca integration pending")

    async def get_account(self) -> dict:
        raise NotImplementedError("Alpaca integration pending")

    async def get_historical_data(self, symbol: str, start: date, end: date) -> list[Bar]:
        raise NotImplementedError("Alpaca integration pending")


def create_broker(config: BrokerConfig) -> BaseBroker:
    if config.mode == "zerodha":
        return ZerodhaBroker(config)
    elif config.mode == "alpaca":
        return AlpacaBroker(config)
    else:
        return SimulatedBroker(config)
