"""Orders and executions endpoints."""

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from packages.domain.models import Side, OrderType, TimeInForce
from packages.integration.pipeline import IntegratedBot
from services.api.dependencies import get_bot_started
from services.api.auth import optional_auth

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("/")
async def create_order(
    strategy_id: str,
    portfolio_id: str,
    symbol: str,
    side: str,
    quantity: int,
    order_type: str = "MARKET",
    price: float | None = None,
    stop_price: float | None = None,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    try:
        side_enum = Side.BUY if side.upper() == "BUY" else Side.SELL
        type_enum = OrderType[order_type.upper()]
        tif = TimeInForce.DAY
        order = bot.oms.create_order(
            strategy_id=strategy_id,
            portfolio_id=portfolio_id,
            symbol=symbol,
            side=side_enum,
            order_type=type_enum,
            quantity=quantity,
            price=Decimal(str(price)) if price is not None else None,
            stop_price=Decimal(str(stop_price)) if stop_price is not None else None,
            time_in_force=tif,
        )
        risk_check = bot.risk.check_order(order, bot.portfolio)
        if not risk_check.get("approved", True):
            bot.oms.reject(order.id, reason="Risk check failed")
            return {"order_id": order.id, "status": "rejected", "reason": risk_check}
        return {
            "order_id": order.id,
            "symbol": order.symbol,
            "side": order.side.value,
            "quantity": order.quantity,
            "status": order.status.value,
            "created_at": order.created_at.isoformat()
            if hasattr(order.created_at, "isoformat")
            else str(order.created_at),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/")
async def list_orders(
    strategy_id: str | None = None,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> list[dict[str, Any]]:
    orders = bot.oms.get_all_orders(strategy_id=strategy_id)
    return [
        {
            "id": o.id,
            "strategy_id": o.strategy_id,
            "symbol": o.symbol,
            "side": o.side.value,
            "status": o.status.value,
            "quantity": o.quantity,
            "filled_quantity": o.filled_quantity,
            "price": float(o.price) if o.price else None,
            "created_at": str(o.created_at),
        }
        for o in orders
    ]


@router.get("/open")
async def get_open_orders(
    symbol: str | None = None,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> list[dict[str, Any]]:
    orders = bot.oms.get_open_orders(symbol=symbol)
    return [
        {
            "id": o.id,
            "symbol": o.symbol,
            "side": o.side.value,
            "status": o.status.value,
            "quantity": o.quantity - o.filled_quantity,
            "price": float(o.price) if o.price else None,
        }
        for o in orders
    ]


@router.get("/counts")
async def order_counts(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    return bot.oms.order_count()


@router.get("/{order_id}")
async def get_order(
    order_id: str,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any] | None:
    order = bot.oms.get_order(order_id)
    if order is None:
        return None
    return {
        "id": order.id,
        "strategy_id": order.strategy_id,
        "symbol": order.symbol,
        "side": order.side.value,
        "status": order.status.value,
        "quantity": order.quantity,
        "filled_quantity": order.filled_quantity,
        "price": float(order.price) if order.price else None,
        "created_at": str(order.created_at),
    }


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    reason: str = "API request",
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, str]:
    try:
        bot.oms.cancel(order_id, reason=reason)
        return {"status": "cancelled", "order_id": order_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
