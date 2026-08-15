"""Gate 6: Signal Optimization — comprehensive tests."""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4

from packages.domain.models import (
    Signal, SignalDirection, Bar, MarketContext, MarketRegime, Trade, Side, ExitReason,
)
from packages.analytics.engine import TradeAnalytics
from packages.analytics.strategy_tracker import StrategyPerformance, StrategyTracker
from packages.analytics.regime_observer import RegimeObserver, MarketRegime as AnalyticsRegime
from packages.analytics.degradation import DegradationDetector, StrategyHealth
from packages.analytics.research import ResearchAssistant
from packages.optimization.signal_optimizer import SignalOptimizer, REGIME_COMPATIBILITY
from packages.optimization.allocation import StrategyAllocator
from packages.optimization.alerts import AlertEngine, AlertSeverity, AlertCategory


def make_trade(
    strategy_id: str = "test",
    symbol: str = "AAPL",
    side: Side = Side.BUY,
    entry_price: Decimal = Decimal("100"),
    exit_price: Decimal = Decimal("110"),
    quantity: int = 100,
    pnl: Decimal = Decimal("1000"),
    pnl_pct: float = 10.0,
    entry_reason: str = "signal",
    exit_reason: str = ExitReason.TAKE_PROFIT.value,
    exit_time: datetime | None = None,
) -> Trade:
    return Trade(
        id=str(uuid4()),
        strategy_id=strategy_id,
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        entry_time=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        exit_time=exit_time or datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc),
        pnl=pnl,
        pnl_pct=pnl_pct,
        entry_reason=entry_reason,
        exit_reason=exit_reason,
    )


def make_signal(
    strategy_id: str = "strat_a",
    direction: SignalDirection = SignalDirection.LONG,
    confidence: float = 0.7,
    reason: list[str] | None = None,
) -> Signal:
    return Signal(
        strategy_id=strategy_id,
        direction=direction,
        confidence=confidence,
        reason=reason or ["trend following signal"],
    )


def make_bar(timestamp: datetime | None = None) -> Bar:
    return Bar(
        timestamp=timestamp or datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        open=Decimal("100"),
        high=Decimal("105"),
        low=Decimal("99"),
        close=Decimal("104"),
        volume=10000,
        symbol="AAPL",
    )


def make_ctx() -> MarketContext:
    return MarketContext(
        timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        regime=MarketRegime.TRENDING,
        volatility=0.15,
    )


# =============================================================================
# SignalOptimizer
# =============================================================================

