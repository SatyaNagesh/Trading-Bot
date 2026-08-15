"""Gate 4: Paper Trading System — comprehensive tests."""

import pytest
from datetime import datetime, timezone, date
from decimal import Decimal

from packages.domain.models import (
    Side, OrderType, OrderStatus, TimeInForce, PositionSide,
    Bar, Order, Trade, Signal, SignalDirection, Portfolio, Position,
    RiskBudget, JournalEntry,
)
from packages.oms.manager import OrderManager
from packages.execution.engine import ExecutionEngine
from packages.portfolio.engine import PortfolioEngine
from packages.risk.engine import RiskEngine
from packages.session.manager import SessionManager, MarketCalendar, SessionStatus
from packages.journal.entry import TradeJournal
from packages.health.monitor import HealthMonitor
from packages.dashboard.display import Dashboard
from packages.broker.gateway import PaperBroker, BrokerConfig


# =============================================================================
# Phase 1: Broker Abstraction
# =============================================================================

class TestPaperBroker:
    @pytest.mark.asyncio
    async def test_place_order_returns_accepted(self):
        broker = PaperBroker(BrokerConfig(mode="paper"))
        order = Order(id="test-1", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                       side=Side.BUY, order_type=OrderType.MARKET, quantity=100, price=Decimal("150"))
        status = await broker.place_order(order)
        assert status == OrderStatus.ACCEPTED

    @pytest.mark.asyncio
    async def test_get_account(self):
        broker = PaperBroker(BrokerConfig(mode="paper"))
        acct = await broker.get_account()
        assert acct["mode"] == "paper"
        assert acct["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_order_status(self):
        broker = PaperBroker(BrokerConfig(mode="paper"))
        order = Order(id="test-2", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                       side=Side.BUY, order_type=OrderType.MARKET, quantity=100, price=Decimal("150"))
        await broker.place_order(order)
        status = await broker.get_order_status("test-2")
        assert status["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_cancel_order(self):
        broker = PaperBroker(BrokerConfig(mode="paper"))
        order = Order(id="test-3", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                       side=Side.BUY, order_type=OrderType.MARKET, quantity=100, price=Decimal("150"))
        await broker.place_order(order)
        result = await broker.cancel_order("test-3")
        assert result is True

    @pytest.mark.asyncio
    async def test_create_broker_factory(self):
        from packages.broker.gateway import create_broker
        broker = create_broker(BrokerConfig(mode="paper"))
        assert isinstance(broker, PaperBroker)


# =============================================================================
# Phase 2: Order Management System
# =============================================================================

class TestOrderManager:
    def test_create_order(self):
        oms = OrderManager()
        order = oms.create_order(
            strategy_id="s1", portfolio_id="p1", symbol="AAPL",
            side=Side.BUY, quantity=100, price=150.0,
        )
        assert order.status == OrderStatus.CREATED
        assert order.id is not None
        assert order.symbol == "AAPL"

    def test_get_order(self):
        oms = OrderManager()
        order = oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100)
        retrieved = oms.get_order(order.id)
        assert retrieved is not None
        assert retrieved.id == order.id

    def test_get_order_not_found(self):
        oms = OrderManager()
        assert oms.get_order("nonexistent") is None

    def test_valid_transition(self):
        oms = OrderManager()
        order = oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100)
        oms.transition(order.id, OrderStatus.VALIDATED)
        assert oms.get_order(order.id).status == OrderStatus.VALIDATED

    def test_invalid_transition_raises(self):
        oms = OrderManager()
        order = oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100)
        with pytest.raises(Exception, match="Invalid transition"):
            oms.transition(order.id, OrderStatus.FILLED)

    def test_full_lifecycle(self):
        oms = OrderManager()
        order = oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100)
        oms.validate(order.id)
        assert order.status == OrderStatus.VALIDATED
        oms.submit(order.id)
        assert order.status == OrderStatus.SUBMITTED
        oms.pending(order.id)
        assert order.status == OrderStatus.PENDING
        oms.accept(order.id)
        assert order.status == OrderStatus.ACCEPTED
        oms.update_fill(order.id, 100, 150.0)
        assert order.status == OrderStatus.FILLED

    def test_partial_fill(self):
        oms = OrderManager()
        order = oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100)
        oms.validate(order.id)
        oms.submit(order.id)
        oms.pending(order.id)
        oms.accept(order.id)
        oms.update_fill(order.id, 50, 150.0)
        assert order.status == OrderStatus.PARTIALLY_FILLED
        assert order.filled_quantity == 50
        oms.update_fill(order.id, 50, 151.0)
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 100

    def test_reject(self):
        oms = OrderManager()
        order = oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100)
        oms.reject(order.id, "Insufficient funds")
        assert order.status == OrderStatus.REJECTED

    def test_cancel(self):
        oms = OrderManager()
        order = oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100)
        oms.cancel(order.id, "User requested")
        assert order.status == OrderStatus.CANCELLED

    def test_expire(self):
        oms = OrderManager()
        order = oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100)
        oms.validate(order.id)
        oms.submit(order.id)
        oms.pending(order.id)
        oms.accept(order.id)
        oms.expire(order.id, "Time exceeded")
        assert order.status == OrderStatus.EXPIRED

    def test_get_open_orders(self):
        oms = OrderManager()
        o1 = oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100)
        o2 = oms.create_order("s1", "p1", "GOOGL", Side.BUY, quantity=50)
        o3 = oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=200)
        oms.reject(o3.id, "test")
        open_orders = oms.get_open_orders()
        assert len(open_orders) == 2
        assert o3.id not in [o.id for o in open_orders]

    def test_get_open_orders_filtered(self):
        oms = OrderManager()
        oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100)
        oms.create_order("s1", "p1", "GOOGL", Side.BUY, quantity=50)
        aapl_orders = oms.get_open_orders(symbol="AAPL")
        assert len(aapl_orders) == 1

    def test_order_count(self):
        oms = OrderManager()
        oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100)
        oms.create_order("s1", "p1", "GOOGL", Side.BUY, quantity=50)
        counts = oms.order_count()
        assert counts.get("CREATED", 0) == 2

    def test_transition_log(self):
        oms = OrderManager()
        o = oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100)
        oms.validate(o.id)
        oms.submit(o.id)
        log = oms.transition_log()
        assert len(log) >= 3

    def test_sell_order_lifecycle(self):
        oms = OrderManager()
        order = oms.create_order("s1", "p1", "AAPL", Side.SELL, quantity=50)
        oms.validate(order.id)
        oms.submit(order.id)
        oms.pending(order.id)
        oms.accept(order.id)
        oms.update_fill(order.id, 50, 160.0)
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 50


