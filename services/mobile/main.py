"""Mobile dashboard API — React Native backend endpoints."""

from fastapi import FastAPI
from pydantic import BaseModel

from packages.core.logging import setup_logging

setup_logging()

app = FastAPI(title="QuantLab Mobile API", version="0.1.0")


class PortfolioSummary(BaseModel):
    total_value: float = 0
    cash: float = 0
    pnl_today: float = 0
    pnl_total: float = 0
    active_strategies: int = 0
    open_positions: int = 0


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mobile-api"}


@app.get("/api/v1/portfolio/summary")
async def get_portfolio_summary():
    return PortfolioSummary()


@app.get("/api/v1/strategies/status")
async def get_strategies_status():
    return {"strategies": [], "active": 0}


@app.get("/api/v1/performance/daily")
async def get_daily_performance(days: int = 30):
    return {"days": days, "equity_curve": []}