class TestSignalOptimizer:
    def test_passthrough_no_dependencies(self):
        opt = SignalOptimizer()
        signals = [make_signal()]
        ctx = make_ctx()
        result = opt.optimize(signals, ctx)
        assert len(result) == 1
        assert result[0].strategy_id == "strat_a"
        assert result[0].confidence == 0.7

    def test_filters_neutral_with_min_confidence(self):
        opt = SignalOptimizer(min_confidence=0.3)
        signals = [
            make_signal(direction=SignalDirection.NEUTRAL, confidence=0.0),
            make_signal(direction=SignalDirection.LONG, confidence=0.1),
        ]
        ctx = make_ctx()
        result = opt.optimize(signals, ctx)
        assert len(result) == 1
        assert result[0].direction == SignalDirection.NEUTRAL

    def test_suppresses_low_confidence(self):
        opt = SignalOptimizer(min_confidence=0.5)
        signals = [make_signal(confidence=0.3)]
        ctx = make_ctx()
        result = opt.optimize(signals, ctx)
        assert len(result) == 0

    def test_health_gating_degraded(self):
        tracker = StrategyTracker()
        detector = DegradationDetector(tracker)
        perf = tracker.register("strat_a")
        for i in range(10):
            pnl = Decimal("50") if i < 5 else Decimal("-80")
            perf.add_trade(make_trade(pnl=pnl, pnl_pct=5.0 if i < 5 else -8.0))
            perf.record_confidence(0.5)
        detector._health_states["strat_a"] = StrategyHealth.DEGRADED
        opt = SignalOptimizer(degradation_detector=detector)
        signals = [make_signal(strategy_id="strat_a")]
        ctx = make_ctx()
        result = opt.optimize(signals, ctx)
        assert len(result) == 0
        assert opt.stats["suppressed_health"] == 1

    def test_health_gating_retired(self):
        tracker = StrategyTracker()
        detector = DegradationDetector(tracker)
        detector._health_states["strat_a"] = StrategyHealth.RETIRED
        opt = SignalOptimizer(degradation_detector=detector)
        signals = [make_signal(strategy_id="strat_a")]
        ctx = make_ctx()
        result = opt.optimize(signals, ctx)
        assert len(result) == 0

    def test_active_health_passes(self):
        tracker = StrategyTracker()
        detector = DegradationDetector(tracker)
        tracker.register("strat_a")
        detector._health_states["strat_a"] = StrategyHealth.ACTIVE
        opt = SignalOptimizer(degradation_detector=detector)
        signals = [make_signal(strategy_id="strat_a")]
        ctx = make_ctx()
        result = opt.optimize(signals, ctx)
        assert len(result) == 1

    def test_watchlist_passes_through(self):
        tracker = StrategyTracker()
        detector = DegradationDetector(tracker)
        tracker.register("strat_a")
        detector._health_states["strat_a"] = StrategyHealth.WATCHLIST
        opt = SignalOptimizer(degradation_detector=detector)
        signals = [make_signal(strategy_id="strat_a")]
        ctx = make_ctx()
        result = opt.optimize(signals, ctx)
        assert len(result) == 1

    def test_regime_gating_incompatible(self):
        observer = RegimeObserver()
        observer._current_regime = AnalyticsRegime.SIDEWAYS
        opt = SignalOptimizer(regime_observer=observer)
        signals = [make_signal(reason=["trend following signal"])]
        ctx = make_ctx()
        result = opt.optimize(signals, ctx)
        assert len(result) == 0
        assert opt.stats["suppressed_regime"] == 1

    def test_regime_gating_compatible(self):
        observer = RegimeObserver()
        observer._current_regime = AnalyticsRegime.TRENDING
        opt = SignalOptimizer(regime_observer=observer)
        signals = [make_signal(reason=["trend following signal"])]
        ctx = make_ctx()
        result = opt.optimize(signals, ctx)
        assert len(result) == 1

    def test_regime_unknown_passes(self):
        observer = RegimeObserver()
        observer._current_regime = AnalyticsRegime.UNKNOWN
        opt = SignalOptimizer(regime_observer=observer)
        signals = [make_signal(reason=["trend following signal"])]
        ctx = make_ctx()
        result = opt.optimize(signals, ctx)
        assert len(result) == 1

    def test_calibrates_confidence_from_history(self):
        tracker = StrategyTracker()
        perf = tracker.register("strat_a")
        for i in range(20):
            pnl = Decimal("100") if i < 12 else Decimal("-50")
            perf.add_trade(make_trade(pnl=pnl, pnl_pct=5.0 if i < 12 else -2.5))
        opt = SignalOptimizer(strategy_tracker=tracker)
        signals = [make_signal(strategy_id="strat_a", confidence=0.5)]
        ctx = make_ctx()
        result = opt.optimize(signals, ctx)
        assert len(result) == 1
        calibrated = result[0].confidence
        assert calibrated != 0.5
        assert 0.0 <= calibrated <= 1.0

    def test_no_calibration_few_trades(self):
        tracker = StrategyTracker()
        perf = tracker.register("strat_a")
        perf.add_trade(make_trade())
        opt = SignalOptimizer(strategy_tracker=tracker)
        signals = [make_signal(strategy_id="strat_a", confidence=0.5)]
        ctx = make_ctx()
        result = opt.optimize(signals, ctx)
        assert result[0].confidence == 0.5

    def test_wrap_decorates_function(self):
        def fake_signal_fn(bar, ctx):
            return [make_signal()]
        opt = SignalOptimizer()
        wrapped = opt.wrap(fake_signal_fn)
        bar = make_bar()
        ctx = make_ctx()
        result = wrapped(bar, ctx)
        assert len(result) == 1

    def test_multiple_signals_partial_filter(self):
        tracker = StrategyTracker()
        detector = DegradationDetector(tracker)
        tracker.register("strat_a")
        detector._health_states["strat_a"] = StrategyHealth.ACTIVE
        detector._health_states["strat_b"] = StrategyHealth.DEGRADED
        opt = SignalOptimizer(degradation_detector=detector)
        signals = [
            make_signal(strategy_id="strat_a"),
            make_signal(strategy_id="strat_b"),
        ]
        ctx = make_ctx()
        result = opt.optimize(signals, ctx)
        assert len(result) == 1
        assert result[0].strategy_id == "strat_a"

    def test_strategy_type_detection(self):
        opt = SignalOptimizer()
        cases = [
            (["mean reversion signal"], "mean_reversion"),
            (["breakout above resistance"], "breakout"),
            (["volatility expansion"], "volatility_arb"),
            (["scalp fast move"], "scalping"),
            (["random entry"], "trend_following"),
        ]
        for reasons, expected in cases:
            sig = make_signal(reason=reasons)
            detected = opt._detect_strategy_type(sig)
            assert detected == expected, f"{reasons} -> {detected}, expected {expected}"

    def test_reset_stats(self):
        opt = SignalOptimizer(min_confidence=0.9)
        signals = [make_signal(confidence=0.3)]
        ctx = make_ctx()
        opt.optimize(signals, ctx)
        assert opt.stats["suppressed_confidence"] == 1
        opt.reset_stats()
        assert opt.stats["suppressed_confidence"] == 0

    def test_custom_regime_map(self):
        custom_map = {"custom_type": ["crisis"]}
        observer = RegimeObserver()
        observer._current_regime = AnalyticsRegime.TRENDING
        opt = SignalOptimizer(regime_observer=observer, regime_map=custom_map)
        signals = [make_signal()]
        ctx = make_ctx()
        result = opt.optimize(signals, ctx)
        assert len(result) == 1

        observer._current_regime = AnalyticsRegime.CRISIS
        ctx2 = make_ctx()
        result2 = opt.optimize([make_signal()], ctx2)
        assert len(result2) == 1

    def test_neutral_confidence_bypass_min_confidence(self):
        opt = SignalOptimizer(min_confidence=0.5)
        signals = [make_signal(direction=SignalDirection.NEUTRAL, confidence=0.0)]
        ctx = make_ctx()
        result = opt.optimize(signals, ctx)
        assert len(result) == 1