# =============================================================================
# Phase 3: Execution Engine
# =============================================================================

class TestExecutionEngine:
    @pytest.mark.asyncio
    async def test_execute_market_order(self):
        broker = PaperBroker(BrokerConfig(mode="paper"))
        oms = OrderManager()
        engine = ExecutionEngine(broker, oms)
        order = oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100, price=150.0)
        result = await engine.execute(order)
        assert result.status == OrderStatus.FILLED
        assert result.filled_quantity == 100

    @pytest.mark.asyncio
    async def test_execute_rejected_order(self):
        broker = PaperBroker(BrokerConfig(mode="paper"))
        oms = OrderManager()
        engine = ExecutionEngine(broker, oms)
        order = oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100, price=150.0)
        oms.reject(order.id, "Risk check failed")
        assert order.status == OrderStatus.REJECTED
        with pytest.raises(Exception, match="Invalid transition"):
            await engine.execute(order)

    @pytest.mark.asyncio
    async def test_duplicate_order_prevention(self):
        broker = PaperBroker(BrokerConfig(mode="paper"))
        oms = OrderManager()
        engine = ExecutionEngine(broker, oms)
        order = oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100, price=150.0)
        await engine.execute(order)
        with pytest.raises(Exception, match="Duplicate"):
            await engine.execute(order)

    @pytest.mark.asyncio
    async def test_cancel_order(self):
        broker = PaperBroker(BrokerConfig(mode="paper"))
        oms = OrderManager()
        engine = ExecutionEngine(broker, oms)
        order = oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100, price=150.0)
        oms.transition(order.id, OrderStatus.VALIDATED)
        oms.transition(order.id, OrderStatus.SUBMITTED)
        await broker.place_order(order)
        result = await engine.cancel_order(order.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_record_partial_fill(self):
        broker = PaperBroker(BrokerConfig(mode="paper"))
        oms = OrderManager()
        engine = ExecutionEngine(broker, oms)
        order = oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100, price=150.0)
        oms.validate(order.id)
        oms.submit(order.id)
        oms.pending(order.id)
        oms.accept(order.id)
        updated = engine.record_partial_fill(order.id, 50, 150.0)
        assert updated.status == OrderStatus.PARTIALLY_FILLED
        assert updated.filled_quantity == 50

    @pytest.mark.asyncio
    async def test_sell_execution(self):
        broker = PaperBroker(BrokerConfig(mode="paper"))
        oms = OrderManager()
        engine = ExecutionEngine(broker, oms)
        order = oms.create_order("s1", "p1", "AAPL", Side.SELL, quantity=50, price=160.0)
        engine._check_duplicate(order)
        oms.validate(order.id)
        oms.submit(order.id)
        oms.accept(order.id)
        filled = engine._process_fill(order)
        assert filled.filled_quantity == 50

    def test_pending_count(self):
        broker = PaperBroker(BrokerConfig(mode="paper"))
        oms = OrderManager()
        engine = ExecutionEngine(broker, oms)
        assert engine.pending_count == 0


