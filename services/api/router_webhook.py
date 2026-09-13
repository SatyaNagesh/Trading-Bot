"""TradingView webhook ingestion + event observability (PAPER-ONLY).

POST /webhook/tradingview receives a TradingView alert, validates and dedupes
it, then routes it through the EXISTING paper trading loop. It can never place
a live order: the gateway refuses live-capable brokers (PAPER_GUARD) and the
loop's ExecutionEngine additionally guards live brokers while the system is
closed. Observability endpoints query the durable event ledger.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from packages.integration.pipeline import IntegratedBot
from packages.webhook import tradingview as tv
from services.api.auth import optional_auth
from services.api.dependencies import get_bot_started

router = APIRouter(prefix="/webhook", tags=["Webhook"])

_gateway: tv.TradingViewEventGateway | None = None
_gateway_owner: int | None = None

# HTTP status per recorded event outcome (recorded outcomes return 2xx so
# TradingView does not retry a decided event; bad-input returns 4xx).
_BAD_INPUT = {
    "MALFORMED",
    "FORBIDDEN_SOURCE",
    "STALE",
    "FUTURE",
    "UNKNOWN_SYMBOL",
    "INVALID_TIMEFRAME",
    "NO_PRICE",
}


def _get_gateway(bot: IntegratedBot) -> tv.TradingViewEventGateway:
    global _gateway, _gateway_owner
    owner = id(bot)
    settings = tv.WebhookSettings.from_env()
    if _gateway is None or _gateway_owner != owner:
        _gateway = tv.TradingViewEventGateway(settings=settings, loop=bot.loop)
        _gateway_owner = owner
    return _gateway


def _reset_gateway() -> None:
    """Test hook: clear the cached gateway after env changes."""
    global _gateway, _gateway_owner
    _gateway = None
    _gateway_owner = None


@router.post("/tradingview")
async def tradingview_webhook(
    request: Request,
    bot: IntegratedBot = Depends(get_bot_started),
) -> JSONResponse:
    """Ingest one TradingView alert into the paper pipeline (PAPER ONLY)."""
    header_secret = request.headers.get(tv.SECRET_HEADER)
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        payload = None

    gateway = _get_gateway(bot)
    record = await gateway.handle(
        payload,
        header_secret,
        remote_addr=request.client.host if request.client else None,
    )
    status = record.get("status", "UNKNOWN")
    if status in ("NOT_CONFIGURED", "PAPER_GUARD"):
        return JSONResponse(record, status_code=503)
    if status == "UNAUTHENTICATED":
        return JSONResponse(record, status_code=401)
    if status in _BAD_INPUT:
        return JSONResponse(record, status_code=400)
    return JSONResponse(record, status_code=200)


@router.get("/events")
async def webhook_events(
    limit: int = 20,
    status: str | None = None,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> list[dict[str, Any]]:
    """Query the durable TradingView event ledger (auth optional)."""
    gateway = _get_gateway(bot)
    return gateway.last_events(limit=min(max(limit, 1), 1000), status=status)


@router.get("/status")
async def webhook_status(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    """Webhook integration status + event counts + last event."""
    gateway = _get_gateway(bot)
    summary = gateway.summary()
    summary["session"] = gateway.session.status()
    return summary