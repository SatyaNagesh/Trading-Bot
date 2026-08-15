"""Alerts and notifications endpoints."""

from typing import Any

from fastapi import APIRouter, Depends

from packages.integration.pipeline import IntegratedBot
from packages.optimization.alerts import AlertSeverity
from services.api.dependencies import get_bot_started
from services.api.auth import optional_auth

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("/")
async def get_alerts(
    level: str | None = None,
    category: str | None = None,
    limit: int = 100,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> list[dict[str, Any]]:
    severity = AlertSeverity[level.upper()] if level and level.upper() in AlertSeverity.__members__ else None
    return bot.alert_engine.alerts(level=severity, category=category, limit=limit)


@router.get("/counts")
async def alert_counts(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    return bot.alert_engine.alert_count()


@router.post("/check")
async def check_alerts(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> list[dict[str, Any]]:
    return bot.alert_engine.check_all()


@router.delete("/clear")
async def clear_alerts(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, str]:
    bot.alert_engine.clear_alerts()
    return {"status": "cleared"}
