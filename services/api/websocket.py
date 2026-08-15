"""WebSocket endpoints for live dashboard updates."""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from packages.integration.pipeline import IntegratedBot
from packages.core.logging import get_logger
from services.api.dependencies import get_bot_instance

logger = get_logger("api_ws")

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    def __init__(self, max_clients: int = 50):
        self._connections: list[WebSocket] = []
        self._max_clients = max_clients

    async def connect(self, ws: WebSocket) -> bool:
        await ws.accept()
        if len(self._connections) >= self._max_clients:
            await ws.send_json({"type": "error", "message": "Max clients reached"})
            await ws.close()
            return False
        self._connections.append(ws)
        return True

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        stale = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)


manager = ConnectionManager()


def _build_snapshot(bot: IntegratedBot | None) -> dict[str, Any]:
    if bot is None:
        return {"type": "no_bot"}
    try:
        pf = bot.portfolio.to_dict() if hasattr(bot, "portfolio") else {}
        positions = len(bot.portfolio.get_all_positions()) if hasattr(bot, "portfolio") else 0
        risk_s = bot.risk.summary() if hasattr(bot, "risk") else {}
        alerts = bot.alert_engine.alert_count() if hasattr(bot, "alert_engine") else {}
        hm = bot.health_monitor.report() if hasattr(bot, "health_monitor") else {}
        metrics = bot.metrics.snapshot() if hasattr(bot, "metrics") else {}
        return {
            "type": "dashboard",
            "portfolio": {
                "nav": float(pf.get("net_asset_value", 0)),
                "cash": float(pf.get("cash", 0)),
                "equity": float(pf.get("equity", 0)),
                "open_positions": positions,
                "total_pnl": float(pf.get("total_pnl", 0)),
            },
            "risk": {
                "kill_switch": risk_s.get("kill_switch_active", False),
                "daily_loss": risk_s.get("daily_loss", 0),
                "daily_trades": risk_s.get("daily_trades", 0),
                "total_rejected": risk_s.get("total_rejected", 0),
            },
            "alerts": alerts,
            "health": hm,
            "metrics": metrics,
            "cycle_count": bot._cycle_count if hasattr(bot, "_cycle_count") else 0,
            "running": bot._running if hasattr(bot, "_running") else False,
        }
    except Exception:
        return {"type": "error"}


@router.websocket("/ws/dashboard")
async def dashboard_websocket(ws: WebSocket):
    connected = await manager.connect(ws)
    if not connected:
        return
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(ws)


@router.websocket("/ws/dashboard/stream")
async def dashboard_stream(ws: WebSocket):
    connected = await manager.connect(ws)
    if not connected:
        return
    try:
        while True:
            bot = get_bot_instance()
            snapshot = _build_snapshot(bot)
            await ws.send_json(snapshot)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        manager.disconnect(ws)


async def broadcast_dashboard(bot: IntegratedBot | None = None) -> None:
    snapshot = _build_snapshot(bot)
    await manager.broadcast(snapshot)
