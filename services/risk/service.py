"""Risk Engine — risk budgets, position sizing, and limits."""

from decimal import Decimal

from packages.core.logging import get_logger
from packages.domain.models import RiskBudget, Position
from packages.knowledge.graph import create_entity, find_entities

logger = get_logger("risk_service")


async def create_risk_budget(
    max_daily_loss: float = 0.02,
    max_drawdown: float = 0.20,
    max_leverage: float = 1.0,
    max_positions: int = 10,
) -> dict:
    budget = RiskBudget(
        max_daily_loss=max_daily_loss,
        max_drawdown=max_drawdown,
        max_leverage=max_leverage,
        max_positions=max_positions,
    )
    props = {
        "max_daily_loss": budget.max_daily_loss,
        "max_drawdown": budget.max_drawdown,
        "max_leverage": budget.max_leverage,
        "max_positions": budget.max_positions,
    }
    result = await create_entity("RiskBudget", props)
    logger.info("risk_budget_created")
    return result


async def compute_position_size(
    capital: float,
    price: float,
    risk_per_trade: float = 0.02,
    stop_loss_pct: float = 0.05,
) -> dict:
    risk_amount = capital * risk_per_trade
    stop_distance = price * stop_loss_pct
    quantity = int(risk_amount / stop_distance) if stop_distance > 0 else 0
    return {
        "capital": capital,
        "price": price,
        "risk_amount": round(risk_amount, 2),
        "stop_distance": round(stop_distance, 2),
        "suggested_quantity": max(1, quantity),
        "notional_value": round(price * max(1, quantity), 2),
    }


async def check_limits(
    portfolio_value: float,
    positions: list[Position],
    budget: RiskBudget | None = None,
) -> dict:
    if budget is None:
        budget = RiskBudget()
    current_positions = len(positions)
    leverage = sum(float(p.current_price * p.quantity) for p in positions) / max(portfolio_value, 1)
    return {
        "passed": current_positions <= budget.max_positions and leverage <= budget.max_leverage,
        "position_count": current_positions,
        "max_positions": budget.max_positions,
        "current_leverage": round(leverage, 2),
        "max_leverage": budget.max_leverage,
    }
