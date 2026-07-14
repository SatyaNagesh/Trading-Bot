from datetime import datetime, date, timezone
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class TimeInForce(str, Enum):
    DAY = "DAY"
    IOC = "IOC"
    GTC = "GTC"
    FOK = "FOK"


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    SUBMITTED = "SUBMITTED"
    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class MarketRegime(str, Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    VOLATILE = "volatile"
    CRISIS = "crisis"


class StrategyStatus(str, Enum):
    DRAFT = "draft"
    BACKTESTING = "backtesting"
    VALIDATING = "validating"
    PAPER_TRADING = "paper_trading"
    LIVE = "live"
    RETIRED = "retired"
    REJECTED = "rejected"


class HypothesisStatus(str, Enum):
    PROPOSED = "proposed"
    TESTING = "testing"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class Bar(BaseModel):
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    symbol: str

    @property
    def spread(self) -> Decimal:
        return self.high - self.low

    @property
    def return_pct(self) -> float:
        return float((self.close - self.open) / self.open * 100)


class Trade(BaseModel):
    id: str = Field(default="")
    strategy_id: str
    symbol: str
    side: Side
    entry_price: Decimal
    exit_price: Decimal | None = None
    quantity: int
    entry_time: datetime
    exit_time: datetime | None = None
    pnl: Decimal = Decimal("0")
    pnl_pct: float = 0.0
    reason: str = ""


class Position(BaseModel):
    symbol: str
    side: PositionSide
    quantity: int
    average_price: Decimal
    current_price: Decimal
    pnl: Decimal = Decimal("0")
    pnl_pct: float = 0.0
    strategy_id: str = ""


class Order(BaseModel):
    id: str = Field(default="")
    strategy_id: str
    portfolio_id: str
    symbol: str
    side: Side
    order_type: OrderType = OrderType.MARKET
    quantity: int
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: TimeInForce = TimeInForce.DAY
    status: OrderStatus = OrderStatus.CREATED
    filled_quantity: int = 0
    average_fill_price: Decimal | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = None


class Signal(BaseModel):
    strategy_id: str
    direction: SignalDirection
    confidence: float = 0.0
    reason: list[str] = []
    indicator_values: dict[str, float] = {}
    metadata: dict = {}


class StrategyDefinition(BaseModel):
    id: str
    name: str
    version: str = "1.0.0"
    status: StrategyStatus = StrategyStatus.DRAFT
    dsl: str = ""
    author: str = ""
    tags: list[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = None


class Hypothesis(BaseModel):
    id: str
    title: str
    description: str
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    confidence: float = 0.0
    keywords: list[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BacktestConfig(BaseModel):
    initial_capital: Decimal = Decimal("1000000")
    start_date: date
    end_date: date
    commission: Decimal = Decimal("0.0005")
    slippage: Decimal = Decimal("0.001")
    spread: Decimal = Decimal("0.0002")


class BacktestResult(BaseModel):
    strategy_id: str
    config: BacktestConfig
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    total_commission: Decimal = Decimal("0")
    equity_curve: list[dict] = []
    trades: list[Trade] = []
    metrics: dict = {}


class MarketContext(BaseModel):
    timestamp: datetime
    regime: MarketRegime = MarketRegime.RANGING
    volatility: float = 0.0
    volume_ratio: float = 1.0
    indicators: dict[str, float] = {}


class RiskBudget(BaseModel):
    max_daily_loss: float = 0.02
    max_monthly_loss: float = 0.06
    max_drawdown: float = 0.20
    max_leverage: float = 1.0
    max_positions: int = 10


class Portfolio(BaseModel):
    id: str
    name: str = "default"
    initial_capital: Decimal
    current_value: Decimal
    cash: Decimal
    positions: list[Position] = []
    strategies: dict[str, float] = {}
