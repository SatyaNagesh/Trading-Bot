"""Execution Engine FastAPI app."""

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException

sys.path.insert(0, str(Path(__file__).parent))

from packages.core.logging import setup_logging
from service import submit_order, list_orders, simulate_order_book

setup_logging()

app = FastAPI(title="Execution Engine", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "execution"}


@app.post("/orders")
async def create_order(
    symbol: str, side: str, quantity: int, order_type: str = "MARKET",
    price: float | None = None, strategy_id: str = "",
):
    return await submit_order(symbol, side, quantity, order_type, price, strategy_id)


@app.get("/orders")
async def get_orders(strategy_id: str | None = None):
    return await list_orders(strategy_id)


@app.get("/orderbook/{symbol}")
async def orderbook(symbol: str):
    return await simulate_order_book(symbol)
