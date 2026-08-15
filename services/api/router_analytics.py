"""Analytics and reports endpoints."""

from typing import Any

from fastapi import APIRouter, Depends

from packages.integration.pipeline import IntegratedBot
from services.api.dependencies import get_bot_started
from services.api.auth import optional_auth

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/regime")
async def current_regime(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    ro = bot.regime_observer
    return {
        "current_regime": ro.current_regime.value if ro.current_regime else "unknown",
        "history": ro.regime_history(limit=20) if hasattr(ro, "regime_history") else [],
        "counts": ro.regime_counts() if hasattr(ro, "regime_counts") else {},
    }


@router.get("/tracker")
async def strategy_tracker(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    t = bot.tracker
    return {"strategies": list(t._strategies.keys()) if hasattr(t, "_strategies") else []}


@router.get("/degradation")
async def degradation_summary(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    dd = bot.degradation
    summary = dd.health_summary() if hasattr(dd, "health_summary") else {}
    degraded = dd.get_degraded_strategies() if hasattr(dd, "get_degraded_strategies") else []
    return {
        "summary": summary,
        "degraded": [
            {"strategy_id": sid, "health": str(h), "issues": issues}
            for sid, h, issues in degraded
        ],
    }


@router.post("/compare")
async def compare_strategies(
    strategy_ids: list[str],
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    return bot.research.compare_strategies(strategy_ids)


@router.get("/tracker/{strategy_id}")
async def strategy_performance(
    strategy_id: str,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    t = bot.tracker
    perf = getattr(t, "get", lambda x: None)(strategy_id)
    if perf is None:
        return {"error": "No data for strategy"}
    return perf.performance_summary() if hasattr(perf, "performance_summary") else {}


@router.get("/health-monitor")
async def health_monitor_report(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    return bot.health_monitor.report()