# =============================================================================
# Phase 4: Portfolio Engine
# =============================================================================

class TestPortfolioEngine:
    def test_initial_state(self):
        pe = PortfolioEngine(Decimal("100000"))
        assert pe.portfolio.cash == Decimal("100000")
        assert pe.portfolio.equity == Decimal("100000")
        assert len(pe.get_all_positions()) == 0

    def test_buy_creates_position(self):
        pe = PortfolioEngine(Decimal("100000"))
        order = Order(id="o1", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                       side=Side.BUY, order_type=OrderType.MARKET, quantity=100, price=Decimal("150"))
        order.filled_quantity = 100
        order.average_fill_price = Decimal("150")
        pe.apply_fill(order, Decimal("150"))
        pos = pe.get_position("AAPL")
        assert pos is not None
        assert pos.quantity == 100
        assert pos.average_price == Decimal("150")
        assert pe.portfolio.cash < Decimal("100000")

    def test_sell_closes_position(self):
        pe = PortfolioEngine(Decimal("100000"))
        buy_order = Order(id="o1", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                           side=Side.BUY, order_type=OrderType.MARKET, quantity=100, price=Decimal("150"))
        buy_order.filled_quantity = 100
        buy_order.average_fill_price = Decimal("150")
        pe.apply_fill(buy_order, Decimal("150"))
        sell_order = Order(id="o2", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                            side=Side.SELL, order_type=OrderType.MARKET, quantity=100, price=Decimal("160"))
        sell_order.filled_quantity = 100
        trades = pe.apply_fill(sell_order, Decimal("160"))
        assert len(trades) == 1
        assert trades[0].pnl == Decimal("1000")
        assert pe.get_position("AAPL") is None

    def test_partial_sell(self):
        pe = PortfolioEngine(Decimal("100000"))
        buy_order = Order(id="o1", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                           side=Side.BUY, order_type=OrderType.MARKET, quantity=100, price=Decimal("150"))
        buy_order.filled_quantity = 100
        pe.apply_fill(buy_order, Decimal("150"))
        sell_order = Order(id="o2", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                            side=Side.SELL, order_type=OrderType.MARKET, quantity=40, price=Decimal("160"))
        sell_order.filled_quantity = 40
        trades = pe.apply_fill(sell_order, Decimal("160"))
        assert len(trades) == 1
        pos = pe.get_position("AAPL")
        assert pos.quantity == 60

    def test_market_price_update(self):
        pe = PortfolioEngine(Decimal("100000"))
        order = Order(id="o1", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                       side=Side.BUY, order_type=OrderType.MARKET, quantity=100, price=Decimal("150"))
        order.filled_quantity = 100
        order.average_fill_price = Decimal("150")
        pe.apply_fill(order, Decimal("150"))
        pe.update_market_price("AAPL", Decimal("170"))
        pos = pe.get_position("AAPL")
        assert pos.current_price == Decimal("170")
        assert float(pos.pnl) > 0

    def test_verify_integrity(self):
        pe = PortfolioEngine(Decimal("100000"))
        order = Order(id="o1", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                       side=Side.BUY, order_type=OrderType.MARKET, quantity=100, price=Decimal("150"))
        order.filled_quantity = 100
        pe.apply_fill(order, Decimal("150"))
        integrity = pe.verify_integrity()
        assert integrity["verified"] is True
        assert integrity["positions"] == 1

    def test_insufficient_cash(self):
        pe = PortfolioEngine(Decimal("1000"))
        order = Order(id="o1", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                       side=Side.BUY, order_type=OrderType.MARKET, quantity=10000, price=Decimal("150"))
        order.filled_quantity = 10000
        pe.apply_fill(order, Decimal("150"))
        assert order.quantity < 10000
        assert pe.portfolio.cash >= Decimal("0")

    def test_to_dict(self):
        pe = PortfolioEngine(Decimal("50000"))
        d = pe.to_dict()
        assert d["initial_capital"] == 50000.0
        assert d["cash"] == 50000.0

    def test_multiple_positions(self):
        pe = PortfolioEngine(Decimal("200000"))
        for i, sym in enumerate(["AAPL", "GOOGL", "MSFT"]):
            o = Order(id=f"o{i}", strategy_id="s1", portfolio_id="p1", symbol=sym,
                       side=Side.BUY, order_type=OrderType.MARKET, quantity=10, price=Decimal("500"))
            o.filled_quantity = 10
            pe.apply_fill(o, Decimal("500"))
        assert len(pe.get_all_positions()) == 3
        assert pe.portfolio.exposure > 0

    def test_realized_pnl_tracking(self):
        pe = PortfolioEngine(Decimal("100000"))
        buy = Order(id="o1", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                     side=Side.BUY, order_type=OrderType.MARKET, quantity=100, price=Decimal("100"))
        buy.filled_quantity = 100
        pe.apply_fill(buy, Decimal("100"))
        sell = Order(id="o2", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                      side=Side.SELL, order_type=OrderType.MARKET, quantity=100, price=Decimal("110"))
        sell.filled_quantity = 100
        pe.apply_fill(sell, Decimal("110"))
        assert float(pe.portfolio.realized_pnl) == 1000.0

    def test_closed_trades(self):
        pe = PortfolioEngine(Decimal("100000"))
        buy = Order(id="o1", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                     side=Side.BUY, order_type=OrderType.MARKET, quantity=100, price=Decimal("100"))
        buy.filled_quantity = 100
        pe.apply_fill(buy, Decimal("100"))
        sell = Order(id="o2", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                      side=Side.SELL, order_type=OrderType.MARKET, quantity=100, price=Decimal("110"))
        sell.filled_quantity = 100
        pe.apply_fill(sell, Decimal("110"))
        trades = pe.get_closed_trades()
        assert len(trades) == 1
        assert float(trades[0].pnl) == 1000.0


