"""Strategy Engine FastAPI app."""

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException

sys.path.insert(0, str(Path(__file__).parent))

from packages.core.logging import setup_logging
from service import create_strategy, list_strategies, evaluate_dsl

setup_logging()

app = FastAPI(title="Strategy Engine", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "strategy"}


@app.post("/strategies")
async def create_strategy_endpoint(
    name: str, dsl: str = "", author: str = "", tags: list[str] | None = None
):
    try:
        return await create_strategy(name, dsl, author, tags)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/strategies")
async def list_strategies_endpoint(status: str | None = None):
    return await list_strategies(status)


@app.post("/strategies/validate")
async def validate_dsl(dsl: str):
    return await evaluate_dsl(dsl)
