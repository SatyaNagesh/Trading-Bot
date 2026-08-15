"""Event-driven backtest engine for QuantLab AI."""

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

import numpy as np

from packages.domain.models import (
    Bar,
    Side,
    OrderType,
    OrderStatus,
    PositionSide,
    Trade,
    Position,
    Order,
    Signal,
    SignalDirection,
    BacktestConfig,
    BacktestResult,
    MarketContext,
    MarketRegime,
)
from packages.core.exceptions import BacktestError
from packages.core.logging import get_logger

logger = get_logger("backtest")


@dataclass
class BacktestEngine:
    config: BacktestConfig
    strategy: Callable | None = None

    def __post_init__(self):
        self.equity_curve: list[dict] = []
        self.trades: list[Trade] = []
        self.positions: dict[str, Position] = {}
        self.cash: Decimal = self.config.initial_capital
        self.current_equity: Decimal = self.config.initial_capital
        self.peak_equity: Decimal = self.config.initial_capital
        self.bar_index: int = 0

    def run(self, bars: dict[str, list[Bar]]) -> BacktestResult:
        if not bars:
            raise BacktestError("No data provided for backtest")

        all_symbols = list(bars.keys())
        current_bars: dict[str, Bar] = {}

        bar_lists = list(bars.values())
        min_len = min(len(b) for b in bar_lists)
        total_bars = min_len

        for idx in range(total_bars):
            self.bar_index = idx
            for symbol in all_symbols:
                current_bars[symbol] = bars[symbol][idx]

            self._on_bar(current_bars)

        return self._compile_results()

    def _on_bar(self, bars: dict[str, Bar]) -> None:
        for symbol, bar in bars.items():
            self._update_positions(symbol, bar)
            self._check_stops(symbol, bar)

        if self.strategy:
            for symbol, bar in bars.items():
                market_ctx = self._build_context(bar)
                signals = self.strategy(bar, market_ctx)
                for signal in signals:
                    self._process_signal(signal, bar)

        self._update_equity()
        self._record_equity()

    def _process_signal(self, signal: Signal, bar: Bar) -> None:
        if signal.direction == SignalDirection.NEUTRAL:
            return

        side = Side.BUY if signal.direction == SignalDirection.LONG else Side.SELL
        quantity = self._compute_quantity(side, bar)

        if quantity <= 0:
            return

        order = Order(
            strategy_id=signal.strategy_id,
            portfolio_id="backtest",
            symbol=bar.symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            price=bar.close,
        )

        self._execute_order(order, bar)

    def _execute_order(self, order: Order, bar: Bar) -> Trade | None:
        fill_price = self._apply_slippage(bar.close, order.side)
        commission = self._compute_commission(fill_price, order.quantity)

        if order.side == Side.BUY:
            cost = fill_price * order.quantity + commission
            if cost > self.cash:
                max_qty = int((self.cash - commission) / fill_price)
                if max_qty <= 0:
                    return None
                order.quantity = max_qty
                cost = fill_price * order.quantity + commission

            if order.symbol in self.positions:
                pos = self.positions[order.symbol]
                total_qty = pos.quantity + order.quantity
                total_cost = (pos.average_price * pos.quantity) + (fill_price * order.quantity)
                pos.average_price = total_cost / total_qty
                pos.quantity = total_qty
            else:
                self.positions[order.symbol] = Position(
                    symbol=order.symbol,
                    side=PositionSide.LONG,
                    quantity=order.quantity,
                    average_price=fill_price,
                    current_price=fill_price,
                    strategy_id=order.strategy_id,
                )

            self.cash -= cost
            order.status = OrderStatus.FILLED

        else:
            if order.symbol not in self.positions:
                return None
            pos = self.positions[order.symbol]
            qty = min(order.quantity, pos.quantity)
            if qty <= 0:
                return None

            proceeds = fill_price * qty - commission
            pnl = (fill_price - pos.average_price) * qty
            pnl_pct = float((fill_price - pos.average_price) / pos.average_price * 100)

            self.cash += proceeds
            pos.quantity -= qty

            trade = Trade(
                strategy_id=order.strategy_id,
                symbol=order.symbol,
                side=order.side,
                entry_price=pos.average_price,
                exit_price=fill_price,
                quantity=qty,
                entry_time=bar.timestamp,
                exit_time=bar.timestamp,
                pnl=pnl,
                pnl_pct=pnl_pct,
            )
            self.trades.append(trade)

            if pos.quantity <= 0:
                del self.positions[order.symbol]

            return trade

        return None

    def _update_positions(self, symbol: str, bar: Bar) -> None:
        if symbol in self.positions:
            pos = self.positions[symbol]
            pos.current_price = bar.close
            pnl = (bar.close - pos.average_price) * pos.quantity
            pos.pnl = pnl
            pos.pnl_pct = float((bar.close - pos.average_price) / pos.average_price * 100)

    def _check_stops(self, symbol: str, bar: Bar) -> None:
        logger.debug("check_stops_not_implemented", symbol=symbol)

    def _update_equity(self) -> None:
        positions_value = sum(
            float(pos.current_price * pos.quantity) for pos in self.positions.values()
        )
        self.current_equity = self.cash + Decimal(str(positions_value))
        self.peak_equity = max(self.peak_equity, self.current_equity)

    def _record_equity(self) -> None:
        self.equity_curve.append(
            {
                "bar": self.bar_index,
                "equity": float(self.current_equity),
                "cash": float(self.cash),
                "drawdown": self._current_drawdown(),
            }
        )

    def _compute_quantity(self, side: Side, bar: Bar) -> int:
        if side == Side.BUY:
            risk_amount = float(self.cash) * 0.02
            qty = max(1, int(risk_amount / float(bar.close)))
            return qty
        elif side == Side.SELL:
            pos = self.positions.get(bar.symbol)
            if not pos:
                return 0
            return pos.quantity
        return 0

    def _apply_slippage(self, price: Decimal, side: Side) -> Decimal:
        slippage_amount = price * self.config.slippage
        if side == Side.BUY:
            return price + slippage_amount
        return price - slippage_amount

    def _compute_commission(self, price: Decimal, quantity: int) -> Decimal:
        return price * quantity * self.config.commission

    def _current_drawdown(self) -> float:
        if self.peak_equity == 0:
            return 0.0
        return float((self.peak_equity - self.current_equity) / self.peak_equity)

    def _build_context(self, bar: Bar) -> MarketContext:
        return MarketContext(
            timestamp=bar.timestamp,
            regime=MarketRegime.RANGING,
            volatility=float(bar.spread / bar.close),
            volume_ratio=1.0,
        )

    def _compute_metrics(self) -> dict:
        if not self.trades:
            return {
                "total_return": 0,
                "annualized_return": 0,
                "sharpe": 0,
                "sortino": 0,
                "max_drawdown": 0,
                "win_rate": 0,
                "profit_factor": 0,
                "total_trades": 0,
            }

        initial = float(self.config.initial_capital)
        final = float(self.current_equity)
        total_return_pct = (final - initial) / initial

        pnls = np.array([float(t.pnl) for t in self.trades])
        winning = pnls[pnls > 0]
        losing = pnls[pnls < 0]

        win_rate = len(winning) / len(pnls) if len(pnls) else 0
        gross_profit = float(np.sum(winning)) if len(winning) else 0
        gross_loss = float(np.abs(np.sum(losing))) if len(losing) else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        daily_returns = self._compute_daily_returns()
        sharpe = self._compute_sharpe(daily_returns)
        sortino = self._compute_sortino(daily_returns)
        max_dd = max(
            (e["drawdown"] for e in self.equity_curve),
            default=0.0,
        )

        return {
            "total_return": round(total_return_pct * 100, 2),
            "annualized_return": round(self._annualized_return(total_return_pct), 2),
            "sharpe": round(sharpe, 2),
            "sortino": round(sortino, 2),
            "max_drawdown": round(max_dd * 100, 2),
            "win_rate": round(win_rate * 100, 2),
            "profit_factor": round(profit_factor, 2),
            "total_trades": len(self.trades),
        }

    def _compute_daily_returns(self) -> np.ndarray:
        if len(self.equity_curve) < 2:
            return np.array([])
        equity = np.array([e["equity"] for e in self.equity_curve])
        prev = equity[:-1]
        curr = equity[1:]
        returns = np.where(prev > 0, (curr - prev) / prev, 0.0)
        return returns

    def _compute_sharpe(self, returns: np.ndarray, rf: float = 0.05) -> float:
        if len(returns) < 2:
            return 0.0
        excess = returns - rf / 252
        std = np.std(excess)
        if std == 0:
            return 0.0
        return float(np.mean(excess) / std * math.sqrt(252))

    def _compute_sortino(self, returns: np.ndarray, rf: float = 0.05) -> float:
        if len(returns) < 2:
            return 0.0
        excess = returns - rf / 252
        downside = excess[excess < 0]
        if len(downside) == 0 or np.std(downside) == 0:
            return 0.0
        return float(np.mean(excess) / np.std(downside) * math.sqrt(252))

    def _annualized_return(self, total_return: float) -> float:
        days = (self.config.end_date - self.config.start_date).days
        years = max(days, 1) / 365.25
        return ((1 + total_return) ** (1 / years) - 1) * 100

    @property
    def metrics(self) -> dict:
        return self._compute_metrics()

    def _compile_results(self) -> BacktestResult:
        metrics = self._compute_metrics()
        return BacktestResult(
            strategy_id="backtest",
            config=self.config,
            total_return=metrics["total_return"],
            annualized_return=metrics["annualized_return"],
            sharpe_ratio=metrics["sharpe"],
            sortino_ratio=metrics["sortino"],
            max_drawdown=metrics["max_drawdown"],
            win_rate=metrics["win_rate"],
            profit_factor=metrics["profit_factor"],
            total_trades=metrics["total_trades"],
            equity_curve=self.equity_curve,
            trades=self.trades,
            metrics=metrics,
        )