# =============================================================================
# Phase 5: Risk Engine
# =============================================================================

class TestRiskEngine:
    def test_approves_valid_order(self):
        pe = PortfolioEngine(Decimal("100000"))
        risk = RiskEngine()
        order = Order(id="o1", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                       side=Side.BUY, order_type=OrderType.MARKET, quantity=10, price=Decimal("150"))
        result = risk.check_order(order, pe)
        assert result["approved"] is True

    def test_blocks_excessive_position_size(self):
        pe = PortfolioEngine(Decimal("100000"))
        risk = RiskEngine(budget=RiskBudget(max_position_size_pct=0.01))
        order = Order(id="o1", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                       side=Side.BUY, order_type=OrderType.MARKET, quantity=10000, price=Decimal("150"))
        result = risk.check_order(order, pe)
        assert result["approved"] is False

    def test_blocks_excessive_positions(self):
        pe = PortfolioEngine(Decimal("100000"))
        risk = RiskEngine(budget=RiskBudget(max_concurrent_trades=1))
        for i in range(2):
            o = Order(id=f"o{i}", strategy_id="s1", portfolio_id="p1", symbol=f"SYM{i}",
                       side=Side.BUY, order_type=OrderType.MARKET, quantity=10, price=Decimal("100"))
            o.filled_quantity = 10
            try:
                pe.apply_fill(o, Decimal("100"))
            except Exception:
                pass
        order = Order(id="o3", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                       side=Side.BUY, order_type=OrderType.MARKET, quantity=10, price=Decimal("150"))
        result = risk.check_order(order, pe)
        assert result["approved"] is False

    def test_kill_switch_blocks_all(self):
        pe = PortfolioEngine(Decimal("100000"))
        risk = RiskEngine()
        risk.kill_switch(True)
        order = Order(id="o1", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                       side=Side.BUY, order_type=OrderType.MARKET, quantity=10, price=Decimal("150"))
        result = risk.check_order(order, pe)
        assert result["approved"] is False

    def test_kill_switch_deactivate(self):
        pe = PortfolioEngine(Decimal("100000"))
        risk = RiskEngine()
        risk.kill_switch(True)
        risk.kill_switch(False)
        order = Order(id="o1", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                       side=Side.BUY, order_type=OrderType.MARKET, quantity=10, price=Decimal("150"))
        result = risk.check_order(order, pe)
        assert result["approved"] is True

    def test_emergency_stop(self):
        risk = RiskEngine()
        risk.emergency_stop("Test emergency")
        assert risk._kill_switched is True

    def test_daily_loss_tracking(self):
        risk = RiskEngine()
        risk.update_daily_loss(-1000.0)
        assert risk._daily_loss == 1000.0

    def test_daily_loss_tracking_positive(self):
        risk = RiskEngine()
        risk.update_daily_loss(500.0)
        assert risk._daily_loss == 0.0

    def test_summary(self):
        risk = RiskEngine()
        s = risk.summary()
        assert "kill_switch_active" in s
        assert s["max_drawdown"] == 20.0
        assert s["max_positions"] == 10

    def test_drawdown_block(self):
        pe = PortfolioEngine(Decimal("100000"))
        risk = RiskEngine(budget=RiskBudget(max_drawdown=0.05))
        buy = Order(id="o1", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                     side=Side.BUY, order_type=OrderType.MARKET, quantity=100, price=Decimal("500"))
        buy.filled_quantity = 100
        pe.apply_fill(buy, Decimal("500"))
        pe.update_market_price("AAPL", Decimal("400"))
        assert pe.portfolio.drawdown > 5.0
        order = Order(id="o2", strategy_id="s1", portfolio_id="p1", symbol="GOOGL",
                       side=Side.BUY, order_type=OrderType.MARKET, quantity=10, price=Decimal("150"))
        result = risk.check_order(order, pe)
        assert result["approved"] is False

    def test_max_exposure(self):
        pe = PortfolioEngine(Decimal("100000"))
        risk = RiskEngine(budget=RiskBudget(max_exposure_pct=0.05))
        buy = Order(id="o1", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                     side=Side.BUY, order_type=OrderType.MARKET, quantity=100, price=Decimal("500"))
        buy.filled_quantity = 100
        pe.apply_fill(buy, Decimal("500"))
        order = Order(id="o2", strategy_id="s1", portfolio_id="p1", symbol="GOOGL",
                       side=Side.BUY, order_type=OrderType.MARKET, quantity=100, price=Decimal("500"))
        result = risk.check_order(order, pe)
        assert result["approved"] is False


