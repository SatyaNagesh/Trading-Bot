"""Trading lifecycle — start, stop, status, run_cycle."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from packages.integration.pipeline import IntegratedBot
from packages.domain.models import Bar
from services.api.dependencies import get_bot_started
from services.api.auth import optional_auth

router = APIRouter(prefix="/trading", tags=["Trading"])


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


@router.post("/cycle")
async def trading_cycle(
    bars_data: dict[str, list[dict[str, Any]]] | None = None,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    try:
        parsed = None
        if bars_data:
            parsed = {}
            for symbol, bar_list in bars_data.items():
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
