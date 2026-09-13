"""Pydantic request/response schemas for the QuantLab API."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Generic ──────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: str
    service: str = "quantlab-api"
    version: str = "0.1.0-rc1"


class ReadinessResponse(BaseModel):
    ready: bool
    bot_running: bool
    database_accessible: bool
    components: dict[str, bool]


# ── Trading ──────────────────────────────────────────────────────────────

class TradingStopRequest(BaseModel):
    reason: str = "API request"


class TradingStatusResponse(BaseModel):
    running: bool
    cycle_count: int
    recovery_events: int


class CycleRunRequest(BaseModel):
    bars: dict[str, list[dict[str, Any]]] | None = None


class CycleResultResponse(BaseModel):
    cycle: int | str
    trades: int
    errors: list[str]
    dashboard: str | None = None
    metrics: dict[str, Any] | None = None


class AdviceScanRequest(BaseModel):
    bars: dict[str, list[dict[str, Any]]] | None = None


class ManualTradeRequest(BaseModel):
    symbol: str
    side: Literal["long", "short"] = "long"
    price: float | None = None


# ── Portfolio ────────────────────────────────────────────────────────────

class PortfolioResponse(BaseModel):
    initial_capital: float
    current_value: float
    cash: float
    equity: float
    net_asset_value: float
    open_positions: int
    total_trades: int
    total_pnl: float
    daily_pnl: float


class PositionResponse(BaseModel):
    symbol: str
    quantity: int
    entry_price: float
    current_price: float
    pnl: float
    pnl_pct: float
    strategy_id: str


class TradeResponse(BaseModel):
    trade_id: str
    symbol: str
    side: str
    quantity: int
    entry_price: float
    exit_price: float | None
    pnl: float | None
    strategy_id: str
    opened_at: str
    closed_at: str | None


# ── Orders ───────────────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    strategy_id: str
    portfolio_id: str
    symbol: str
    side: str
    order_type: str = "MARKET"
    quantity: int
    price: float | None = None
    stop_price: float | None = None
    time_in_force: str = "DAY"


class OrderResponse(BaseModel):
    id: str
    strategy_id: str
    portfolio_id: str
    symbol: str
    side: str
    order_type: str
    status: str
    quantity: int
    filled_quantity: int
    price: float | None
    stop_price: float | None
    created_at: str
    updated_at: str | None
    rejection_reason: str | None


class OrderTransitionRequest(BaseModel):
    reason: str = ""


class OrderCountResponse(BaseModel):
    pending: int
    submitted: int
    partially_filled: int
    filled: int
    rejected: int
    cancelled: int
    expired: int


# ── Risk ─────────────────────────────────────────────────────────────────

class RiskSummaryResponse(BaseModel):
    kill_switch_active: bool
    daily_loss: float
    daily_trades: int
    total_rejected: int
    max_drawdown: float
    max_daily_loss: float
    max_positions: int
    max_exposure_pct: float
    max_leverage: float
    max_position_size_pct: float


class KillSwitchRequest(BaseModel):
    active: bool


# ── Strategies ───────────────────────────────────────────────────────────

class StrategyEntry(BaseModel):
    id: str
    name: str
    description: str
    score: float
    sharpe: float
    total_return: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    stress_passed: bool
    regime: str
    risk: str
    confidence: str
    strengths: str
    weaknesses: str


class StrategyGenerateResponse(BaseModel):
    count: int
    strategies: list[StrategyEntry]


class BacktestRequest(BaseModel):
    symbol: str
    capital: float = 1000000
    days: int = 30
    strategy_type: str = "sma_crossover"


class BacktestResultResponse(BaseModel):
    symbol: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    volatility: float


# ── Analytics ────────────────────────────────────────────────────────────

class StrategyComparisonRequest(BaseModel):
    strategy_ids: list[str]


class RegimeResponse(BaseModel):
    current_regime: str
    history: list[dict[str, Any]]
    counts: dict[str, int]


class DegradationSummary(BaseModel):
    healthy: int
    degraded: int
    critical: int
    unknown: int
    total: int


# ── Alerts ───────────────────────────────────────────────────────────────

class AlertResponse(BaseModel):
    id: str
    level: str
    category: str
    message: str
    strategy_id: str | None
    timestamp: str
    acknowledged: bool


class AlertCountResponse(BaseModel):
    info: int
    warning: int
    critical: int
    total: int


# ── Health ───────────────────────────────────────────────────────────────

class HealthReport(BaseModel):
    all_healthy: bool
    checks: dict[str, Any]
    alerts: list[dict[str, Any]]


# ── Production ───────────────────────────────────────────────────────────

class NamespaceEntry(BaseModel):
    key: str
    value: Any
    timestamp: str


class NamespaceInfo(BaseModel):
    namespaces: list[str]


class CheckpointInfo(BaseModel):
    checkpoint_id: str
    timestamp: str
    namespaces: int
    entries: int


class MetricsSnapshot(BaseModel):
    counters: dict[str, int]
    gauges: dict[str, float]
    timings: dict[str, list[float]]


class RecoveryResultResponse(BaseModel):
    success: bool
    recovered_namespaces: list[str]
    errors: list[str]
    duration_ms: float
