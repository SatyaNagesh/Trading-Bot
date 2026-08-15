"""Risk engine status and controls."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from packages.integration.pipeline import IntegratedBot
from services.api.dependencies import get_bot_started
from services.api.auth import optional_auth

router = APIRouter(prefix="/risk", tags=["Risk"])


@router.get("/summary")
async def risk_summary(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    return bot.risk.summary()


@router.post("/kill-switch")
async def set_kill_switch(
    active: bool,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, str]:
    bot.risk.kill_switch(active=active)
    return {"kill_switch": "activated" if active else "deactivated"}


@router.post("/emergency-stop")
async def emergency_stop(
    reason: str = "API emergency stop",
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, str]:
    bot.risk.emergency_stop(reason=reason)
    return {"status": "emergency_stopped", "reason": reason}


@router.get("/daily-loss")
async def daily_loss(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    s = bot.risk.summary()
    return {"daily_loss": s["daily_loss"], "max_daily_loss": s["max_daily_loss"], "daily_trades": s["daily_trades"]}