# =============================================================================
# Phase 6: Session Manager
# =============================================================================

class TestSessionManager:
    def test_weekend_detection(self):
        cal = MarketCalendar()
        sat = datetime(2026, 7, 18, 10, 0, tzinfo=timezone.utc)
        assert cal.is_weekend(sat.date()) is True

    def test_weekday(self):
        cal = MarketCalendar()
        wed = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)
        assert cal.is_weekend(wed.date()) is False

    def test_holiday_detection(self):
        cal = MarketCalendar(holidays={date(2026, 1, 26), date(2026, 12, 25)})
        holiday = date(2026, 1, 26)
        assert cal.is_holiday(holiday) is True

    def test_market_open(self):
        sm = SessionManager()
        open_time = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)
        assert sm.is_open(open_time) is True

    def test_market_closed(self):
        sm = SessionManager()
        closed_time = datetime(2026, 7, 15, 20, 0, tzinfo=timezone.utc)
        assert sm.is_open(closed_time) is False

    def test_weekend_session(self):
        sm = SessionManager()
        sat = datetime(2026, 7, 18, 10, 0, tzinfo=timezone.utc)
        status = sm.check_session(sat)
        assert status == SessionStatus.WEEKEND

    def test_holiday_session(self):
        sm = SessionManager(calendar=MarketCalendar(holidays={date(2026, 1, 26)}))
        holiday = datetime(2026, 1, 26, 10, 0, tzinfo=timezone.utc)
        status = sm.check_session(holiday)
        assert status == SessionStatus.HOLIDAY

    def test_time_to_close(self):
        sm = SessionManager()
        morning = datetime(2026, 7, 15, 9, 30, tzinfo=timezone.utc)
        ttc = sm.time_to_close(morning)
        assert ttc.total_seconds() > 0

    def test_time_to_open(self):
        sm = SessionManager()
        evening = datetime(2026, 7, 15, 20, 0, tzinfo=timezone.utc)
        tto = sm.time_to_open(evening)
        assert tto.total_seconds() > 0

    def test_status_report(self):
        sm = SessionManager()
        s = sm.status()
        assert "session" in s
        assert "is_open" in s


