"""Pre-trade risk checks — Risk Engine integration for execution validation."""

from packages.domain.models import Order, Position, RiskBudget
from packages.core.logging import get_logger

logger = get_logger("pretrade_risk")


async def check_order_risk(
    order: Order,
    portfolio_value: float,
    open_positions: list[Position],
    budget: RiskBudget | None = None,
) -> dict:
    if budget is None:
        budget = RiskBudget()
    checks = []
    current_positions = len(open_positions)
    if current_positions >= budget.max_positions:
        checks.append(
            {
                "check": "max_positions",
                "passed": False,
                "detail": f"At max {budget.max_positions} positions",
            }
        )
    else:
        checks.append({"check": "max_positions", "passed": True})
    estimated_notional = float(order.price or 0) * order.quantity
    leverage = (
        sum(float(p.current_price * p.quantity) for p in open_positions) + estimated_notional
    ) / max(portfolio_value, 1)
    if leverage > budget.max_leverage:
        checks.append(
            {
                "check": "max_leverage",
                "passed": False,
                "detail": f"Leverage {leverage:.2f} > max {budget.max_leverage}",
            }
        )
    else:
        checks.append({"check": "max_leverage", "passed": True})
    all_passed = all(c["passed"] for c in checks)
    return {
        "order_id": order.id,
        "symbol": order.symbol,
        "side": order.side.value,
        "quantity": order.quantity,
        "checks": checks,
        "approved": all_passed,
        "portfolio_value": portfolio_value,
    }
