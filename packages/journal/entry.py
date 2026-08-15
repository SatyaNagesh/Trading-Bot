"""Trade Journal — automatically generates detailed journal entries from completed trades."""

from datetime import datetime, timezone
from uuid import uuid4

from packages.core.logging import get_logger
from packages.domain.models import Trade, JournalEntry

logger = get_logger("trade_journal")


class TradeJournal:
    def __init__(self):
        self._entries: list[JournalEntry] = []

    def record_trade(
        self,
        trade: Trade,
        strategy_id: str = "",
        hypothesis_id: str = "",
        signal: str = "",
        market_regime: str = "",
        confidence: float = 0.0,
        composite_score: float = 0.0,
        expected_edge: float = 0.0,
        risk_score: float = 0.0,
        execution_details: dict | None = None,
        notes: str = "",
        tags: list[str] | None = None,
    ) -> JournalEntry:
        entry = JournalEntry(
            id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            strategy_id=strategy_id or trade.strategy_id,
            hypothesis_id=hypothesis_id,
            symbol=trade.symbol,
            side=trade.side,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            quantity=trade.quantity,
            position_size=trade.entry_price * trade.quantity,
            entry_time=trade.entry_time,
            exit_time=trade.exit_time,
            pnl=trade.pnl,
            pnl_pct=trade.pnl_pct,
            signal=signal,
            market_regime=market_regime,
            confidence=confidence,
            composite_score=composite_score,
            expected_edge=expected_edge,
            risk_score=risk_score,
            exit_reason=trade.exit_reason,
            execution_details=execution_details or {},
            notes=notes,
            tags=tags or [],
        )
        self._entries.append(entry)
        logger.info(
            "journal_entry_created",
            strategy=strategy_id,
            symbol=trade.symbol,
            pnl=float(trade.pnl),
            side=trade.side.value,
        )
        return entry

    def get_entries(self, strategy_id: str | None = None, limit: int = 100) -> list[JournalEntry]:
        entries = self._entries
        if strategy_id:
            entries = [e for e in entries if e.strategy_id == strategy_id]
        return list(reversed(entries))[:limit]

    def get_entry(self, entry_id: str) -> JournalEntry | None:
        for e in self._entries:
            if e.id == entry_id:
                return e
        return None

    def total_entries(self) -> int:
        return len(self._entries)

    def summary(self) -> dict:
        if not self._entries:
            return {
                "total_trades": 0,
                "total_pnl": 0.0,
                "win_rate": 0.0,
                "avg_pnl": 0.0,
                "avg_confidence": 0.0,
                "strategies": 0,
                "symbols": 0,
                "winning_trades": 0,
                "losing_trades": 0,
            }

        total_pnl = sum(float(e.pnl) for e in self._entries)
        winning = sum(1 for e in self._entries if float(e.pnl) > 0)
        losing = sum(1 for e in self._entries if float(e.pnl) < 0)

        return {
            "total_trades": len(self._entries),
            "total_pnl": round(total_pnl, 2),
            "winning_trades": winning,
            "losing_trades": losing,
            "win_rate": round(winning / len(self._entries) * 100, 2) if self._entries else 0,
            "avg_pnl": round(total_pnl / len(self._entries), 2) if self._entries else 0,
            "avg_confidence": round(
                sum(e.confidence for e in self._entries) / len(self._entries), 2
            )
            if self._entries
            else 0,
            "strategies": len(set(e.strategy_id for e in self._entries)),
            "symbols": len(set(e.symbol for e in self._entries)),
        }

    def export(self) -> list[dict]:
        return [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "strategy_id": e.strategy_id,
                "hypothesis_id": e.hypothesis_id,
                "symbol": e.symbol,
                "side": e.side.value,
                "entry_price": float(e.entry_price),
                "exit_price": float(e.exit_price) if e.exit_price else None,
                "quantity": e.quantity,
                "position_size": float(e.position_size),
                "pnl": float(e.pnl),
                "pnl_pct": e.pnl_pct,
                "signal": e.signal,
                "market_regime": e.market_regime,
                "confidence": e.confidence,
                "composite_score": e.composite_score,
                "expected_edge": e.expected_edge,
                "risk_score": e.risk_score,
                "exit_reason": e.exit_reason,
                "execution_details": e.execution_details,
                "notes": e.notes,
                "tags": e.tags,
            }
            for e in reversed(self._entries)
        ]
