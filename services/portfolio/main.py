"""Portfolio Engine FastAPI app."""

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException

sys.path.insert(0, str(Path(__file__).parent))

from packages.core.logging import setup_logging
from service import create_portfolio, allocate, rebalance

setup_logging()

app = FastAPI(title="Portfolio Engine", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "portfolio"}


@app.post("/portfolios")
async def create(name: str, initial_capital: float):
    return await create_portfolio(name, initial_capital)


@app.post("/portfolios/allocate")
async def allocate_endpoint(
    portfolio_value: float, risk_score: float = 0.5, strategies: dict[str, float] = {}
):
    return await allocate(portfolio_value, risk_score, strategies)


@app.post("/portfolios/rebalance")
async def rebalance_endpoint(
    portfolio_value: float, target_allocations: dict[str, float] = {}
):
    return await rebalance([], target_allocations, portfolio_value)
