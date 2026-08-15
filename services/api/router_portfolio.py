"""Portfolio and positions endpoints."""

from typing import Any

from fastapi import APIRouter, Depends

from packages.integration.pipeline import IntegratedBot
from services.api.dependencies import get_bot_started
from services.api.auth import optional_auth

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


@router.get("/summary")
async def portfolio_summary(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    pf = bot.portfolio.to_dict()
    return pf


@router.get("/positions")
async def get_positions(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> list[dict[str, Any]]:
    return [
        {
            "symbol": p.symbol,
            "quantity": p.quantity,
            "entry_price": float(p.entry_price),
            "current_price": float(p.current_price),
            "pnl": float(p.unrealized_pnl),
            "pnl_pct": float(p.unrealized_pnl_pct) if hasattr(p, "unrealized_pnl_pct") else 0.0,
            "strategy_id": p.strategy_id,
        }
        for p in bot.portfolio.get_all_positions()
    ]


@router.get("/positions/{symbol}")
async def get_position(
    symbol: str,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any] | None:
    pos = bot.portfolio.get_position(symbol)
    if pos is None:
        return None
    return {
        "symbol": pos.symbol,
        "quantity": pos.quantity,
        "entry_price": float(pos.entry_price),
        "current_price": float(pos.current_price),
        "pnl": float(pos.unrealized_pnl),
        "pnl_pct": float(pos.unrealized_pnl_pct) if hasattr(pos, "unrealized_pnl_pct") else 0.0,
        "strategy_id": pos.strategy_id,
    }


@router.get("/trades")
async def get_trades(
    limit: int = 100,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> list[dict[str, Any]]:
    trades = bot.portfolio.get_closed_trades(limit=limit)
    return [
        {
            "trade_id": getattr(t, "trade_id", str(id(t))),
            "symbol": t.symbol,
            "side": str(t.side.value) if hasattr(t, "side") else "",
            "quantity": t.quantity,
            "entry_price": float(t.entry_price),
            "exit_price": float(t.exit_price) if hasattr(t, "exit_price") and t.exit_price else None,
            "pnl": float(t.pnl) if hasattr(t, "pnl") else None,
            "strategy_id": getattr(t, "strategy_id", ""),
            "opened_at": str(t.opened_at),
            "closed_at": str(t.closed_at) if hasattr(t, "closed_at") and t.closed_at else None,
        }
        for t in trades
    ]


@router.get("/integrity")
async def portfolio_integrity(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    return bot.portfolio.verify_integrity()
