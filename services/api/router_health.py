"""Health, liveness, and readiness endpoints."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from starlette.requests import Request

from packages.integration.pipeline import IntegratedBot
from services.api.dependencies import get_bot_instance, get_bot_started
from services.api.auth import optional_auth

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "quantlab-api", "version": "0.1.0-rc1"}


@router.get("/ready")
async def readiness(
    bot: IntegratedBot | None = Depends(get_bot_instance),
) -> dict[str, Any]:
    if bot is None:
        return {"ready": False, "bot_running": False, "database_accessible": False, "components": {}}
    try:
        ns_count = len(bot.store.list_namespaces())
        db_ok = True
    except Exception:
        db_ok = False
    components = {
        "persistence": db_ok,
        "trading": bot._running,
        "portfolio": True,
        "risk": True,
    }
    return {
        "ready": bot._running and db_ok,
        "bot_running": bot._running,
        "database_accessible": db_ok,
        "components": components,
        "uptime_seconds": None,
    }


@router.get("/live")
async def liveness() -> dict[str, str]:
    return {"alive": "true", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health/report")
async def full_health_report(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    hm = bot.health_monitor
    return {
        "all_healthy": hm.all_healthy(),
        "checks": hm.report(),
        "alerts": hm.recent_alerts(limit=20),
    }
