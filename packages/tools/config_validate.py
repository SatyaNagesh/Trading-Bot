#!/usr/bin/env python3
"""Configuration Validation Module — validates all config loading and type consistency."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dataclasses import dataclass, field
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from typing import Any


@dataclass
class ConfigTestResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ConfigValidationReport:
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tests: list[ConfigTestResult] = field(default_factory=list)
    total_duration_ms: float = 0.0

    @property
    def passed(self) -> int:
        return sum(1 for t in self.tests if t.passed)

    @property
    def failed(self) -> int:
        return sum(1 for t in self.tests if not t.passed)

    def summary_text(self) -> str:
        lines = [
            "=" * 60,
            f"CONFIG VALIDATION REPORT — {self.timestamp}",
            "=" * 60,
            f"Total: {len(self.tests)} | Passed: {self.passed} | Failed: {self.failed} | Duration: {self.total_duration_ms:.1f}ms",
            "",
            "-" * 60,
        ]
        for t in self.tests:
            icon = "  OK" if t.passed else "FAIL"
            lines.append(f"  [{icon}] {t.name}")
            lines.append(f"         {t.detail}")
        lines.append("-" * 60)
        return "\n".join(lines)


def time_it(fn):
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            return result, elapsed, None
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return None, elapsed, str(e)

    return wrapper


# ── 1. Core Settings ──────────────────────────────────────────────────


@time_it
def test_core_settings():
    from packages.core.config import Settings

    s = Settings()
    fields = {
        "env": s.env,
        "debug": s.debug,
        "log_level": s.log_level,
        "secret_key": s.secret_key,
        "api_host": s.api_host,
        "api_port": s.api_port,
        "api_workers": s.api_workers,
        "cors_origins": s.cors_origins,
        "default_initial_capital": s.default_initial_capital,
        "default_commission": s.default_commission,
        "default_slippage": s.default_slippage,
        "agent_default_model": s.agent_default_model,
        "agent_max_turns": s.agent_max_turns,
        "agent_timeout_seconds": s.agent_timeout_seconds,
    }
    assert s.env in ("development", "staging", "production")
    assert isinstance(s.debug, bool)
    assert isinstance(s.api_port, int) and s.api_port > 0
    assert isinstance(s.default_initial_capital, float) and s.default_initial_capital > 0
    assert isinstance(s.default_commission, float) and 0 <= s.default_commission < 1
    assert isinstance(s.default_slippage, float) and 0 <= s.default_slippage < 1
    assert isinstance(s.agent_max_turns, int) and s.agent_max_turns > 0
    return {"fields_accessible": len(fields), "default_env": s.env}


# ── 2. IntegrationConfig ──────────────────────────────────────────────


@time_it
def test_integration_config():
    from packages.integration.pipeline import IntegrationConfig

    cfg = IntegrationConfig()
    checks = {
        "config_path": isinstance(cfg.config_path, str),
        "db_path": isinstance(cfg.db_path, str),
        "initial_capital": cfg.initial_capital == Decimal("100000"),
        "max_candidates_per_cycle": cfg.max_candidates_per_cycle == 50,
        "max_evaluated_candidates": cfg.max_evaluated_candidates == 10,
        "backtest_days": cfg.backtest_days == 30,
        "commission": cfg.commission == 0.001,
        "slippage": cfg.slippage == 0.001,
        "min_sharpe_for_review": cfg.min_sharpe_for_review == 0.3,
        "min_trades_for_review": cfg.min_trades_for_review == 5,
        "sharpe_for_paper_test": cfg.sharpe_for_paper_test == 0.5,
        "sharpe_for_promotion": cfg.sharpe_for_promotion == 1.0,
        "min_trades_for_promotion": cfg.min_trades_for_promotion == 10,
        "checkpoint_interval": cfg.checkpoint_interval == 10,
        "top_n_ranked": cfg.top_n_ranked == 5,
        "simulation_max_cycles": cfg.simulation_max_cycles == 5000,
        "simulation_iteration_limit": cfg.simulation_iteration_limit == 200,
    }
    failed = [k for k, v in checks.items() if not v]
    assert not failed, f"checks failed: {failed}"
    assert isinstance(cfg.initial_capital, Decimal)
    assert isinstance(cfg.commission, float)
    assert isinstance(cfg.checkpoint_interval, int)
    return {"total_fields": len(checks), "all_sensible": True}


# ── 3. ProductionConfig ───────────────────────────────────────────────


@time_it
def test_production_config():
    from packages.production.config import ProductionConfig

    cfg = ProductionConfig()

    assert cfg.env == "development"
    assert cfg.debug is False

    pt = cfg.paper_trading
    assert isinstance(pt.symbols, list) and len(pt.symbols) == 3
    assert pt.position_sizing == "risk_parity"
    assert pt.max_positions == 10
    assert pt.initial_capital == 1_000_000.0

    r = cfg.risk
    assert r.max_concurrent_trades == 5
    assert r.max_position_size_pct == 20.0
    assert r.max_exposure_pct == 80.0
    assert r.max_drawdown_pct == 25.0
    assert r.max_daily_loss_pct == 5.0
    assert r.max_leverage == 1.0

    db = cfg.database
    assert db.dsn == "sqlite:///data/quantlab.db"
    assert db.pool_size == 5
    assert db.timeout_seconds == 30

    md = cfg.market_data
    assert md.provider == "yfinance"
    assert md.cache_ttl_seconds == 300

    return {
        "env": cfg.env,
        "paper_symbols": pt.symbols,
        "risk_fields": 6,
    }


# ── 4. ScheduleConfig ─────────────────────────────────────────────────


@time_it
def test_schedule_config():
    from packages.autonomous.scheduler import ScheduleConfig, AutonomousScheduler

    sc = ScheduleConfig()
    assert sc.research_interval_hours == 4.0
    assert sc.paper_trading_interval_minutes == 15.0
    assert sc.learning_interval_hours == 1.0
    assert sc.reporting_interval_hours == 6.0
    assert sc.health_check_interval_minutes == 5.0
    assert sc.max_candidates_per_cycle == 500
    assert sc.max_paper_positions == 10
    assert sc.degradation_threshold_sharpe == 0.5
    assert sc.min_trades_for_analysis == 20
    assert sc.max_active_experiments == 5

    s = AutonomousScheduler(sc)
    cid = s.start()
    assert cid is not None
    assert s.is_running is True

    s.next_cycle()
    status = s.status()
    assert status["cycle_count"] == 1
    assert status["is_running"] is True

    s.mark_research_done()
    s.mark_learning_done()
    s.mark_report_done()
    s.stop()
    assert s.is_running is False

    return {
        "intervals": {
            "research_hours": sc.research_interval_hours,
            "trading_minutes": sc.paper_trading_interval_minutes,
            "learning_hours": sc.learning_interval_hours,
        },
        "cycle_count": status["cycle_count"],
    }


# ── 5. BrokerConfig ───────────────────────────────────────────────────


@time_it
def test_broker_config():
    from packages.broker.gateway import BrokerConfig, SimulatedBroker, PaperBroker

    configs = {
        "paper": BrokerConfig(mode="paper"),
        "simulated": BrokerConfig(mode="simulated"),
        "alpaca": BrokerConfig(mode="alpaca", api_key="test", api_secret="test"),
        "empty": BrokerConfig(),
    }
    for label, bc in configs.items():
        assert isinstance(bc.mode, str)
        assert hasattr(bc, "api_key")
        assert hasattr(bc, "api_secret")
        assert hasattr(bc, "access_token")
        assert hasattr(bc, "base_url")

    sim = SimulatedBroker(configs["simulated"])
    assert sim.config.mode == "simulated"

    paper = PaperBroker(configs["paper"])
    assert paper.config.mode == "paper"
    assert paper._fill_probability == 0.97

    return {
        "broker_modes": list(configs.keys()),
        "simulated_works": True,
        "paper_works": True,
    }


# ── 6. BacktestConfig ─────────────────────────────────────────────────


@time_it
def test_backtest_config():
    from packages.domain.models import BacktestConfig

    today = date.today()
    thirty_ago = today - timedelta(days=30)

    bc = BacktestConfig(
        start_date=thirty_ago,
        end_date=today,
    )
    assert bc.initial_capital == Decimal("1000000")
    assert bc.start_date == thirty_ago
    assert bc.end_date == today
    assert bc.commission == Decimal("0.0005")
    assert bc.slippage == Decimal("0.001")
    assert bc.spread == Decimal("0.0002")

    assert isinstance(bc.initial_capital, Decimal)
    assert isinstance(bc.commission, Decimal)
    assert isinstance(bc.slippage, Decimal)
    assert isinstance(bc.start_date, date)
    assert isinstance(bc.end_date, date)

    assert bc.end_date > bc.start_date

    one_day = BacktestConfig(start_date=today, end_date=today)
    assert one_day.end_date >= one_day.start_date

    year_ago = today - timedelta(days=365)
    bc_long = BacktestConfig(start_date=year_ago, end_date=today)
    delta = (bc_long.end_date - bc_long.start_date).days
    assert delta > 30

    return {
        "start": str(thirty_ago),
        "end": str(today),
        "initial_capital": str(bc.initial_capital),
        "date_range_days": (today - thirty_ago).days,
    }


# ── 7. Env Variables ──────────────────────────────────────────────────


@time_it
def test_env_variables():
    markers = {
        "SECRET_KEY": os.environ.get("SECRET_KEY", ""),
        "DB_PATH": os.environ.get("DB_PATH", ""),
        "REDIS_DSN": os.environ.get("REDIS_DSN", ""),
        "POSTGRES_DSN": os.environ.get("POSTGRES_DSN", ""),
        "API_KEY": os.environ.get("API_KEY", ""),
    }
    from packages.core.config import Settings

    s = Settings()
    pattern_fields = {
        "secret_key": s.secret_key,
        "postgres_dsn": s.postgres_dsn,
        "redis_dsn": s.redis_dsn,
        "qdrant_url": s.qdrant_url,
        "neo4j_uri": s.neo4j_uri,
        "rabbitmq_dsn": s.rabbitmq_dsn,
        "minio_endpoint": s.minio_endpoint,
    }
    for key, val in pattern_fields.items():
        assert isinstance(val, str)

    env_available = {k: bool(v) for k, v in markers.items()}

    return {
        "env_variables_accessible": len(markers),
        "config_secret_fields": len(pattern_fields),
        "env_set": {k for k, v in env_available.items() if v},
        "note": "All fields accessible as strings; actual values depend on .env",
    }


# ── 8. Type Consistency ───────────────────────────────────────────────


@time_it
def test_type_consistency():
    from decimal import Decimal
    from datetime import date, datetime

    from packages.domain.models import BacktestConfig, Order, Trade, Position, Bar, Signal
    from packages.integration.pipeline import IntegrationConfig
    from packages.core.config import Settings

    findings: dict[str, str] = {}

    cfg = Settings()
    findings["core_capital_type"] = type(cfg.default_initial_capital).__name__
    assert isinstance(cfg.default_initial_capital, float)
    assert isinstance(cfg.default_commission, float)
    assert isinstance(cfg.api_port, int)
    assert isinstance(cfg.agent_max_turns, int)
    assert isinstance(cfg.debug, bool)

    ic = IntegrationConfig()
    findings["integration_capital_type"] = type(ic.initial_capital).__name__
    assert isinstance(ic.initial_capital, Decimal)
    assert isinstance(ic.commission, float)
    assert isinstance(ic.max_candidates_per_cycle, int)
    assert isinstance(ic.slippage, float)

    now = datetime.now(timezone.utc)
    bt = BacktestConfig(start_date=date.today(), end_date=date.today())
    findings["backtest_capital_type"] = type(bt.initial_capital).__name__
    assert isinstance(bt.initial_capital, Decimal)
    assert isinstance(bt.commission, Decimal)
    assert isinstance(bt.slippage, Decimal)
    assert isinstance(bt.start_date, date)

    bar = Bar(
        timestamp=now,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100.5"),
        volume=10000,
        symbol="TEST",
    )
    assert isinstance(bar.open, Decimal)
    assert isinstance(bar.close, Decimal)
    assert isinstance(bar.volume, int)
    findings["bar_price_type"] = type(bar.close).__name__

    order = Order(strategy_id="s1", portfolio_id="p1", symbol="TEST", side="BUY", quantity=10)
    assert isinstance(order.quantity, int)
    assert order.price is None or isinstance(order.price, Decimal)
    findings["order_quantity_type"] = type(order.quantity).__name__

    pos = Position(
        symbol="TEST",
        side="LONG",
        quantity=10,
        average_price=Decimal("100"),
        current_price=Decimal("101"),
    )
    assert isinstance(pos.quantity, int)
    assert isinstance(pos.average_price, Decimal)
    assert isinstance(pos.pnl, Decimal)
    assert isinstance(pos.pnl_pct, float)
    findings["position_price_type"] = type(pos.average_price).__name__

    trade = Trade(
        strategy_id="s1",
        symbol="TEST",
        side="BUY",
        entry_price=Decimal("100"),
        quantity=10,
        entry_time=now,
    )
    assert isinstance(trade.entry_price, Decimal)
    assert isinstance(trade.quantity, int)
    assert isinstance(trade.pnl, Decimal)
    assert isinstance(trade.pnl_pct, float)
    findings["trade_pnl_type"] = type(trade.pnl).__name__

    signal = Signal(strategy_id="s1", direction="long")
    assert isinstance(signal.confidence, float)
    findings["signal_confidence_type"] = type(signal.confidence).__name__

    return {
        "checks": len(findings),
        "core": f"capital={findings['core_capital_type']}",
        "integration": f"capital={findings['integration_capital_type']}",
        "backtest": f"capital={findings['backtest_capital_type']}",
        "bar": f"price={findings['bar_price_type']}",
        "order": f"quantity={findings['order_quantity_type']}",
        "position": f"price={findings['position_price_type']}",
        "trade": f"pnl={findings['trade_pnl_type']}",
        "signal": f"confidence={findings['signal_confidence_type']}",
        "pattern": "Decimal for money, float for rates/pcts, int for counts",
    }


TESTS: list[tuple[str, Any]] = [
    ("1. Core Settings", test_core_settings),
    ("2. IntegrationConfig", test_integration_config),
    ("3. ProductionConfig", test_production_config),
    ("4. ScheduleConfig", test_schedule_config),
    ("5. BrokerConfig", test_broker_config),
    ("6. BacktestConfig", test_backtest_config),
    ("7. Env Variables", test_env_variables),
    ("8. Type Consistency", test_type_consistency),
]


def run() -> ConfigValidationReport:
    report = ConfigValidationReport()
    start = time.perf_counter()

    for name, fn in TESTS:
        result, elapsed, error = fn()
        if error:
            report.tests.append(ConfigTestResult(name=name, passed=False, detail=error))
        else:
            report.tests.append(
                ConfigTestResult(
                    name=name,
                    passed=True,
                    detail=str(result) if result else "ok",
                )
            )

    report.total_duration_ms = (time.perf_counter() - start) * 1000
    return report


if __name__ == "__main__":
    report = run()
    print(report.summary_text())
    sys.exit(0 if report.failed == 0 else 1)