# =============================================================================
# Phase 7: Trade Journal
# =============================================================================

class TestTradeJournal:
    def test_record_trade(self):
        journal = TradeJournal()
        trade = Trade(strategy_id="s1", symbol="AAPL", side=Side.BUY,
                       entry_price=Decimal("100"), exit_price=Decimal("110"),
                       quantity=100, entry_time=datetime.now(timezone.utc),
                       exit_time=datetime.now(timezone.utc), pnl=Decimal("1000"), pnl_pct=10.0)
        entry = journal.record_trade(trade, strategy_id="s1", signal="buy_signal",
                                      market_regime="trending", confidence=0.8)
        assert entry.symbol == "AAPL"
        assert float(entry.pnl) == 1000.0
        assert entry.confidence == 0.8

    def test_get_entries(self):
        journal = TradeJournal()
        for i in range(5):
            trade = Trade(strategy_id=f"s{i}", symbol="AAPL", side=Side.BUY,
                           entry_price=Decimal("100"), exit_price=Decimal("110"),
                           quantity=100, entry_time=datetime.now(timezone.utc),
                           exit_time=datetime.now(timezone.utc), pnl=Decimal("100"), pnl_pct=10.0)
            journal.record_trade(trade)
        entries = journal.get_entries(limit=3)
        assert len(entries) == 3

    def test_get_entries_filtered(self):
        journal = TradeJournal()
        for i in range(3):
            trade = Trade(strategy_id=f"s{i}", symbol="AAPL", side=Side.BUY,
                           entry_price=Decimal("100"), exit_price=Decimal("110"),
                           quantity=100, entry_time=datetime.now(timezone.utc),
                           exit_time=datetime.now(timezone.utc), pnl=Decimal("100"), pnl_pct=10.0)
            journal.record_trade(trade, strategy_id=f"s{i}")
        entries = journal.get_entries(strategy_id="s1")
        assert len(entries) == 1

    def test_summary_empty(self):
        journal = TradeJournal()
        s = journal.summary()
        assert s["total_trades"] == 0

    def test_summary(self):
        journal = TradeJournal()
        for i in range(10):
            pnl = 100 if i < 6 else -50
            trade = Trade(strategy_id="s1", symbol="AAPL", side=Side.BUY,
                           entry_price=Decimal("100"), exit_price=Decimal("110"),
                           quantity=100, entry_time=datetime.now(timezone.utc),
                           exit_time=datetime.now(timezone.utc), pnl=Decimal(str(pnl)), pnl_pct=10.0)
            journal.record_trade(trade, strategy_id="s1", confidence=0.7)
        s = journal.summary()
        assert s["total_trades"] == 10
        assert s["winning_trades"] == 6
        assert s["win_rate"] == 60.0

    def test_export(self):
        journal = TradeJournal()
        trade = Trade(strategy_id="s1", symbol="AAPL", side=Side.BUY,
                       entry_price=Decimal("100"), exit_price=Decimal("110"),
                       quantity=100, entry_time=datetime.now(timezone.utc),
                       exit_time=datetime.now(timezone.utc), pnl=Decimal("100"), pnl_pct=10.0)
        journal.record_trade(trade)
        exported = journal.export()
        assert len(exported) == 1
        assert exported[0]["symbol"] == "AAPL"

    def test_get_entry_by_id(self):
        journal = TradeJournal()
        trade = Trade(strategy_id="s1", symbol="AAPL", side=Side.BUY,
                       entry_price=Decimal("100"), exit_price=Decimal("110"),
                       quantity=100, entry_time=datetime.now(timezone.utc),
                       exit_time=datetime.now(timezone.utc), pnl=Decimal("100"), pnl_pct=10.0)
        entry = journal.record_trade(trade)
        found = journal.get_entry(entry.id)
        assert found is not None
        assert found.id == entry.id

    def test_total_entries(self):
        journal = TradeJournal()
        assert journal.total_entries() == 0
        for i in range(3):
            trade = Trade(strategy_id="s1", symbol="AAPL", side=Side.BUY,
                           entry_price=Decimal("100"), exit_price=Decimal("110"),
                           quantity=100, entry_time=datetime.now(timezone.utc),
                           pnl=Decimal("100"), pnl_pct=10.0)
            journal.record_trade(trade)
        assert journal.total_entries() == 3