# =============================================================================
# StrategyAllocator
# =============================================================================

class TestStrategyAllocator:
    def test_equal_weight(self):
        alloc = StrategyAllocator()
        result = alloc.equal_weight(["a", "b", "c", "d"])
        assert all(v == 0.25 for v in result.values())
        assert sum(result.values()) == 1.0

    def test_equal_weight_empty(self):
        alloc = StrategyAllocator()
        assert alloc.equal_weight([]) == {}

    def test_equal_weight_single(self):
        alloc = StrategyAllocator()
        result = alloc.equal_weight(["a"])
        assert result == {"a": 1.0}

    def test_health_filtered(self):
        tracker = StrategyTracker()
        detector = DegradationDetector(tracker)
        detector._health_states["a"] = StrategyHealth.ACTIVE
        detector._health_states["b"] = StrategyHealth.DEGRADED
        tracker.register("a")
        tracker.register("b")
        alloc = StrategyAllocator(tracker=tracker, detector=detector)
        filtered = alloc.health_filtered(["a", "b"])
        assert filtered == ["a"]

    def test_health_filtered_no_detector(self):
        alloc = StrategyAllocator()
        assert alloc.health_filtered(["a", "b"]) == ["a", "b"]

    def test_performance_weighted(self):
        tracker = StrategyTracker()
        for sid in ["a", "b"]:
            perf = tracker.register(sid)
            for i in range(10):
                pnl = Decimal(str(100 - i * 5)) if sid == "a" else Decimal(str(10 - i * 5))
                pnl_pct = 10.0 - i * 0.5 if sid == "a" else 1.0 - i * 0.5
                perf.add_trade(make_trade(strategy_id=sid, pnl=pnl, pnl_pct=pnl_pct))
        alloc = StrategyAllocator(tracker=tracker)
        result = alloc.performance_weighted(["a", "b"])
        assert result["a"] > result["b"]
        assert abs(sum(result.values()) - 1.0) < 0.001

    def test_performance_weighted_fallback_equal(self):
        alloc = StrategyAllocator()
        result = alloc.performance_weighted(["a", "b"])
        assert result == {"a": 0.5, "b": 0.5}

    def test_sharpe_weighted(self):
        tracker = StrategyTracker()
        perf_a = tracker.register("a")
        perf_b = tracker.register("b")
        for i in range(10):
            pnl_a = Decimal(str(100 - i * 5))
            pnl_b = Decimal(str(-20 + i * 3))
            perf_a.add_trade(make_trade(strategy_id="a", pnl=pnl_a, pnl_pct=10.0 - i * 0.5))
            perf_b.add_trade(make_trade(strategy_id="b", pnl=pnl_b, pnl_pct=-2.0 + i * 0.3))
        alloc = StrategyAllocator(tracker=tracker)
        result = alloc.sharpe_weighted(["a", "b"])
        assert result["a"] > result["b"]
        assert abs(sum(result.values()) - 1.0) < 0.001

    def test_sharpe_weighted_fallback_equal(self):
        alloc = StrategyAllocator()
        result = alloc.sharpe_weighted(["a", "b"])
        assert result == {"a": 0.5, "b": 0.5}

    def test_risk_parity(self):
        tracker = StrategyTracker()
        perf_a = tracker.register("a")
        perf_b = tracker.register("b")
        for i in range(10):
            perf_a.add_trade(make_trade(strategy_id="a", pnl=Decimal("100"), pnl_pct=5.0))
            perf_b.add_trade(make_trade(strategy_id="b", pnl=Decimal("-80"), pnl_pct=-8.0))
        alloc = StrategyAllocator(tracker=tracker)
        result = alloc.risk_parity(["a", "b"])
        assert result["a"] > result["b"]

    def test_risk_parity_fallback_equal(self):
        alloc = StrategyAllocator()
        result = alloc.risk_parity(["a", "b"])
        assert result == {"a": 0.5, "b": 0.5}

    def test_allocate_default_method(self):
        tracker = StrategyTracker()
        for sid in ["a", "b"]:
            tracker.register(sid)
            for i in range(5):
                pnl = Decimal(str(50 - i * 8))
                pnl_pct = 5.0 - i * 0.8
                tracker.get(sid).add_trade(make_trade(strategy_id=sid, pnl=pnl, pnl_pct=pnl_pct))
        alloc = StrategyAllocator(tracker=tracker)
        result = alloc.allocate(["a", "b"])
        assert sorted(result.keys()) == sorted(["a", "b"])
        assert abs(sum(result.values()) - 1.0) < 0.001

    def test_allocate_equal_method(self):
        alloc = StrategyAllocator()
        result = alloc.allocate(["a", "b", "c"], method="equal")
        assert all(v == pytest.approx(1.0 / 3, abs=0.001) for v in result.values())

    def test_allocate_sharpe_method(self):
        tracker = StrategyTracker()
        perf_a = tracker.register("a")
        perf_b = tracker.register("b")
        for i in range(10):
            pnl_a = Decimal(str(100 - i * 5))
            pnl_b = Decimal(str(-30 + i * 2))
            perf_a.add_trade(make_trade(strategy_id="a", pnl=pnl_a, pnl_pct=10.0 - i * 0.5))
            perf_b.add_trade(make_trade(strategy_id="b", pnl=pnl_b, pnl_pct=-3.0 + i * 0.2))
        alloc = StrategyAllocator(tracker=tracker)
        result = alloc.allocate(["a", "b"], method="sharpe")
        assert result["a"] > 0
        assert result["b"] >= 0

    def test_allocate_risk_parity_method(self):
        tracker = StrategyTracker()
        for sid in ["a", "b"]:
            tracker.register(sid)
            for i in range(10):
                tracker.get(sid).add_trade(make_trade(strategy_id=sid, pnl=Decimal("50"), pnl_pct=2.0))
        alloc = StrategyAllocator(tracker=tracker)
        result = alloc.allocate(["a", "b"], method="risk_parity")
        assert abs(sum(result.values()) - 1.0) < 0.001

    def test_allocate_excludes_degraded(self):
        tracker = StrategyTracker()
        detector = DegradationDetector(tracker)
        tracker.register("a")
        tracker.register("b")
        detector._health_states["b"] = StrategyHealth.DEGRADED
        alloc = StrategyAllocator(tracker=tracker, detector=detector)
        result = alloc.allocate(["a", "b"])
        assert result["a"] == 1.0
        assert result["b"] == 0.0

    def test_allocate_all_degraded(self):
        tracker = StrategyTracker()
        detector = DegradationDetector(tracker)
        tracker.register("a")
        detector._health_states["a"] = StrategyHealth.RETIRED
        alloc = StrategyAllocator(tracker=tracker, detector=detector)
        result = alloc.allocate(["a"])
        assert result["a"] == 0.0

    def test_allocate_empty_list(self):
        alloc = StrategyAllocator()
        assert alloc.allocate([]) == {}

    def test_normalize_zero_total(self):
        result = StrategyAllocator._normalize({"a": 0.0, "b": 0.0})
        assert result == {"a": 0.0, "b": 0.0}

    def test_normalize_single(self):
        result = StrategyAllocator._normalize({"a": 5.0})
        assert result == {"a": 1.0}


