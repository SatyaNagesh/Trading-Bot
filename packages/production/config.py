"""Configuration Management — YAML config with typed sections, defaults, env-override."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


CONFIG_PATH = Path("config.yaml")


@dataclass
class PaperTradingConfig:
    symbols: list[str] = field(default_factory=lambda: ["RELIANCE", "TCS", "HDFCBANK"])
    position_sizing: str = "risk_parity"
    max_positions: int = 10
    initial_capital: float = 1_000_000.0


@dataclass
class RiskConfig:
    max_concurrent_trades: int = 5
    max_position_size_pct: float = 20.0
    max_exposure_pct: float = 80.0
    max_drawdown_pct: float = 25.0
    max_daily_loss_pct: float = 5.0
    max_leverage: float = 1.0


@dataclass
class LoggingConfig:
    level: str = "INFO"
    json: bool = False
    rotation_mb: int = 100
    retention_days: int = 30
    directory: str = "logs"


@dataclass
class ScheduleConfig:
    research_interval_hours: float = 4.0
    paper_trading_interval_minutes: float = 15.0
    learning_interval_hours: float = 1.0
    reporting_interval_hours: float = 6.0
    health_check_interval_minutes: float = 5.0
    checkpoint_interval_minutes: float = 15.0


@dataclass
class DatabaseConfig:
    dsn: str = "sqlite:///data/quantlab.db"
    postgres_dsn: str = ""
    pool_size: int = 5
    timeout_seconds: int = 30


@dataclass
class MarketDataConfig:
    provider: str = "yfinance"
    fallback_provider: str = "alphavantage"
    api_key: str = ""
    cache_ttl_seconds: int = 300


@dataclass
class ProductionConfig:
    env: str = "development"
    debug: bool = False
    data_dir: str = "data"
    paper_trading: PaperTradingConfig = field(default_factory=PaperTradingConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    market_data: MarketDataConfig = field(default_factory=MarketDataConfig)


def default_config() -> ProductionConfig:
    return ProductionConfig()


def _from_dict(data: dict, cls: type) -> Any:
    if hasattr(cls, "__dataclass_fields__"):
        fields = cls.__dataclass_fields__
        kwargs = {}
        for k, v in data.items():
            if k in fields:
                ftype = fields[k].type
                if hasattr(ftype, "__dataclass_fields__") and isinstance(v, dict):
                    kwargs[k] = _from_dict(v, ftype)
                elif isinstance(v, list) and getattr(ftype, "__origin__", None) is list:
                    kwargs[k] = v
                else:
                    kwargs[k] = v
        return cls(**kwargs)
    return data


def load_config(path: str | Path = CONFIG_PATH) -> ProductionConfig:
    p = Path(path)
    if not p.exists():
        cfg = default_config()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            yaml.dump(_to_dict(cfg), f, default_flow_style=False)
        return cfg
    with open(p) as f:
        raw: dict = yaml.safe_load(f) or {}
    return _from_dict(raw, ProductionConfig)


def _to_dict(cfg: ProductionConfig) -> dict:
    result: dict[str, Any] = {}
    for field_name in cfg.__dataclass_fields__:
        val = getattr(cfg, field_name)
        if hasattr(val, "__dataclass_fields__"):
            sub: dict[str, Any] = {}
            for sf in val.__dataclass_fields__:
                sub[sf] = getattr(val, sf)
            result[field_name] = sub
        else:
            result[field_name] = val
    return result
