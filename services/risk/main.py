"""Risk Engine FastAPI app."""

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException

sys.path.insert(0, str(Path(__file__).parent))

from packages.core.logging import setup_logging
from service import create_risk_budget, compute_position_size, check_limits

setup_logging()

app = FastAPI(title="Risk Engine", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "risk"}


@app.post("/budgets")
async def create_budget(
    max_daily_loss: float = 0.02,
    max_drawdown: float = 0.20,
    max_leverage: float = 1.0,
    max_positions: int = 10,
):
    return await create_risk_budget(max_daily_loss, max_drawdown, max_leverage, max_positions)


@app.post("/positions/size")
async def position_size(
    capital: float, price: float, risk_per_trade: float = 0.02, stop_loss_pct: float = 0.05
):
    return await compute_position_size(capital, price, risk_per_trade, stop_loss_pct)
