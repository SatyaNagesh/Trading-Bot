"""Research Engine FastAPI app."""

import sys
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException

sys.path.insert(0, str(Path(__file__).parent))

from packages.core.config import settings
from packages.core.logging import setup_logging
from service import create_hypothesis, list_hypotheses, get_available_data

setup_logging()

app = FastAPI(title="Research Engine", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "research"}


@app.post("/hypotheses")
async def create_hypothesis_endpoint(title: str, description: str, keywords: list[str] | None = None):
    try:
        result = await create_hypothesis(title, description, keywords)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/hypotheses")
async def list_hypotheses_endpoint(status: str | None = None):
    return await list_hypotheses(status)


@app.get("/data/{symbol}")
async def check_data(symbol: str, start: date, end: date):
    return await get_available_data(symbol, start, end)
