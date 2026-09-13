"""QuantLab AI — Unified REST API + WebSocket Layer.

Thin FastAPI wrapper over the existing IntegratedBot engine.
No business logic duplication — all calls delegate to engine modules.
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

_root = str(Path(__file__).resolve().parents[2])
if _root not in sys.path:
    sys.path.insert(0, _root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from packages.core.logging import setup_logging, get_logger
from packages.integration.pipeline import IntegrationConfig

from services.api.config import APIConfig
from services.api.auth import configure_auth
from services.api.middleware import register_middleware
from services.api.dependencies import create_bot, shutdown_bot
from services.api.router_trading import router as trading_router
from services.api.router_portfolio import router as portfolio_router
from services.api.router_orders import router as orders_router
from services.api.router_strategies import router as strategies_router
from services.api.router_analytics import router as analytics_router
from services.api.router_risk import router as risk_router
from services.api.router_production import router as production_router
from services.api.router_health import router as health_router
from services.api.router_alerts import router as alerts_router
from services.api.router_config import router as config_router
from services.api.websocket import router as ws_router
from services.api.router_advice import router as advice_router
from services.api.router_webhook import router as webhook_router

setup_logging()
logger = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = APIConfig()
    configure_auth(cfg)
    bot_cfg = IntegrationConfig()
    create_bot(bot_cfg)
    logger.info("api_started", host=cfg.host, port=cfg.port)
    yield
    shutdown_bot()
    logger.info("api_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="QuantLab AI API",
        version="0.1.0-rc1",
        description="Unified REST API and WebSocket layer for the QuantLab AI trading engine. "
                    "All operations delegate to the existing IntegratedBot and engine modules.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_middleware(app, APIConfig())

    app.include_router(health_router)
    app.include_router(trading_router)
    app.include_router(portfolio_router)
    app.include_router(orders_router)
    app.include_router(strategies_router)
    app.include_router(analytics_router)
    app.include_router(risk_router)
    app.include_router(production_router)
    app.include_router(alerts_router)
    app.include_router(config_router)
    app.include_router(ws_router)
    app.include_router(advice_router)
    app.include_router(webhook_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    cfg = APIConfig()
    uvicorn.run("services.api.main:app", host=cfg.host, port=cfg.port, reload=True)
