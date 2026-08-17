"""End-to-End Paper Trading Loop — connects all subsystems into a continuous pipeline."""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from packages.broker.gateway import BaseBroker, SimulatedBroker, BrokerConfig
from packages.core.logging import get_logger
from packages.core.exceptions import ExecutionError, RiskLimitBreach
from packages.domain.models import (
    OrderType,
    Side,
    Signal,
    SignalDirection,
    Bar,
    MarketRegime,
)
from packages.oms.manager import OrderManager
from packages.execution.engine import ExecutionEngine
from packages.portfolio.engine import PortfolioEngine
from packages.risk.engine import RiskEngine
from packages.session.manager import SessionManager
from packages.journal.entry import TradeJournal
from packages.health.monitor import HealthMonitor
from packages.dashboard.display import Dashboard
from packages.domain.models import MarketContext

logger = get_logger("trading_loop")

StrategyFn = Callable[[Bar, MarketContext], list[Signal]]


class PaperTradingLoop:
    def __init__(
        self,
        broker: BaseBroker | None = None,
        initial_capital: Decimal = Decimal("1000000"),
        session_manager: SessionManager | None = None,
        portfolio: PortfolioEngine | None = None,
    ):
        self.broker = broker or SimulatedBroker(BrokerConfig(mode="paper"))
        self.oms = OrderManager()
        self.execution = ExecutionEngine(self.broker, self.oms)
        self.portfolio = portfolio or PortfolioEngine(initial_capital=initial_capital)
        self.risk = RiskEngine()
        self.session = session_manager or SessionManager()
        self.journal = TradeJournal()
        self.health = HealthMonitor()
        self.dashboard = Dashboard(
            portfolio_engine=self.portfolio,
            risk_engine=self.risk,
            health_monitor=self.health,
            trade_journal=self.journal,
            session_manager=self.session,
            order_manager=self.oms,
        )
        self._running = False
        self._strategy_fn: StrategyFn | None = None
        self._current_bar: Bar | None = None

    def set_strategy(self, strategy_fn: StrategyFn | None) -> None:
        self._strategy_fn = strategy_fn

    async def process_signal(
        self,
        signal: Signal,
        bar: Bar,
    ) -> dict[str, Any]:
        if signal.direction == SignalDirection.NEUTRAL:
            return {"action": "none", "reason": "neutral signal"}

        if not self.session.is_open():
            return {"action": "skipped", "reason": "market closed"}

        if not self.health.all_healthy():
            return {"action": "skipped", "reason": "health check failed"}

        side = Side.BUY if signal.direction == SignalDirection.LONG else Side.SELL
        order = self.oms.create_order(
            strategy_id=signal.strategy_id,
            portfolio_id=self.portfolio.portfolio.id,
            symbol=bar.symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=self._compute_quantity(side, bar),
            price=bar.close,
        )

        risk_check = self.risk.check_order(order, self.portfolio)
        if not risk_check["approved"]:
            self.oms.reject(order.id, f"Risk check failed: {risk_check['checks']}")
            logger.warning("order_rejected_by_risk", order=order.id, checks=risk_check["checks"])
            return {"action": "rejected", "reason": risk_check["checks"]}

        self.oms.validate(order.id)

        try:
            filled_order = await self.execution.execute(order)
        except (ExecutionError, RiskLimitBreach) as e:
            logger.error("execution_failed", order=order.id, error=str(e))
            return {"action": "failed", "error": str(e)}

        if filled_order.status.name in ("FILLED", "PARTIALLY_FILLED"):
            fill_price = filled_order.average_fill_price or order.price
            trades = self.portfolio.apply_fill(filled_order, Decimal(str(fill_price)))
            for trade in trades:
                self.journal.record_trade(
                    trade=trade,
                    strategy_id=signal.strategy_id,
                    signal=str(signal.direction.value),
                    confidence=signal.confidence,
                    execution_details={
                        "order_id": order.id,
                        "fill_price": float(fill_price),
                        "filled_qty": order.quantity,
                    },
                )
            daily_pnl = sum(float(t.pnl) for t in trades)
            self.risk.update_daily_loss(daily_pnl)

            integrity = self.portfolio.verify_integrity()
            self.health.check_portfolio_integrity(integrity["verified"])

            return {
                "action": "filled" if filled_order.status.name == "FILLED" else "partial",
                "order_id": order.id,
                "symbol": bar.symbol,
                "side": side.value,
                "quantity": filled_order.quantity,
                "fill_price": float(fill_price),
                "trades": len(trades),
            }

        return {"action": "unknown", "status": filled_order.status.value}

    async def run(self, bars: list[Bar], symbol: str = "SIMULATED") -> dict[str, Any]:
        self._running = True
        stats = {"processed": 0, "filled": 0, "rejected": 0, "errors": 0}

        for bar in bars:
            if not self._running:
                break

            self._current_bar = bar
            self.portfolio.update_market_price(bar.symbol, bar.close)
            self.health.check_data_freshness(0.0)

            if self._strategy_fn:
                market_ctx = self._build_context(bar)
                signals = self._strategy_fn(bar, market_ctx)
                for signal in signals:
                    result = await self.process_signal(signal, bar)
                    stats["processed"] += 1
                    if result["action"] in ("filled", "partial"):
                        stats["filled"] += 1
                    elif result["action"] == "rejected":
                        stats["rejected"] += 1
                    elif result["action"] == "failed":
                        stats["errors"] += 1

        self._running = False
        return stats

    def stop(self) -> None:
        self._running = False
        logger.info("trading_loop_stopped")

    def emergency_stop(self, reason: str = "Manual stop") -> None:
        self._running = False
        self.risk.emergency_stop(reason)
        logger.critical("emergency_stop", reason=reason)

    def _compute_quantity(self, side: Side, bar: Bar) -> int:
        risk_amount = float(self.portfolio.portfolio.cash) * 0.02
        qty = max(1, int(risk_amount / float(max(bar.close, Decimal("0.01")))))
        return qty

    def _build_context(self, bar: Bar) -> "MarketContext":
        from packages.domain.models import MarketContext

        return MarketContext(
            timestamp=bar.timestamp,
            regime=MarketRegime.RANGING,
            volatility=float(bar.spread / max(bar.close, Decimal("0.01"))),
            volume_ratio=1.0,
        )

    def status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "portfolio": self.portfolio.to_dict(),
            "risk": self.risk.summary(),
            "session": self.session.status(),
            "health": self.health.report(),
            "journal": self.journal.summary(),
            "orders": self.oms.order_count(),
        }

    def render_dashboard(self) -> str:
        return self.dashboard.render()
