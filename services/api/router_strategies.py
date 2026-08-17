"""Strategies, candidates, and backtesting endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from packages.integration.pipeline import IntegratedBot
from packages.backtesting.engine import BacktestEngine
from packages.backtesting.report import generate_summary
from packages.domain.models import BacktestConfig
from services.api.dependencies import get_bot_started
from services.api.auth import optional_auth

router = APIRouter(prefix="/strategies", tags=["Strategies"])


@router.get("/")
async def list_strategies(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> list[dict[str, Any]]:
    if bot.library is None:
        return []
    return bot.library.to_dicts()


@router.get("/lifecycle")
async def strategy_lifecycle(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    if bot.lifecycle is None:
        return {"error": "Lifecycle not available"}
    return bot.lifecycle.summary()


@router.get("/{strategy_id}")
async def get_strategy(
    strategy_id: str,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any] | None:
    if bot.library is None:
        return None
    entry = bot.library.get(strategy_id)
    if entry is None:
        return None
    return {
        "id": entry.template.id,
        "name": entry.template.name,
        "description": entry.template.description,
        "score": entry.composite_score,
        "sharpe": entry.result.sharpe_ratio,
        "total_return": entry.result.total_return,
        "max_drawdown": entry.result.max_drawdown,
        "win_rate": entry.result.win_rate,
        "profit_factor": entry.result.profit_factor,
        "total_trades": entry.result.total_trades,
        "stress_passed": entry.stress_passed,
    }


@router.get("/candidates/rankings")
async def get_rankings(
    top_n: int = 10,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> list[dict[str, Any]]:
    if bot.library is None or bot.ranker is None:
        return []
    entries = bot.library.all()
    ranked = bot.ranker.top_n(entries, n=top_n)
    return [
        {
            "strategy_id": r.entry.template.id,
            "name": r.entry.template.name,
            "score": bot.ranker.compute_score(r.entry),
            "sharpe": r.entry.result.sharpe_ratio,
        }
        for r in ranked
    ]


@router.post("/generate")
async def generate_strategies(
    count: int = 5,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    if bot.strategy_gen is None:
        raise HTTPException(status_code=400, detail="Strategy generator not available")
    templates = bot.strategy_gen.generate(max_candidates=count)
    return {"count": len(templates), "strategies": [t.name for t in templates]}


@router.get("/{strategy_id}/research")
async def research_strategy(
    strategy_id: str,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    if bot.research is None:
        return {"error": "Research not available"}
    return bot.research.explain_performance(strategy_id)
