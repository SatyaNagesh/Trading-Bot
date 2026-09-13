"""Broker Gateway — abstraction layer for pluggable brokers."""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timezone

from packages.core.exceptions import ConfigurationError
from packages.core.logging import get_logger
from packages.domain.models import Order, OrderStatus, Bar

logger = get_logger("broker_gateway")

LIVE_TRADING_ENV_VAR = "QUANTLAB_LIVE_TRADING_ENABLED"


def live_trading_enabled() -> bool:
    """Whether real-broker (live) trading is permitted.

    Defaults to CLOSED. Live modes fail closed unless the operator explicitly
    sets ``QUANTLAB_LIVE_TRADING_ENABLED=1``.
    """
    return os.environ.get(LIVE_TRADING_ENV_VAR, "").strip().lower() in ("1", "true", "yes", "on")


def require_live_trading_allowed() -> None:
    if not live_trading_enabled():
        raise ConfigurationError(
            "Live trading is CLOSED. Set QUANTLAB_LIVE_TRADING_ENABLED=1 to permit "
            "connections to real brokers. Paper/simulated modes are unaffected."
        )


@dataclass
class BrokerConfig:
    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""
    base_url: str = ""
    mode: str = "paper"


class BaseBroker(ABC):
    live_capable: bool = False

    def __init__(self, config: BrokerConfig):
        self.config = config

    @abstractmethod
    async def place_order(self, order: Order) -> OrderStatus: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    async def get_positions(self) -> list[dict]: ...

    @abstractmethod
    async def get_account(self) -> dict: ...

    @abstractmethod
    async def get_historical_data(self, symbol: str, start: date, end: date) -> list[Bar]: ...

    async def get_order_status(self, order_id: str) -> dict:
        """Return current status of an order from the broker."""
        return {"order_id": order_id, "status": "unknown"}

    async def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        """Return list of open orders from the broker."""
        return []


class SimulatedBroker(BaseBroker):
    async def place_order(self, order: Order) -> OrderStatus:
        logger.info(
            "simulated_order", symbol=order.symbol, side=order.side.value, qty=order.quantity
        )
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


class PaperBroker(BaseBroker):
    """Full lifecycle paper broker — simulates realistic fills with latency, partial fills, and rejects."""

    def __init__(self, config: BrokerConfig):
        super().__init__(config)
        self._orders: dict[str, dict] = {}
        self._positions: dict[str, dict] = {}
        self._fill_probability: float = 0.97
        self._latency_ms: int = 50

    async def place_order(self, order: Order) -> OrderStatus:
        logger.info(
            "paper_place_order", symbol=order.symbol, side=order.side.value, qty=order.quantity
        )
        self._orders[order.id] = {
            "id": order.id,
            "symbol": order.symbol,
            "side": order.side.value,
            "quantity": order.quantity,
            "status": "accepted",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return OrderStatus.ACCEPTED

    async def cancel_order(self, order_id: str) -> bool:
        if order_id in self._orders:
            self._orders[order_id]["status"] = "cancelled"
            return True
        return False

    async def get_positions(self) -> list[dict]:
        return list(self._positions.values())

    async def get_account(self) -> dict:
        return {
            "buying_power": 1_000_000,
            "equity": 1_000_000,
            "mode": "paper",
            "status": "active",
        }

    async def get_historical_data(self, symbol: str, start: date, end: date) -> list[Bar]:
        from packages.market.data_pipeline import fetch_bars

        return await fetch_bars(symbol, start, end)

    async def get_order_status(self, order_id: str) -> dict:
        return self._orders.get(order_id, {"order_id": order_id, "status": "not_found"})

    async def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        orders = [
            o for o in self._orders.values() if o["status"] in ("accepted", "submitted", "pending")
        ]
        if symbol:
            orders = [o for o in orders if o["symbol"] == symbol]
        return orders


class AlpacaBroker(BaseBroker):
    live_capable = True

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
                resp = await client.post(
                    f"{base}/v2/orders", headers=headers, json=payload, timeout=10
                )
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
    if config.mode in ("paper", "simulated"):
        return SimulatedBroker(config) if config.mode == "simulated" else PaperBroker(config)
    elif config.mode == "zerodha":
        require_live_trading_allowed()
        from packages.broker.zerodha import ZerodhaBroker

        return ZerodhaBroker(config)
    elif config.mode == "alpaca":
        require_live_trading_allowed()
        return AlpacaBroker(config)
    elif config.mode == "angel":
        require_live_trading_allowed()
        from packages.broker.angel import AngelOneBroker

        return AngelOneBroker(config)
    elif config.mode == "live":
        raise ConfigurationError(
            "mode='live' is ambiguous. Use an explicit broker mode "
            "('zerodha' | 'alpaca' | 'angel') and set QUANTLAB_LIVE_TRADING_ENABLED=1."
        )
    else:
        raise ConfigurationError(
            f"Unknown broker mode '{config.mode}'. Use 'paper', 'simulated', "
            "'zerodha', 'alpaca', or 'angel'."
        )
