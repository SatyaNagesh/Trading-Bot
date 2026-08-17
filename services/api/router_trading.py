"""Trading lifecycle — start, stop, status, run_cycle, manual trade."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from packages.integration.pipeline import IntegratedBot
from packages.domain.models import Bar, Signal, SignalDirection
from services.api.dependencies import get_bot_started
from services.api.auth import optional_auth
from services.api.schemas import (
    CycleRunRequest,
    CycleResultResponse,
    ManualTradeRequest,
)

router = APIRouter(prefix="/trading", tags=["Trading"])


def _latest_price(symbol: str) -> float | None:
    """Last cached close for a symbol, or None if unknown."""
    try:
        import pickle

        with open("data/genuine_bars.pkl", "rb") as f:
            bars = pickle.load(f)
        series = bars.get(symbol)
        if not series:
            return None
        last = float(series[-1].close)
        return last
    except Exception:  # noqa: BLE001
        return None


@router.get("/status")
async def trading_status(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    return {
        "running": bot._running,
        "cycle_count": bot._cycle_count,
        "recovery_events": bot._recovery_events,
    }


@router.post("/start")
async def trading_start(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, str]:
    if not bot._running:
        bot.start()
    return {"status": "started"}


@router.post("/stop")
async def trading_stop(
    reason: str = "API request",
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, str]:
    if bot._running:
        bot.stop()
    return {"status": "stopped", "reason": reason}


@router.post("/cycle", response_model=CycleResultResponse)
async def trading_cycle(
    body: CycleRunRequest | None = None,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    try:
        parsed = None
        if body is not None and body.bars:
            parsed = {}
            for symbol, bar_list in body.bars.items():
                parsed[symbol] = [Bar(**b) for b in bar_list]
        result = await bot.run_cycle(parsed)
        return {
            "cycle": result.get("cycle", "unknown"),
            "trades": result.get("trades", 0),
            "errors": result.get("errors", []),
            "dashboard": result.get("dashboard", ""),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manual")
async def manual_trade(
    body: ManualTradeRequest,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    """Manually call out a long/short trade, auto-sized, respecting market hours."""
    symbol = (body.symbol or "").strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    price = body.price
    if price is None:
        price = _latest_price(symbol)
    if price is None or price <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"no known price for {symbol}; provide one via 'price'",
        )

    direction = SignalDirection.LONG if body.side == "long" else SignalDirection.SHORT
    ts = datetime.utcnow()
    p = Decimal(str(price))
    tick = p * Decimal("0.0005")
    bar = Bar(
        timestamp=ts,
        open=p,
        high=p + tick,
        low=p - tick,
        close=p,
        volume=1,
        symbol=symbol,
    )
    signal = Signal(
        strategy_id=f"manual:{body.side}",
        symbol=symbol,
        direction=direction,
        confidence=1.0,
        reason=[f"manual-callout:{body.side}:{symbol}"],
        timestamp=ts.isoformat(),
    )

    result = await bot.loop.process_signal(signal, bar)
    return {
        "requested": {"symbol": symbol, "side": body.side, "price": price},
        "execution": result,
    }
