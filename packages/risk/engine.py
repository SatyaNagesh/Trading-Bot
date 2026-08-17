"""Risk Engine — validates every order against configurable rules before execution."""

from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Any

from packages.core.logging import get_logger
from packages.domain.models import Order, Position, RiskBudget, Side
from packages.portfolio.engine import PortfolioEngine

logger = get_logger("risk_engine")


class RiskEngine:
    def __init__(self, budget: RiskBudget | None = None):
        self.budget = budget or RiskBudget()
        self._daily_loss: float = 0.0
        self._daily_trades: int = 0
        self._kill_switched: bool = False
        self._current_date: date = date.today()
        self._rejected_orders: list[dict] = []

    def check_order(self, order: Order, portfolio: PortfolioEngine) -> dict[str, Any]:
        if self._kill_switched:
            return self._reject(order, "kill_switch", "Kill switch is active — all orders rejected")

        checks: list[dict] = []
        nav = float(portfolio.portfolio.net_asset_value)
        estimated_notional = float(order.price or 0) * order.quantity if order.price else 0
        open_positions = portfolio.get_all_positions()

        pos_check = self._check_max_positions(
            order, open_positions, self.budget.max_concurrent_trades
        )
        checks.append(pos_check)

        size_check = self._check_position_size(
            estimated_notional, nav, self.budget.max_position_size_pct
        )
        checks.append(size_check)

        exposure_check = self._check_exposure(
            estimated_notional, portfolio, self.budget.max_exposure_pct
        )
        checks.append(exposure_check)

        drawdown_check = self._check_drawdown(
            portfolio.portfolio.drawdown, self.budget.max_drawdown
        )
        checks.append(drawdown_check)

        daily_loss_check = self._check_daily_loss(
            self._daily_loss, self.budget.max_daily_loss, nav
        )
        checks.append(daily_loss_check)

        leverage_check = self._check_leverage(
            estimated_notional, portfolio, self.budget.max_leverage
        )
        checks.append(leverage_check)

        strategy_check = self._check_strategy_allocation(order, portfolio)
        checks.append(strategy_check)

        all_passed = all(c["passed"] for c in checks)
        result = {
            "order_id": order.id,
            "symbol": order.symbol,
            "side": order.side.value,
            "quantity": order.quantity,
            "checks": checks,
            "approved": all_passed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if all_passed:
            self._daily_trades += 1
        else:
            self._rejected_orders.append(result)

        return result

    def _check_max_positions(
        self, order: Order, positions: list[Position], limit: int
    ) -> dict[str, Any]:
        count = sum(1 for p in positions if p.quantity > 0)
        if order.side != Side.SELL and count >= limit:
            return {
                "check": "max_concurrent_trades",
                "passed": False,
                "current": count,
                "limit": limit,
            }
        return {"check": "max_concurrent_trades", "passed": True, "current": count, "limit": limit}

    def _check_position_size(self, notional: float, nav: float, limit: float) -> dict[str, Any]:
        pct = notional / nav if nav > 0 else 1
        if pct > limit:
            return {
                "check": "max_position_size",
                "passed": False,
                "current": round(pct * 100, 2),
                "limit": limit * 100,
            }
        return {
            "check": "max_position_size",
            "passed": True,
            "current": round(pct * 100, 2),
            "limit": limit * 100,
        }

    def _check_exposure(
        self, notional: float, portfolio: PortfolioEngine, limit: float
    ) -> dict[str, Any]:
        total_exposure = sum(
            float(p.current_price * Decimal(str(p.quantity))) for p in portfolio.get_all_positions()
        )
        total_exposure += notional
        nav = float(portfolio.portfolio.net_asset_value)
        exposure_pct = total_exposure / nav if nav > 0 else 1
        if exposure_pct > limit:
            return {
                "check": "max_exposure",
                "passed": False,
                "current": round(exposure_pct * 100, 2),
                "limit": limit * 100,
            }
        return {
            "check": "max_exposure",
            "passed": True,
            "current": round(exposure_pct * 100, 2),
            "limit": limit * 100,
        }

    def _check_drawdown(self, current_dd: float, limit: float) -> dict[str, Any]:
        if current_dd > limit * 100:
            return {
                "check": "max_drawdown",
                "passed": False,
                "current": round(current_dd, 2),
                "limit": limit * 100,
            }
        return {
            "check": "max_drawdown",
            "passed": True,
            "current": round(current_dd, 2),
            "limit": limit * 100,
        }

    def _check_daily_loss(
        self, daily_loss: float, limit: float, nav: float = 0.0
    ) -> dict[str, Any]:
        # daily_loss is accumulated in rupees; the budget limit is a fraction of
        # equity (e.g. 0.02 = 2%). Normalize the rupee loss against NAV so both
        # sides are comparable percentages before checking.
        loss_frac = (daily_loss / nav) if nav > 0 else 0.0
        if loss_frac > limit:
            return {
                "check": "max_daily_loss",
                "passed": False,
                "current": round(loss_frac * 100, 2),
                "limit": limit * 100,
            }
        return {
            "check": "max_daily_loss",
            "passed": True,
            "current": round(loss_frac * 100, 2),
            "limit": limit * 100,
        }

    def _check_leverage(
        self, notional: float, portfolio: PortfolioEngine, limit: float
    ) -> dict[str, Any]:
        total_position_value = sum(
            float(p.current_price * Decimal(str(p.quantity))) for p in portfolio.get_all_positions()
        )
        nav = float(portfolio.portfolio.net_asset_value)
        leverage = (total_position_value + notional) / nav if nav > 0 else 0
        if leverage > limit:
            return {
                "check": "max_leverage",
                "passed": False,
                "current": round(leverage, 2),
                "limit": limit,
            }
        return {
            "check": "max_leverage",
            "passed": True,
            "current": round(leverage, 2),
            "limit": limit,
        }

    def _check_strategy_allocation(
        self, order: Order, portfolio: PortfolioEngine
    ) -> dict[str, Any]:
        strategy_nav = sum(
            float(p.current_price * Decimal(str(p.quantity)))
            for p in portfolio.get_all_positions()
            if p.strategy_id == order.strategy_id
        )
        nav = float(portfolio.portfolio.net_asset_value)
        strategy_pct = strategy_nav / nav if nav > 0 else 0
        limit = self.budget.per_strategy_allocation_pct
        if strategy_pct > limit:
            return {
                "check": "per_strategy_allocation",
                "passed": False,
                "current": round(strategy_pct * 100, 2),
                "limit": limit * 100,
            }
        return {
            "check": "per_strategy_allocation",
            "passed": True,
            "current": round(strategy_pct * 100, 2),
            "limit": limit * 100,
        }

    def update_daily_loss(self, pnl: float) -> None:
        today = date.today()
        if today != self._current_date:
            self._daily_loss = 0.0
            self._daily_trades = 0
            self._current_date = today
        if pnl < 0:
            self._daily_loss += abs(pnl)

    def emergency_stop(self, reason: str = "Manual emergency stop") -> None:
        self._kill_switched = True
        logger.critical("emergency_stop_activated", reason=reason)

    def kill_switch(self, active: bool = True) -> None:
        self._kill_switched = active
        status = "activated" if active else "deactivated"
        logger.warning("kill_switch", status=status)

    def _reject(self, order: Order, rule: str, reason: str) -> dict[str, Any]:
        result = {
            "order_id": order.id,
            "symbol": order.symbol,
            "side": order.side.value,
            "quantity": order.quantity,
            "checks": [{"check": rule, "passed": False, "reason": reason}],
            "approved": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._rejected_orders.append(result)
        return result

    def summary(self) -> dict[str, Any]:
        return {
            "kill_switch_active": self._kill_switched,
            "daily_loss": round(self._daily_loss, 2),
            "daily_trades": self._daily_trades,
            "total_rejected": len(self._rejected_orders),
            "max_drawdown": self.budget.max_drawdown * 100,
            "max_daily_loss": self.budget.max_daily_loss * 100,
            "max_positions": self.budget.max_positions,
            "max_exposure_pct": self.budget.max_exposure_pct * 100,
            "max_leverage": self.budget.max_leverage,
            "max_position_size_pct": self.budget.max_position_size_pct * 100,
        }