# =============================================================================
# AlertEngine
# =============================================================================

class TestAlertEngine:
    def test_no_alerts_initially(self):
        engine = AlertEngine()
        assert engine.alerts() == []

    def test_degradation_alerts(self):
        tracker = StrategyTracker()
        detector = DegradationDetector(tracker)
        tracker.register("strat_a")
        detector._health_states["strat_a"] = StrategyHealth.ACTIVE
        detector._degradation_log.append({
            "strategy_id": "strat_a",
            "from": "ACTIVE",
            "to": "WATCHLIST",
            "reasons": ["sharpe_fall"],
            "timestamp": "2025-01-01T00:00:00Z",
        })
        engine = AlertEngine(detector=detector)
        alerts = engine.check_degradation_alerts()
        assert len(alerts) >= 1
        assert alerts[0]["category"] == "degradation"
        assert alerts[0]["severity"] == "low"

    def test_degradation_high_severity(self):
        tracker = StrategyTracker()
        detector = DegradationDetector(tracker)
        tracker.register("strat_a")
        detector._degradation_log.append({
            "strategy_id": "strat_a",
            "from": "WATCHLIST",
            "to": "DEGRADED",
            "reasons": ["sharpe_fall", "drawdown_rise", "win_rate_fall"],
            "timestamp": "2025-01-01T00:00:00Z",
        })
        engine = AlertEngine(detector=detector)
        alerts = engine.check_degradation_alerts()
        assert alerts[0]["severity"] == "high"

    def test_regime_change_alert(self):
        observer = RegimeObserver()
        observer._current_regime = AnalyticsRegime.TRENDING
        engine = AlertEngine(regime_observer=observer)
        first = engine.check_regime_alerts()
        assert first == []
        observer._current_regime = AnalyticsRegime.CRISIS
        second = engine.check_regime_alerts()
        assert len(second) == 1
        assert second[0]["category"] == "regime"
        assert second[0]["severity"] == "medium"

    def test_regime_change_normal_severity(self):
        observer = RegimeObserver()
        observer._current_regime = AnalyticsRegime.TRENDING
        engine = AlertEngine(regime_observer=observer)
        engine.check_regime_alerts()
        observer._current_regime = AnalyticsRegime.SIDEWAYS
        alerts = engine.check_regime_alerts()
        assert alerts[0]["severity"] == "low"

    def test_performance_degrading_alert(self):
        tracker = StrategyTracker()
        perf = tracker.register("strat_a")
        for i in range(10):
            pnl = Decimal("50") if i < 3 else Decimal("-80")
            perf.add_trade(make_trade(pnl=pnl, pnl_pct=5.0 if i < 3 else -8.0))
        engine = AlertEngine(tracker=tracker)
        alerts = engine.check_performance_alerts()
        degrading_alerts = [a for a in alerts if a["category"] == "performance"]
        assert len(degrading_alerts) >= 1

    def test_milestone_trade_count(self):
        tracker = StrategyTracker()
        perf = tracker.register("strat_a")
        for i in range(15):
            perf.add_trade(make_trade(pnl=Decimal("50"), pnl_pct=5.0))
        engine = AlertEngine(tracker=tracker)
        alerts = engine.check_performance_alerts()
        milestone_alerts = [a for a in alerts if a["category"] == "milestone"]
        assert len(milestone_alerts) >= 1

    def test_check_all_aggregates(self):
        tracker = StrategyTracker()
        detector = DegradationDetector(tracker)
        tracker.register("strat_a")
        detector._degradation_log.append({
            "strategy_id": "strat_a",
            "from": "ACTIVE",
            "to": "WATCHLIST",
            "reasons": ["sharpe_fall"],
            "timestamp": "2025-01-01T00:00:00Z",
        })
        engine = AlertEngine(detector=detector)
        alerts = engine.check_all()
        assert len(alerts) >= 1

    def test_alert_filter_by_severity(self):
        engine = AlertEngine()
        engine._alerts = [
            {"severity": "info", "category": "test", "message": "a", "timestamp": "2025-01-01T00:00:00Z"},
            {"severity": "high", "category": "test", "message": "b", "timestamp": "2025-01-01T00:00:00Z"},
        ]
        filtered = engine.alerts(level=AlertSeverity.HIGH)
        assert len(filtered) == 1
        assert filtered[0]["severity"] == "high"

    def test_alert_filter_by_category(self):
        engine = AlertEngine()
        engine._alerts = [
            {"severity": "info", "category": "degradation", "message": "a", "timestamp": "2025-01-01T00:00:00Z"},
            {"severity": "info", "category": "regime", "message": "b", "timestamp": "2025-01-01T00:00:00Z"},
        ]
        filtered = engine.alerts(category=AlertCategory.DEGRADATION)
        assert len(filtered) == 1
        assert filtered[0]["category"] == "degradation"

    def test_clear_alerts(self):
        engine = AlertEngine()
        engine._alerts = [{"severity": "info", "category": "test", "message": "a", "timestamp": "2025-01-01T00:00:00Z"}]
        engine.clear_alerts()
        assert engine.alerts() == []

    def test_alert_count(self):
        engine = AlertEngine()
        engine._alerts = [
            {"severity": "info", "category": "degradation", "message": "a", "timestamp": "2025-01-01T00:00:00Z"},
            {"severity": "low", "category": "regime", "message": "b", "timestamp": "2025-01-01T00:00:00Z"},
            {"severity": "high", "category": "degradation", "message": "c", "timestamp": "2025-01-01T00:00:00Z"},
        ]
        counts = engine.alert_count()
        assert counts["degradation"] == 2
        assert counts["regime"] == 1

    def test_duplicate_degradation_suppressed(self):
        tracker = StrategyTracker()
        detector = DegradationDetector(tracker)
        tracker.register("strat_a")
        entry = {
            "strategy_id": "strat_a",
            "from": "ACTIVE",
            "to": "WATCHLIST",
            "reasons": ["sharpe_fall"],
            "timestamp": "2025-01-01T00:00:00Z",
        }
        detector._degradation_log.append(entry)
        detector._degradation_log.append(entry)
        engine = AlertEngine(detector=detector)
        alerts = engine.check_degradation_alerts()
        assert len(alerts) == 1

    def test_milestone_severity_mapping(self):
        assert AlertEngine._milestone_severity("x", 10) == AlertSeverity.LOW
        assert AlertEngine._milestone_severity("x", 50) == AlertSeverity.MEDIUM
        assert AlertEngine._milestone_severity("x", 100) == AlertSeverity.HIGH
        assert AlertEngine._milestone_severity("x", 1000) == AlertSeverity.CRITICAL

    def test_health_to_severity_mapping(self):
        assert AlertEngine._health_to_severity("WATCHLIST") == AlertSeverity.LOW
        assert AlertEngine._health_to_severity("DEGRADED") == AlertSeverity.HIGH
        assert AlertEngine._health_to_severity("RETIRED") == AlertSeverity.CRITICAL
        assert AlertEngine._health_to_severity("ACTIVE") == AlertSeverity.INFO

    def test_alert_limit(self):
        engine = AlertEngine()
        for i in range(10):
            engine._alerts.append({
                "severity": "info",
                "category": "test",
                "message": str(i),
                "timestamp": f"2025-01-01T00:{i:02d}:00Z",
            })
        assert len(engine.alerts(limit=3)) == 3

    def test_no_duplicate_performance_alerts(self):
        tracker = StrategyTracker()
        perf = tracker.register("strat_a")
        for i in range(10):
            pnl = Decimal("50") if i < 2 else Decimal("-100")
            perf.add_trade(make_trade(pnl=pnl, pnl_pct=3.0 if i < 2 else -10.0))
        engine = AlertEngine(tracker=tracker)
        first = engine.check_all()
        second = engine.check_all()
        degrading_first = sum(1 for a in first if a["category"] == "performance")
        degrading_second = sum(1 for a in second if a["category"] == "performance")
        assert degrading_second == 0
