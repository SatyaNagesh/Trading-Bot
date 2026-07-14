"""Portfolio Engine — allocation, rebalancing, and performance tracking."""

from decimal import Decimal

from packages.core.logging import get_logger
from packages.domain.models import Portfolio, Position, RiskBudget
from packages.knowledge.graph import create_entity, find_entities

logger = get_logger("portfolio_service")


async def create_portfolio(name: str, initial_capital: float) -> dict:
    portfolio = Portfolio(
        name=name,
        initial_capital=Decimal(str(initial_capital)),
        current_value=Decimal(str(initial_capital)),
        cash=Decimal(str(initial_capital)),
    )
    props = {
        "name": portfolio.name,
        "initial_capital": float(portfolio.initial_capital),
        "current_value": float(portfolio.current_value),
        "cash": float(portfolio.cash),
    }
    result = await create_entity("Portfolio", props)
    logger.info("portfolio_created", name=name)
    return result


async def allocate(
    portfolio_value: float,
    risk_score: float,
    strategies: dict[str, float],
) -> dict:
    total_weight = sum(strategies.values())
    if total_weight <= 0:
        return {"error": "Total weight must be > 0"}
    allocations = {}
    for strategy, weight in strategies.items():
        alloc = portfolio_value * (weight / total_weight) * (1 - risk_score * 0.1)
        allocations[strategy] = round(alloc, 2)
    return {
        "portfolio_value": portfolio_value,
        "risk_score": risk_score,
        "allocations": allocations,
    }


async def rebalance(
    current_positions: list[Position],
    target_allocations: dict[str, float],
    portfolio_value: float,
) -> dict:
    trades = []
    for strategy, target_pct in target_allocations.items():
        target_value = portfolio_value * target_pct
        current_value = sum(
            float(p.current_price * p.quantity)
            for p in current_positions
            if p.strategy_id == strategy
        )
        diff = target_value - current_value
        trades.append({
            "strategy": strategy,
            "target": round(target_value, 2),
            "current": round(current_value, 2),
            "diff": round(diff, 2),
            "action": "buy" if diff > 0 else "sell" if diff < 0 else "hold",
        })
    return {"trades": trades}


async def portfolio_summary(portfolio_id: str) -> dict:
    result = await find_entities("Portfolio", {"id": portfolio_id})
    if not result:
        return {"error": "Portfolio not found"}
    return result[0]
