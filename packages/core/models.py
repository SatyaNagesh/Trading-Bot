import uuid
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Numeric,
    DateTime,
    Date,
    Text,
    Enum as SAEnum,
    ForeignKey,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import DeclarativeBase

from packages.domain.models import (
    Side,
    OrderType,
    OrderStatus,
    StrategyStatus,
    HypothesisStatus,
)


class Base(DeclarativeBase):
    pass


def ulid() -> str:
    return str(uuid.uuid4())[:8] + datetime.now().strftime("%y%m%d%H%M%S")


class MarketData(Base):
    __tablename__ = "market_data"

    id = Column(String, primary_key=True, default=ulid)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    open = Column(Numeric(20, 4), nullable=False)
    high = Column(Numeric(20, 4), nullable=False)
    low = Column(Numeric(20, 4), nullable=False)
    close = Column(Numeric(20, 4), nullable=False)
    volume = Column(Integer, nullable=False)
    source = Column(String(50), default="yfinance")
    created_at = Column(DateTime, default=_now)

    __table_args__ = (
        Index("ix_market_data_symbol_ts", "symbol", "timestamp"),
        UniqueConstraint("symbol", "timestamp", name="uq_symbol_timestamp"),
    )


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(String, primary_key=True, default=ulid)
    name = Column(String(200), nullable=False)
    version = Column(String(20), default="1.0.0")
    status = Column(SAEnum(StrategyStatus), default=StrategyStatus.DRAFT)
    dsl = Column(Text, default="")
    author = Column(String(100), default="")
    tags = Column(JSON, default=list)
    sharpe = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, onupdate=_now)


class Hypothesis(Base):
    __tablename__ = "hypotheses"

    id = Column(String, primary_key=True, default=ulid)
    title = Column(String(300), nullable=False)
    description = Column(Text, default="")
    status = Column(SAEnum(HypothesisStatus), default=HypothesisStatus.PROPOSED)
    confidence = Column(Float, default=0.0)
    keywords = Column(JSON, default=list)
    created_at = Column(DateTime, default=_now)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id = Column(String, primary_key=True, default=ulid)
    strategy_id = Column(String, ForeignKey("strategies.id"), nullable=False)
    initial_capital = Column(Numeric(20, 2), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    total_return = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    sortino_ratio = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    config = Column(JSON, default=dict)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=_now)
    completed_at = Column(DateTime, nullable=True)


class Trade(Base):
    __tablename__ = "trades"

    id = Column(String, primary_key=True, default=ulid)
    backtest_id = Column(String, ForeignKey("backtest_runs.id"), nullable=True)
    strategy_id = Column(String, ForeignKey("strategies.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(SAEnum(Side), nullable=False)
    entry_price = Column(Numeric(20, 4), nullable=False)
    exit_price = Column(Numeric(20, 4), nullable=True)
    quantity = Column(Integer, nullable=False)
    pnl = Column(Numeric(20, 2), default=0)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, default=ulid)
    strategy_id = Column(String, ForeignKey("strategies.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(SAEnum(Side), nullable=False)
    order_type = Column(SAEnum(OrderType), default=OrderType.MARKET)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(20, 4), nullable=True)
    status = Column(SAEnum(OrderStatus), default=OrderStatus.CREATED)
    filled_quantity = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, onupdate=_now)
