"""Production persistence, recovery, checkpoint, and metrics endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from packages.integration.pipeline import IntegratedBot
from services.api.dependencies import get_bot_started
from services.api.auth import optional_auth

router = APIRouter(prefix="/system", tags=["Production"])


@router.get("/namespaces")
async def list_namespaces(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> list[str]:
    return bot.store.list_namespaces()


@router.get("/namespaces/{namespace}")
async def get_namespace(
    namespace: str,
    limit: int = 100,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    keys = bot.store.list_keys(namespace)
    count = bot.store.count(namespace)
    items = []
    for k in keys[:limit]:
        val = bot.store.get(namespace, k)
        items.append({"key": k, "value": val, "timestamp": bot.store.get_updated_at(namespace, k)})
    return {"namespace": namespace, "count": count, "items": items}


@router.delete("/namespaces/{namespace}")
async def clear_namespace(
    namespace: str,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    deleted = bot.store.clear_namespace(namespace)
    return {"namespace": namespace, "deleted": deleted}


@router.post("/checkpoint")
async def create_checkpoint(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    ckpt = bot.checkpointer.create_checkpoint()
    return {
        "checkpoint_id": ckpt.checkpoint_id,
        "timestamp": ckpt.timestamp.isoformat(),
        "namespaces": ckpt.namespace_count,
        "entries": ckpt.entry_count,
    }


@router.get("/checkpoints")
async def list_checkpoints(
    limit: int = 20,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> list[dict[str, Any]]:
    return bot.checkpointer.list_checkpoints(limit=limit)


@router.post("/checkpoints/{checkpoint_id}/restore")
async def restore_checkpoint(
    checkpoint_id: str,
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    result = bot.checkpointer.restore_checkpoint(checkpoint_id)
    return {"status": "restored", "namespaces_restored": len(result)}


@router.post("/recovery")
async def run_recovery(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    result = bot.recovery.recover()
    return {
        "success": len(result.errors) == 0,
        "recovered_namespaces": result.recovered_namespaces,
        "errors": result.errors,
    }


@router.get("/metrics")
async def get_metrics(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any]:
    return bot.metrics.snapshot()


@router.get("/dashboard")
async def render_dashboard(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, str]:
    return {"dashboard": bot.dashboard.render()}


@router.get("/checkpoints/latest")
async def latest_checkpoint(
    bot: IntegratedBot = Depends(get_bot_started),
    _auth=Depends(optional_auth),
) -> dict[str, Any] | None:
    return bot.checkpointer.latest_checkpoint()