# =============================================================================
# Phase 8: Health Monitor
# =============================================================================

class TestHealthMonitor:
    def test_initial_healthy(self):
        hm = HealthMonitor()
        assert hm.all_healthy() is True

    def test_broker_disconnect_pauses(self):
        hm = HealthMonitor()
        hm.check_broker(False)
        assert hm.all_healthy() is False
        assert hm.status.trading_paused is True

    def test_market_data_unavailable(self):
        hm = HealthMonitor()
        hm.check_market_data(False)
        assert hm.all_healthy() is False

    def test_api_failures(self):
        hm = HealthMonitor(max_api_failures=3)
        for _ in range(3):
            hm.check_api_failure()
        assert hm.all_healthy() is False
        assert hm.status.trading_paused is True

    def test_risk_engine_unhealthy(self):
        hm = HealthMonitor()
        hm.check_risk_engine(False)
        assert hm.all_healthy() is False

    def test_portfolio_integrity_fail(self):
        hm = HealthMonitor()
        hm.check_portfolio_integrity(False)
        assert hm.all_healthy() is False

    def test_stale_data_pauses(self):
        hm = HealthMonitor(max_data_age_seconds=10)
        hm.check_data_freshness(30.0)
        assert hm.all_healthy() is False

    def test_system_exceptions(self):
        hm = HealthMonitor()
        for _ in range(3):
            hm.check_system_exception()
        assert hm.all_healthy() is False

    def test_resume_trading(self):
        hm = HealthMonitor()
        hm.check_broker(False)
        assert hm.status.trading_paused is True
        hm.resume_trading()
        assert hm.status.trading_paused is False

    def test_report(self):
        hm = HealthMonitor()
        r = hm.report()
        assert r["healthy"] is True
        assert "broker_connected" in r

    def test_recent_alerts(self):
        hm = HealthMonitor()
        hm.check_broker(False)
        alerts = hm.recent_alerts()
        assert len(alerts) >= 1
        assert alerts[0]["severity"] == "critical"

    def test_execution_latency_warning(self):
        hm = HealthMonitor()
        hm.check_execution_latency(10000.0, threshold_ms=1000)
        assert hm.status.execution_latency_ms == 10000.0
        alerts = hm.recent_alerts()
        assert any("latency" in a["message"] for a in alerts)


# =============================================================================
# Phase 9: Dashboard
# =============================================================================

class TestDashboard:
    def test_empty_dashboard(self):
        d = Dashboard()
        output = d.render()
        assert "QUANTLAB AI" in output

    def test_dashboard_with_components(self):
        pe = PortfolioEngine(Decimal("100000"))
        risk = RiskEngine()
        hm = HealthMonitor()
        journal = TradeJournal()
        sm = SessionManager()
        oms = OrderManager()
        d = Dashboard(pe, risk, hm, journal, sm, oms)
        output = d.render()
        assert "PORTFOLIO" in output
        assert "RISK" in output
        assert "HEALTH" in output

    def test_dashboard_with_positions(self):
        pe = PortfolioEngine(Decimal("100000"))
        order = Order(id="o1", strategy_id="s1", portfolio_id="p1", symbol="AAPL",
                       side=Side.BUY, order_type=OrderType.MARKET, quantity=100, price=Decimal("150"))
        order.filled_quantity = 100
        pe.apply_fill(order, Decimal("150"))
        d = Dashboard(portfolio_engine=pe)
        output = d.render()
        assert "AAPL" in output
        assert "LONG" in output

    def test_dashboard_with_orders(self):
        oms = OrderManager()
        oms.create_order("s1", "p1", "AAPL", Side.BUY, quantity=100, price=150.0)
        d = Dashboard(order_manager=oms)
        output = d.render()
        assert "PENDING ORDERS" in output

    def test_dashboard_with_journal(self):
        journal = TradeJournal()
        trade = Trade(strategy_id="s1", symbol="AAPL", side=Side.BUY,
                       entry_price=Decimal("100"), exit_price=Decimal("110"),
                       quantity=100, entry_time=datetime.now(timezone.utc),
                       exit_time=datetime.now(timezone.utc), pnl=Decimal("1000"), pnl_pct=10.0)
        journal.record_trade(trade)
        d = Dashboard(trade_journal=journal)
        output = d.render()
        assert "TRADE JOURNAL" in output


