"""Self Review — post-trade analysis with lessons learned."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from packages.domain.models import Trade, Side, ExitReason


class TradeReview:
    def __init__(
        self,
        trade: Trade,
        previous_trades: list[Trade] | None = None,
        strategy_win_rate: float = 0.0,
    ):
        self.trade = trade
        self.previous_trades = previous_trades or []
        self.strategy_win_rate = strategy_win_rate
        self._review_id = str(uuid4())

    def _why_taken(self) -> str:
        reasons = []
        if self.trade.entry_reason:
            reasons.append(self.trade.entry_reason)
        if self.trade.side == Side.BUY:
            reasons.append("Long position initiated based on strategy signal")
        else:
            reasons.append("Short position initiated based on strategy signal")
        return "; ".join(reasons)

    def _why_result(self) -> str:
        if float(self.trade.pnl) > 0:
            if self.trade.exit_reason == ExitReason.TAKE_PROFIT.value:
                return "Trade reached target profit level. Strategy correctly identified the move."
            elif self.trade.exit_reason == ExitReason.SIGNAL_REVERSAL.value:
                return "Exited on signal reversal. Strategy captured directional move correctly."
            else:
                return "Trade was profitable. Strategy direction was correct."
        elif float(self.trade.pnl) < 0:
            if self.trade.exit_reason == ExitReason.STOP_LOSS.value:
                return (
                    "Trade hit stop loss. Market moved against the position beyond acceptable risk."
                )
            elif self.trade.exit_reason == ExitReason.RISK_LIMIT.value:
                return "Trade closed by risk limits. Risk management prevented further loss."
            else:
                return (
                    "Trade was unprofitable. Strategy direction was incorrect or timing was poor."
                )
        else:
            return "Trade closed at breakeven."

    def _risk_taken(self) -> str:
        if float(self.trade.pnl) < 0:
            return f"Loss of {abs(float(self.trade.pnl)):.2f} ({abs(self.trade.pnl_pct):.2f}%). Risk materialized fully."
        pos_value = float(self.trade.entry_price * self.trade.quantity)
        return f"Position size: {self.trade.quantity} @ {float(self.trade.entry_price):.2f} = {pos_value:.2f}. Risk managed within strategy parameters."

    def _better_alternatives(self) -> str:
        alternatives = []
        if float(self.trade.pnl) < 0:
            if self.trade.exit_reason == ExitReason.STOP_LOSS.value:
                alternatives.append(
                    "Consider wider stop loss if volatility was higher than expected"
                )
            alternatives.append("Consider waiting for better entry price")
            alternatives.append("Consider reducing position size in current market conditions")
        else:
            alternatives.append("Current approach appears effective")
            alternatives.append("Consider adding to winning positions in strong trends")
        return "; ".join(alternatives)

    def _confidence_adjustment(self) -> float:
        if float(self.trade.pnl) > 0:
            return min(1.0, self.strategy_win_rate + 0.02) if self.strategy_win_rate > 0 else 0.55
        else:
            return max(0.1, self.strategy_win_rate - 0.03) if self.strategy_win_rate > 0 else 0.40

    def _lessons(self) -> str:
        lessons = []
        if float(self.trade.pnl) < 0:
            wins_before = sum(1 for t in self.previous_trades[-5:] if float(t.pnl) > 0)
            if wins_before >= 4:
                lessons.append(
                    "Winning streak may have reduced risk awareness. Maintain discipline after wins."
                )
            if self.trade.exit_reason == ExitReason.STOP_LOSS.value:
                lessons.append(
                    "Stop loss placement needs review. Market may have different volatility profile."
                )
            elif self.trade.exit_reason == ExitReason.RISK_LIMIT.value:
                lessons.append("Consider adjusting risk parameters if frequent risk limit hits.")
        else:
            losses_before = sum(1 for t in self.previous_trades[-5:] if float(t.pnl) <= 0)
            if losses_before >= 3:
                lessons.append("Recovered from losing streak. Strategy adaptation may be working.")
        lessons.append("Continue tracking performance for long-term trend confirmation.")
        return "; ".join(lessons)

    def generate(self) -> dict[str, Any]:
        return {
            "review_id": self._review_id,
            "trade_id": self.trade.id,
            "strategy_id": self.trade.strategy_id,
            "symbol": self.trade.symbol,
            "side": self.trade.side.value,
            "entry_price": float(self.trade.entry_price),
            "exit_price": float(self.trade.exit_price) if self.trade.exit_price else None,
            "quantity": self.trade.quantity,
            "pnl": float(self.trade.pnl),
            "pnl_pct": self.trade.pnl_pct,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "why_taken": self._why_taken(),
            "why_result": self._why_result(),
            "risk_taken": self._risk_taken(),
            "better_alternatives": self._better_alternatives(),
            "confidence_adjustment": self._confidence_adjustment(),
            "lessons_learned": self._lessons(),
        }


class ReviewStore:
    def __init__(self):
        self._reviews: list[dict[str, Any]] = []

    def record(self, review: dict[str, Any]) -> None:
        self._reviews.append(review)

    def get_reviews(self, strategy_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        results = self._reviews
        if strategy_id:
            results = [r for r in results if r.get("strategy_id") == strategy_id]
        return list(reversed(results))[:limit]

    def all_reviews(self) -> list[dict[str, Any]]:
        return list(self._reviews)

    def count(self) -> int:
        return len(self._reviews)
