"""Portfolio Engine — accurate position and PnL accounting."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from packages.core.exceptions import RiskError
from packages.core.logging import get_logger
from packages.domain.models import (
    Portfolio,
    Position,
    PositionSide,
    Trade,
    Side,
    Order,
)

logger = get_logger("portfolio_engine")


class PortfolioEngine:
    def __init__(self, initial_capital: Decimal = Decimal("1000000")):
        self.portfolio = Portfolio(
            id=str(uuid4()),
            initial_capital=initial_capital,
            current_value=initial_capital,
            cash=initial_capital,
            buying_power=initial_capital,
            equity=initial_capital,
            net_asset_value=initial_capital,
        )
        self._daily_start_equity = initial_capital
        self._peak_equity = float(initial_capital)
        self._closed_trades: list[Trade] = []

    def apply_fill(self, order: Order, fill_price: Decimal) -> list[Trade]:
        trades = []
        if order.side == Side.BUY:
            cost = fill_price * Decimal(str(order.quantity))
            if cost > self.portfolio.cash:
                max_qty = int(float(self.portfolio.cash) / float(fill_price))
                if max_qty <= 0:
                    raise RiskError(f"Insufficient cash for {order.symbol}")
                logger.warning(
                    "cash_shortfall_clamp",
                    order_id=order.id,
                    symbol=order.symbol,
                    requested_qty=order.quantity,
                    filled_qty=max_qty,
                    reason="Insufficient cash: quantity clamped to affordable max",
                )
                order.quantity = max_qty
                cost = fill_price * Decimal(str(order.quantity))

            existing = self._get_position(order.symbol)
            if existing:
                total_qty = existing.quantity + order.quantity
                total_cost = (existing.average_price * Decimal(str(existing.quantity))) + (
                    fill_price * Decimal(str(order.quantity))
                )
                existing.average_price = total_cost / Decimal(str(total_qty))
                existing.quantity = total_qty
                existing.current_price = fill_price
            else:
                self.portfolio.positions.append(
                    Position(
                        symbol=order.symbol,
                        side=PositionSide.LONG,
                        quantity=order.quantity,
                        average_price=fill_price,
                        current_price=fill_price,
                        strategy_id=order.strategy_id,
                    )
                )

            self.portfolio.cash -= cost

        elif order.side == Side.SELL:
            pos = self._get_position(order.symbol)
            if not pos:
                raise RiskError(f"No position to sell for {order.symbol}")

            qty = min(order.quantity, pos.quantity)
            if qty <= 0:
                raise RiskError(f"Invalid sell quantity {order.quantity} for {order.symbol}")

            proceeds = fill_price * Decimal(str(qty))
            pnl = (fill_price - pos.average_price) * Decimal(str(qty))
            pnl_pct = float((fill_price - pos.average_price) / pos.average_price * 100)

            self.portfolio.cash += proceeds
            self.portfolio.realized_pnl += pnl
            pos.quantity -= qty

            trade = Trade(
                id=str(uuid4()),
                strategy_id=order.strategy_id,
                symbol=order.symbol,
                side=order.side,
                entry_price=pos.average_price,
                exit_price=fill_price,
                quantity=qty,
                entry_time=order.created_at,
                exit_time=datetime.now(timezone.utc),
                pnl=pnl,
                pnl_pct=pnl_pct,
                entry_reason="signal",
                exit_reason="target",
            )
            self._closed_trades.append(trade)
            trades.append(trade)

            if pos.quantity <= 0:
                self.portfolio.positions = [
                    p for p in self.portfolio.positions if p.symbol != order.symbol
                ]

        self._update_portfolio()
        return trades

    def update_market_price(self, symbol: str, price: Decimal) -> None:
        for pos in self.portfolio.positions:
            if pos.symbol == symbol:
                pos.current_price = price
        self._update_portfolio()

    def _update_portfolio(self) -> None:
        total_position_value = sum(
            float(pos.current_price * Decimal(str(pos.quantity)))
            for pos in self.portfolio.positions
        )
        self.portfolio.current_value = self.portfolio.cash + Decimal(str(total_position_value))
        self.portfolio.equity = self.portfolio.current_value

        total_unrealized = Decimal("0")
        for pos in self.portfolio.positions:
            upnl = (pos.current_price - pos.average_price) * Decimal(str(pos.quantity))
            total_unrealized += upnl
            pos.pnl = upnl
            pos.pnl_pct = float((pos.current_price - pos.average_price) / pos.average_price * 100)

        self.portfolio.unrealized_pnl = total_unrealized
        self.portfolio.net_asset_value = self.portfolio.cash + sum(
            (pos.current_price * Decimal(str(pos.quantity))) for pos in self.portfolio.positions
        )

        nav_float = float(self.portfolio.net_asset_value)
        self._peak_equity = max(self._peak_equity, nav_float)
        self.portfolio.drawdown = (
            (self._peak_equity - nav_float) / self._peak_equity * 100
            if self._peak_equity > 0
            else 0
        )

        init_float = float(self.portfolio.initial_capital)
        self.portfolio.total_return = (
            (nav_float - init_float) / init_float * 100 if init_float > 0 else 0
        )
        self.portfolio.daily_return = (
            (nav_float - float(self._daily_start_equity)) / float(self._daily_start_equity) * 100
            if float(self._daily_start_equity) > 0
            else 0
        )

        total_exposure = sum(
            float(pos.current_price * Decimal(str(pos.quantity)))
            for pos in self.portfolio.positions
        )
        self.portfolio.exposure = total_exposure / nav_float * 100 if nav_float > 0 else 0
        self.portfolio.buying_power = self.portfolio.cash

    def get_position(self, symbol: str) -> Position | None:
        return self._get_position(symbol)

    def _get_position(self, symbol: str) -> Position | None:
        for pos in self.portfolio.positions:
            if pos.symbol == symbol:
                return pos
        return None

    def get_all_positions(self) -> list[Position]:
        return list(self.portfolio.positions)

    def get_closed_trades(self, limit: int = 100) -> list[Trade]:
        return list(reversed(self._closed_trades))[:limit]

    def verify_integrity(self) -> dict[str, Any]:
        nav = float(self.portfolio.net_asset_value)
        cash = float(self.portfolio.cash)
        pos_value = sum(
            float(p.current_price * Decimal(str(p.quantity))) for p in self.portfolio.positions
        )
        computed_nav = cash + pos_value
        diff = abs(nav - computed_nav)
        return {
            "verified": diff < 0.01,
            "nav": nav,
            "cash": cash,
            "position_value": pos_value,
            "computed_nav": computed_nav,
            "difference": diff,
            "positions": len(self.portfolio.positions),
            "closed_trades": len(self._closed_trades),
        }

    def reset_daily(self) -> None:
        self._daily_start_equity = self.portfolio.equity

    def to_dict(self) -> dict[str, Any]:
        p = self.portfolio
        return {
            "id": p.id,
            "initial_capital": float(p.initial_capital),
            "cash": float(p.cash),
            "equity": float(p.equity),
            "buying_power": float(p.buying_power),
            "nav": float(p.net_asset_value),
            "unrealized_pnl": float(p.unrealized_pnl),
            "realized_pnl": float(p.realized_pnl),
            "total_return_pct": round(p.total_return, 2),
            "daily_return_pct": round(p.daily_return, 2),
            "drawdown_pct": round(p.drawdown, 2),
            "exposure_pct": round(p.exposure, 2),
            "open_positions": len(p.positions),
            "closed_trades": len(self._closed_trades),
        }