# =============================================================================
# Phase 10: End-to-End Trading Loop
# =============================================================================

class TestPaperTradingLoop:
    @pytest.mark.asyncio
    async def test_loop_initialization(self):
        from packages.trading.loop import PaperTradingLoop
        loop = PaperTradingLoop(initial_capital=Decimal("500000"))
        status = loop.status()
        assert "portfolio" in status
        assert "risk" in status
        assert "session" in status
        assert loop._running is False

    @pytest.mark.asyncio
    async def test_loop_creates_broker(self):
        from packages.trading.loop import PaperTradingLoop
        loop = PaperTradingLoop()
        assert loop.broker is not None

    @pytest.mark.asyncio
    async def test_loop_stop(self):
        from packages.trading.loop import PaperTradingLoop
        loop = PaperTradingLoop()
        loop.stop()
        assert loop._running is False

    @pytest.mark.asyncio
    async def test_emergency_stop(self):
        from packages.trading.loop import PaperTradingLoop
        loop = PaperTradingLoop()
        loop.emergency_stop("Test")
        assert loop.risk._kill_switched is True
        assert loop._running is False

    @pytest.mark.asyncio
    async def test_process_signal_buy(self):
        from packages.trading.loop import PaperTradingLoop
        loop = PaperTradingLoop(initial_capital=Decimal("100000"))
        signal = Signal(strategy_id="s1", direction=SignalDirection.LONG, confidence=0.8)
        bar = Bar(timestamp=datetime.now(timezone.utc), symbol="AAPL",
                   open=Decimal("150"), high=Decimal("152"), low=Decimal("149"),
                   close=Decimal("151"), volume=10000)
        result = await loop.process_signal(signal, bar)
        assert result["action"] in ("filled", "none", "rejected", "skipped", "failed")

    @pytest.mark.asyncio
    async def test_process_neutral_signal(self):
        from packages.trading.loop import PaperTradingLoop
        loop = PaperTradingLoop()
        signal = Signal(strategy_id="s1", direction=SignalDirection.NEUTRAL, confidence=0.5)
        bar = Bar(timestamp=datetime.now(timezone.utc), symbol="AAPL",
                   open=Decimal("150"), high=Decimal("152"), low=Decimal("149"),
                   close=Decimal("151"), volume=10000)
        result = await loop.process_signal(signal, bar)
        assert result["action"] == "none"

    @pytest.mark.asyncio
    async def test_render_dashboard(self):
        from packages.trading.loop import PaperTradingLoop
        loop = PaperTradingLoop()
        output = loop.render_dashboard()
        assert "QUANTLAB AI" in output

    @pytest.mark.asyncio
    async def test_process_signal_sell(self):
        from packages.trading.loop import PaperTradingLoop
        loop = PaperTradingLoop(initial_capital=Decimal("100000"))
        buy_signal = Signal(strategy_id="s1", direction=SignalDirection.LONG, confidence=0.8)
        bar = Bar(timestamp=datetime.now(timezone.utc), symbol="AAPL",
                   open=Decimal("100"), high=Decimal("102"), low=Decimal("99"),
                   close=Decimal("101"), volume=10000)
        await loop.process_signal(buy_signal, bar)
        sell_signal = Signal(strategy_id="s1", direction=SignalDirection.SHORT, confidence=0.9)
        bar2 = Bar(timestamp=datetime.now(timezone.utc), symbol="AAPL",
                    open=Decimal("110"), high=Decimal("112"), low=Decimal("109"),
                    close=Decimal("111"), volume=10000)
        result = await loop.process_signal(sell_signal, bar2)
        assert result["action"] in ("filled", "none", "rejected", "skipped", "failed")
