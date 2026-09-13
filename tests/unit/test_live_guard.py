"""Live-trading guard — all real-broker paths must fail closed.

Live trading is CLOSED for QuantLab Trader. The broker factory and the
execution engine must refuse to connect to, or place orders with, a real
broker unless QUANTLAB_LIVE_TRADING_ENABLED is explicitly set to a truthy
value. Without the env var, default-paper behavior must be unaffected.
"""

from decimal import Decimal

import pytest

from packages.broker.angel import AngelOneBroker
from packages.broker.gateway import BrokerConfig, create_broker, live_trading_enabled
from packages.broker.zerodha import ZerodhaBroker
from packages.core.exceptions import ConfigurationError
from packages.domain.models import Order, OrderType, Side


class TestLiveGuard:
    def test_live_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("QUANTLAB_LIVE_TRADING_ENABLED", raising=False)
        assert live_trading_enabled() is False

    def test_live_requires_explicit_true(self, monkeypatch):
        monkeypatch.setenv("QUANTLAB_LIVE_TRADING_ENABLED", "1")
        assert live_trading_enabled() is True
        monkeypatch.setenv("QUANTLAB_LIVE_TRADING_ENABLED", "0")
        assert live_trading_enabled() is False
        monkeypatch.setenv("QUANTLAB_LIVE_TRADING_ENABLED", "false")
        assert live_trading_enabled() is False

    def test_create_broker_paper_works(self):
        broker = create_broker(BrokerConfig(mode="paper"))
        assert broker.config.mode == "paper"

    def test_create_broker_simulated_works(self):
        broker = create_broker(BrokerConfig(mode="simulated"))
        assert broker.config.mode == "simulated"

    @pytest.mark.parametrize("mode", ["zerodha", "alpaca", "angel"])
    def test_create_broker_live_modes_fail_closed(self, mode, monkeypatch):
        monkeypatch.delenv("QUANTLAB_LIVE_TRADING_ENABLED", raising=False)
        with pytest.raises(ConfigurationError):
            create_broker(BrokerConfig(mode=mode))

    def test_live_mode_alias_rejected(self, monkeypatch):
        monkeypatch.delenv("QUANTLAB_LIVE_TRADING_ENABLED", raising=False)
        with pytest.raises(ConfigurationError):
            create_broker(BrokerConfig(mode="live"))

    def test_unknown_mode_rejected(self):
        with pytest.raises(ConfigurationError):
            create_broker(BrokerConfig(mode="nonsense"))

    def test_live_modes_require_env_to_build(self, monkeypatch):
        monkeypatch.setenv("QUANTLAB_LIVE_TRADING_ENABLED", "1")
        broker = create_broker(BrokerConfig(mode="zerodha", api_key="k", access_token="t"))
        assert broker.config.mode == "zerodha"

    def test_brokers_flag_live_capable(self):
        assert AngelOneBroker.live_capable is True
        assert ZerodhaBroker.live_capable is True


def _order() -> Order:
    return Order(
        id="o1",
        strategy_id="s1",
        portfolio_id="p1",
        symbol="RELIANCE.NS",
        side=Side.BUY,
        order_type=OrderType.MARKET,
        quantity=1,
        price=Decimal("2500"),
    )


class TestExecutionEngineGuard:
    async def test_execution_refuses_live_broker_when_closed(self, monkeypatch):
        monkeypatch.delenv("QUANTLAB_LIVE_TRADING_ENABLED", raising=False)
        from packages.execution.engine import ExecutionEngine
        from packages.oms.manager import OrderManager

        live = ZerodhaBroker(BrokerConfig(mode="zerodha", api_key="k", access_token="t"))
        engine = ExecutionEngine(live, OrderManager())
        with pytest.raises(ConfigurationError):
            await engine.execute(_order())

    async def test_execution_allows_paper_broker(self):
        from packages.broker.gateway import PaperBroker
        from packages.execution.engine import ExecutionEngine
        from packages.oms.manager import OrderManager

        paper = PaperBroker(BrokerConfig(mode="paper"))
        oms = OrderManager()
        engine = ExecutionEngine(paper, oms)
        order = oms.create_order(
            "s1", "p1", "RELIANCE.NS", Side.BUY, order_type=OrderType.MARKET,
            quantity=1, price=Decimal("2500"),
        )
        result = await engine.execute(order)
        assert result.status.value == "FILLED"
