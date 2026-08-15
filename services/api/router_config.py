"""Read-only configuration endpoints."""

from typing import Any

from fastapi import APIRouter, Depends

from packages.integration.pipeline import IntegratedBot
from services.api.dependencies import get_bot_started
from services.api.auth import optional_auth

router = APIRouter(prefix="/config", tags=["Configuration"])


@router.get("/")
async def get_config(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    cfg = bot.config
    return {
        "initial_capital": float(cfg.initial_capital),
        "max_candidates_per_cycle": cfg.max_candidates_per_cycle,
        "backtest_days": cfg.backtest_days,
        "commission": cfg.commission,
        "slippage": cfg.slippage,
        "min_sharpe_for_review": cfg.min_sharpe_for_review,
        "sharpe_for_paper_test": cfg.sharpe_for_paper_test,
        "sharpe_for_promotion": cfg.sharpe_for_promotion,
        "checkpoint_interval": cfg.checkpoint_interval,
        "top_n_ranked": cfg.top_n_ranked,
    }


@router.get("/risk-budget")
async def get_risk_budget(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    budget = bot.risk.budget if hasattr(bot.risk, "budget") else None
    if budget is None:
        return {}
    return {
        "max_concurrent_trades": budget.max_concurrent_trades,
        "max_position_size_pct": budget.max_position_size_pct * 100,
        "max_exposure_pct": budget.max_exposure_pct * 100,
        "max_drawdown_pct": budget.max_drawdown * 100,
        "max_daily_loss_pct": budget.max_daily_loss * 100,
        "max_leverage": budget.max_leverage,
        "per_strategy_allocation_pct": budget.per_strategy_allocation_pct * 100,
    }


@router.get("/schedule")
async def get_schedule(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    sched = bot.scheduler
    st = sched.status() if hasattr(sched, "status") else {}
    return st
