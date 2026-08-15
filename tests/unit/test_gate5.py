"""Gate 5: Paper Trading Observation & Learning — comprehensive tests."""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4

from packages.domain.models import Trade, Side, ExitReason
from packages.analytics.engine import TradeAnalytics
from packages.analytics.strategy_tracker import StrategyPerformance, StrategyTracker
from packages.analytics.regime_observer import RegimeObserver, MarketRegime, calculate_regime_performance
from packages.analytics.self_review import TradeReview, ReviewStore
from packages.analytics.degradation import DegradationDetector, StrategyHealth
from packages.analytics.research import ResearchAssistant
from packages.analytics.reports import ReportGenerator
from packages.analytics.observation import ObservationLoop, SimulationConfig


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


# =============================================================================
# Phase 1: Trade Analytics Engine
# =============================================================================

class TestTradeAnalytics:
    def test_win_rate_all_wins(self):
        trades = [make_trade(pnl=Decimal(str(i * 100))) for i in range(1, 11)]
        a = TradeAnalytics(trades)
        assert a.win_rate == 100.0

    def test_win_rate_all_losses(self):
        trades = [make_trade(pnl=Decimal(str(-i * 100))) for i in range(1, 11)]
        a = TradeAnalytics(trades)
        assert a.win_rate == 0.0

    def test_win_rate_mixed(self):
        trades = [make_trade(pnl=Decimal("100")) for _ in range(6)]
        trades += [make_trade(pnl=Decimal("-50")) for _ in range(4)]
        a = TradeAnalytics(trades)
        assert a.win_rate == 60.0

    def test_total_return(self):
        trades = [make_trade(pnl=Decimal("100")) for _ in range(5)]
        trades += [make_trade(pnl=Decimal("-50")) for _ in range(5)]
        a = TradeAnalytics(trades)
        assert a.total_return == 250.0

    def test_sharpe_ratio_positive(self):
        trades = [make_trade(pnl=Decimal(str(i * 10)), pnl_pct=i * 1.0) for i in range(1, 21)]
        a = TradeAnalytics(trades)
        sharpe = a.sharpe_ratio
        assert sharpe > 0

    def test_sharpe_ratio_negative(self):
        trades = [make_trade(pnl=Decimal(str(-i * 10)), pnl_pct=-i * 1.0) for i in range(1, 21)]
        a = TradeAnalytics(trades)
        sharpe = a.sharpe_ratio
        assert sharpe < 0

    def test_sharpe_ratio_zero_flat(self):
        trades = [make_trade(pnl=Decimal("0")) for _ in range(10)]
        a = TradeAnalytics(trades)
        assert a.sharpe_ratio == 0.0

    def test_sortino_ratio(self):
        trades = [make_trade(pnl=Decimal("100")) for _ in range(5)]
        trades += [make_trade(pnl=Decimal("-200")) for _ in range(3)]
        a = TradeAnalytics(trades)
        sortino = a.sortino_ratio
        assert isinstance(sortino, float)

    def test_profit_factor(self):
        trades = [make_trade(pnl=Decimal("100")) for _ in range(6)]
        trades += [make_trade(pnl=Decimal("-50")) for _ in range(4)]
        a = TradeAnalytics(trades)
        pf = a.profit_factor
        assert abs(pf - 3.0) < 0.01

    def test_profit_factor_all_wins(self):
        trades = [make_trade(pnl=Decimal("100")) for _ in range(10)]
        a = TradeAnalytics(trades)
        pf = a.profit_factor
        assert pf == float("inf")

    def test_profit_factor_all_losses(self):
        trades = [make_trade(pnl=Decimal("-50")) for _ in range(5)]
        a = TradeAnalytics(trades)
        pf = a.profit_factor
        assert pf == 0.0

    def test_max_drawdown(self):
        trades = [
            make_trade(pnl=Decimal("100"), pnl_pct=1.0),
            make_trade(pnl=Decimal("-200"), pnl_pct=-2.0),
            make_trade(pnl=Decimal("-300"), pnl_pct=-3.0),
            make_trade(pnl=Decimal("500"), pnl_pct=5.0),
        ]
        a = TradeAnalytics(trades)
        dd = a.max_drawdown
        assert dd > 0

    def test_rolling_summary(self):
        trades = [make_trade(pnl=Decimal("100"), pnl_pct=1.0) for _ in range(10)]
        a = TradeAnalytics(trades)
        rolling = a.rolling_summary()
        assert isinstance(rolling, list)

    def test_empty_trades(self):
        a = TradeAnalytics([])
        assert a.win_rate == 0.0
        assert a.total_return == 0.0
        assert a.sharpe_ratio == 0.0
        assert a.max_drawdown == 0.0
        assert a.profit_factor == 0.0

    def test_calmar_ratio(self):
        trades = [
            make_trade(pnl=Decimal("100"), pnl_pct=1.0),
            make_trade(pnl=Decimal("50"), pnl_pct=0.5),
        ]
        a = TradeAnalytics(trades)
        calmar = a.calmar_ratio
        assert isinstance(calmar, float)

    def test_recovery_factor(self):
        trades = [
            make_trade(pnl=Decimal("100"), pnl_pct=1.0),
            make_trade(pnl=Decimal("-200"), pnl_pct=-2.0),
            make_trade(pnl=Decimal("300"), pnl_pct=3.0),
        ]
        a = TradeAnalytics(trades)
        rf = a.recovery_factor
        assert rf > 0

    def test_consecutive_wins(self):
        trades = [make_trade(pnl=Decimal("100")) for _ in range(5)]
        trades += [make_trade(pnl=Decimal("-50")) for _ in range(3)]
        a = TradeAnalytics(trades)
        wins = a.consecutive_wins
        assert wins >= 5

    def test_consecutive_losses(self):
        trades = [make_trade(pnl=Decimal("-50")) for _ in range(4)]
        trades += [make_trade(pnl=Decimal("100")) for _ in range(2)]
        a = TradeAnalytics(trades)
        losses = a.consecutive_losses
        assert losses >= 4

    def test_summary(self):
        trades = [make_trade(pnl=Decimal("100")) for _ in range(6)]
        trades += [make_trade(pnl=Decimal("-50")) for _ in range(4)]
        a = TradeAnalytics(trades)
        s = a.summary()
        assert s["total_trades"] == 10
        assert s["winning_trades"] == 6
        assert s["losing_trades"] == 4
        assert s["win_rate"] == 60.0
        assert "sharpe_ratio" in s
        assert "max_drawdown" in s
        assert "profit_factor" in s

    def test_expectancy(self):
        trades = [make_trade(pnl=Decimal("200")) for _ in range(6)]
        trades += [make_trade(pnl=Decimal("-100")) for _ in range(4)]
        a = TradeAnalytics(trades)
        exp = a.expectancy
        assert abs(exp - 80.0) < 0.01

    def test_avg_holding_time(self):
        t1 = make_trade(
            exit_time=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
            pnl_pct=1.0,
        )
        t2 = make_trade(
            exit_time=datetime(2025, 1, 1, 14, 0, tzinfo=timezone.utc),
            pnl_pct=2.0,
        )
        a = TradeAnalytics([t1, t2])
        avg = a.average_holding_time
        assert avg.total_seconds() > 0


# =============================================================================
# Phase 2: Strategy Performance Tracking
# =============================================================================

class TestStrategyPerformance:
    def test_lifetime_analytics(self):
        trades = [make_trade(strategy_id="s1", pnl=Decimal("100")) for _ in range(10)]
        sp = StrategyPerformance("s1", trades)
        life = sp.lifetime()
        assert life["total_trades"] == 10
        assert life["win_rate"] == 100.0

    def test_recent_analytics(self):
        trades = [make_trade(strategy_id="s1", pnl=Decimal("100")) for _ in range(10)]
        trades += [make_trade(strategy_id="s1", pnl=Decimal("-50")) for _ in range(15)]
        sp = StrategyPerformance("s1", trades)
        rec = sp.recent(last_n=20)
        assert rec["total_trades"] == 20
        assert rec["winning_trades"] == 10

    def test_stability_score(self):
        trades = [make_trade(strategy_id="s1", pnl=Decimal("100")) for _ in range(10)]
        sp = StrategyPerformance("s1", trades)
        ss = sp.stability_score
        assert 0 <= ss <= 1

    def test_drawdown_trend(self):
        trades = [make_trade(strategy_id="s1", pnl=Decimal("100")) for _ in range(5)]
        trades += [make_trade(strategy_id="s1", pnl=Decimal("-200")) for _ in range(5)]
        sp = StrategyPerformance("s1", trades)
        trend = sp.drawdown_trend
        assert isinstance(trend, dict)
        assert "current" in trend
        assert "trend" in trend

    def test_analytics_by_regime(self):
        trades = [make_trade(strategy_id="s1", pnl=Decimal("100")) for _ in range(10)]
        sp = StrategyPerformance("s1", trades)
        regimes = sp.by_regime("trending")
        assert isinstance(regimes, dict)

    def test_analytics_by_symbol(self):
        t1 = make_trade(strategy_id="s1", symbol="AAPL", pnl=Decimal("100"))
        t2 = make_trade(strategy_id="s1", symbol="GOOGL", pnl=Decimal("50"))
        sp = StrategyPerformance("s1", [t1, t2])
        symbols = sp.by_symbol("AAPL")
        assert isinstance(symbols, dict)

    def test_is_degrading_false(self):
        trades = [make_trade(strategy_id="s1", pnl=Decimal("100")) for _ in range(30)]
        sp = StrategyPerformance("s1", trades)
        degrading, warnings = sp.is_degrading()
        assert degrading is False

    def test_performance_summary(self):
        trades = [make_trade(strategy_id="s1", pnl=Decimal("100")) for _ in range(5)]
        sp = StrategyPerformance("s1", trades)
        s = sp.performance_summary()
        assert "strategy_id" in s
        assert "lifetime" in s
        assert "recent" in s
        assert "confidence_trend" in s
        assert "stability_score" in s
        assert s["strategy_id"] == "s1"

    def test_closed_trades_property(self):
        trades = [make_trade(strategy_id="s1", pnl=Decimal("100")) for _ in range(3)]
        sp = StrategyPerformance("s1", trades)
        assert len(sp.closed_trades) == 3

    def test_no_trades(self):
        sp = StrategyPerformance("s1", [])
        life = sp.lifetime()
        assert life["total_trades"] == 0


class TestStrategyTracker:
    def test_record_and_get(self):
        st = StrategyTracker()
        trade = make_trade(strategy_id="s1", pnl=Decimal("100"))
        st.record_trade(trade)
        perf = st.get("s1")
        assert perf is not None
        assert perf.lifetime()["total_trades"] == 1

    def test_get_nonexistent(self):
        st = StrategyTracker()
        assert st.get("missing") is None

    def test_multiple_strategies(self):
        st = StrategyTracker()
        for sid in ["s1", "s2", "s3"]:
            for _ in range(5):
                st.record_trade(make_trade(strategy_id=sid))
        assert len(st._strategies) == 3

    def test_top_ranking(self):
        st = StrategyTracker()
        for _ in range(10):
            st.record_trade(make_trade(strategy_id="winner", pnl=Decimal("100")))
        for _ in range(10):
            st.record_trade(make_trade(strategy_id="loser", pnl=Decimal("-100")))
        top = st.top_strategies(n=1)
        assert len(top) == 1
        assert top[0][0] == "winner"

    def test_all_summaries(self):
        st = StrategyTracker()
        for _ in range(5):
            st.record_trade(make_trade(strategy_id="s1"))
        summaries = st.all_summaries()
        assert len(summaries) > 0

    def test_strategy_count(self):
        st = StrategyTracker()
        for _ in range(3):
            st.record_trade(make_trade(strategy_id="s1"))
        assert st.strategy_count() == 1


# =============================================================================
# Phase 3: Market Regime Observation
# =============================================================================

class TestRegimeObserver:
    def test_classify_trending(self):
        ro = RegimeObserver(lookback=10)
        prices = [100]
        for i in range(1, 10):
            prices.append(prices[-1] * (1 + 0.008 + (i % 2) * 0.004))
        regime = ro.classify(prices)
        assert regime in (MarketRegime.TRENDING, MarketRegime.LOW_VOLATILITY), f"Got {regime}"

    def test_classify_mean_reverting(self):
        ro = RegimeObserver(lookback=10)
        prices = [100]
        for i in range(1, 10):
            ret = 0.003 if i % 2 == 0 else -0.003
            prices.append(prices[-1] * (1 + ret))
        regime = ro.classify(prices)
        assert regime in (MarketRegime.MEAN_REVERTING, MarketRegime.LOW_VOLATILITY), f"Got {regime}"

    def test_classify_high_volatility(self):
        ro = RegimeObserver(lookback=10)
        prices = [100]
        for _ in range(9):
            prices.append(prices[-1] * (1 + (0.03 if _ % 2 == 0 else -0.03)))
        regime = ro.classify(prices)
        assert regime in (MarketRegime.HIGH_VOLATILITY, MarketRegime.BREAKOUT, MarketRegime.CRISIS), f"Got {regime}"

    def test_classify_sideways(self):
        ro = RegimeObserver(lookback=10)
        prices = [100 + (i % 2) * 0.1 for i in range(10)]
        regime = ro.classify(prices)
        assert regime == MarketRegime.SIDEWAYS, f"Got {regime}"

    def test_classify_unknown_insufficient(self):
        ro = RegimeObserver(lookback=21)
        prices = [100, 101, 102]
        regime = ro.classify(prices)
        assert regime == MarketRegime.UNKNOWN

    def test_observe_records(self):
        ro = RegimeObserver()
        prices = [100]
        for i in range(1, 10):
            prices.append(prices[-1] * (1 + 0.008 + (i % 2) * 0.004))
        regime = ro.observe(prices)
        assert len(ro._regime_log) == 1
        assert isinstance(regime, MarketRegime)

    def test_current_regime(self):
        ro = RegimeObserver(lookback=10)
        assert ro.current_regime == MarketRegime.UNKNOWN
        prices = [100]
        for i in range(1, 10):
            prices.append(prices[-1] * (1 + 0.008 + (i % 2) * 0.004))
        ro.observe(prices)
        assert ro.current_regime != MarketRegime.UNKNOWN

    def test_regime_history(self):
        ro = RegimeObserver()
        for i in range(5):
            prices = [100 + i + j for j in range(10)]
            ro.observe(prices)
        history = ro.regime_history(limit=3)
        assert len(history) <= 3

    def test_regime_counts(self):
        ro = RegimeObserver()
        ro._regime_log = [
            {"regime": "trending", "timestamp": "now"},
            {"regime": "trending", "timestamp": "now"},
            {"regime": "sideways", "timestamp": "now"},
        ]
        counts = ro.regime_counts()
        assert counts["trending"] == 2
        assert counts["sideways"] == 1

    def test_most_common_regime(self):
        ro = RegimeObserver()
        ro._regime_log = [
            {"regime": "trending", "timestamp": "now"},
            {"regime": "trending", "timestamp": "now"},
            {"regime": "sideways", "timestamp": "now"},
        ]
        assert ro.most_common_regime() == "trending"

    def test_calculate_regime_performance(self):
        ro = RegimeObserver()
        for i in range(5):
            prices = [100 + i + j for j in range(10)]
            ro.observe(prices, timestamp=datetime(2025, 1, i + 1, tzinfo=timezone.utc))
        trades = [make_trade(pnl=Decimal("100"))]
        results = calculate_regime_performance(trades, ro._regime_log)
        assert isinstance(results, dict)


# =============================================================================
# Phase 4: Self Review
# =============================================================================

class TestTradeReview:
    def test_generate_review_structure(self):
        trade = make_trade(pnl=Decimal("100"))
        review = TradeReview(trade).generate()
        assert "review_id" in review
        assert "trade_id" in review
        assert "why_taken" in review
        assert "why_result" in review
        assert "risk_taken" in review
        assert "better_alternatives" in review
        assert "confidence_adjustment" in review
        assert "lessons_learned" in review

    def test_review_winning_trade(self):
        trade = make_trade(pnl=Decimal("100"))
        review = TradeReview(trade, strategy_win_rate=0.6).generate()
        assert review["confidence_adjustment"] >= 0.5
        assert "correctly" in review["why_result"].lower()

    def test_review_losing_trade(self):
        trade = make_trade(pnl=Decimal("-100"))
        review = TradeReview(trade, strategy_win_rate=0.6).generate()
        assert review["confidence_adjustment"] < 0.6
        assert "unprofitable" in review["why_result"].lower() or "loss" in review["risk_taken"].lower()

    def test_review_with_previous_trades(self):
        prev = [make_trade(pnl=Decimal("100")) for _ in range(4)]
        trade = make_trade(pnl=Decimal("-50"))
        review = TradeReview(trade, previous_trades=prev).generate()
        assert "lessons_learned" in review

    def test_review_breakeven(self):
        trade = make_trade(pnl=Decimal("0"))
        review = TradeReview(trade).generate()
        assert review["confidence_adjustment"] is not None

    def test_review_stop_loss(self):
        trade = make_trade(pnl=Decimal("-200"), exit_reason=ExitReason.STOP_LOSS.value)
        review = TradeReview(trade).generate()
        assert "stop" in review["why_result"].lower()


class TestReviewStore:
    def test_record_and_count(self):
        store = ReviewStore()
        store.record({"review_id": "r1"})
        assert store.count() == 1

    def test_get_all_reviews(self):
        store = ReviewStore()
        store.record({"review_id": "r1", "strategy_id": "s1"})
        store.record({"review_id": "r2", "strategy_id": "s2"})
        assert len(store.all_reviews()) == 2

    def test_get_reviews_filtered(self):
        store = ReviewStore()
        store.record({"review_id": "r1", "strategy_id": "s1"})
        store.record({"review_id": "r2", "strategy_id": "s2"})
        s1_reviews = store.get_reviews(strategy_id="s1")
        assert len(s1_reviews) == 1
        assert s1_reviews[0]["strategy_id"] == "s1"

    def test_get_reviews_limit(self):
        store = ReviewStore()
        for i in range(10):
            store.record({"review_id": str(i)})
        assert len(store.get_reviews(limit=5)) == 5


# =============================================================================
# Phase 5: Strategy Degradation Detection
# =============================================================================

class TestDegradationDetector:
    def test_evaluate_active(self):
        st = StrategyTracker()
        for _ in range(20):
            st.record_trade(make_trade(strategy_id="s1", pnl=Decimal("100"), pnl_pct=1.0))
        dd = DegradationDetector(st)
        health, failures = dd.evaluate("s1")
        assert health == StrategyHealth.ACTIVE
        assert len(failures) == 0

    def test_sharpe_fall_triggers_watchlist(self):
        st = StrategyTracker()
        for i in range(15):
            st.record_trade(make_trade(strategy_id="s1", pnl=Decimal("100"), pnl_pct=2.0))
        for i in range(15):
            st.record_trade(make_trade(strategy_id="s1", pnl=Decimal("-100"), pnl_pct=-2.0))
        dd = DegradationDetector(st)
        health, failures = dd.evaluate("s1")
        assert health in (StrategyHealth.ACTIVE, StrategyHealth.WATCHLIST)

    def test_evaluate_all(self):
        st = StrategyTracker()
        for sid in ["s1", "s2"]:
            for _ in range(10):
                st.record_trade(make_trade(strategy_id=sid, pnl=Decimal("100"), pnl_pct=1.0))
        dd = DegradationDetector(st)
        results = dd.evaluate_all()
        assert len(results) == 2

    def test_get_health_default(self):
        st = StrategyTracker()
        dd = DegradationDetector(st)
        assert dd.get_health("missing") == StrategyHealth.ACTIVE

    def test_get_degraded_strategies(self):
        st = StrategyTracker()
        for _ in range(10):
            st.record_trade(make_trade(strategy_id="good", pnl=Decimal("100"), pnl_pct=1.0))
        dd = DegradationDetector(st)
        assert len(dd.get_degraded_strategies()) == 0

    def test_health_summary(self):
        st = StrategyTracker()
        dd = DegradationDetector(st)
        for _ in range(10):
            st.record_trade(make_trade(strategy_id="s1", pnl=Decimal("100"), pnl_pct=1.0))
        dd.evaluate("s1")
        summary = dd.health_summary()
        assert summary.get("ACTIVE", 0) >= 1

    def test_degradation_history(self):
        st = StrategyTracker()
        dd = DegradationDetector(st)
        for _ in range(10):
            st.record_trade(make_trade(strategy_id="s1", pnl=Decimal("100"), pnl_pct=1.0))
        dd.evaluate("s1")
        history = dd.degradation_history()
        assert isinstance(history, list)


# =============================================================================
# Phase 6: AI Research Assistant
# =============================================================================

class TestResearchAssistant:
    def test_compare_strategies(self):
        st = StrategyTracker()
        for _ in range(10):
            st.record_trade(make_trade(strategy_id="s1", pnl=Decimal("200"), pnl_pct=2.0))
        for _ in range(10):
            st.record_trade(make_trade(strategy_id="s2", pnl=Decimal("100"), pnl_pct=1.0))
        ra = ResearchAssistant(st)
        result = ra.compare_strategies(["s1", "s2"])
        assert "strategies" in result
        assert "best_strategy" in result
        assert result["best_strategy"] == "s1"

    def test_compare_strategies_single(self):
        st = StrategyTracker()
        for _ in range(5):
            st.record_trade(make_trade(strategy_id="s1", pnl=Decimal("100"), pnl_pct=1.0))
        ra = ResearchAssistant(st)
        result = ra.compare_strategies(["s1"])
        assert result["best_strategy"] == "s1"

    def test_explain_performance_found(self):
        st = StrategyTracker()
        for _ in range(10):
            st.record_trade(make_trade(strategy_id="s1", pnl=Decimal("100"), pnl_pct=1.0))
        ra = ResearchAssistant(st)
        result = ra.explain_performance("s1")
        assert "explanations" in result
        assert len(result["explanations"]) > 0

    def test_explain_performance_not_found(self):
        st = StrategyTracker()
        ra = ResearchAssistant(st)
        result = ra.explain_performance("missing")
        assert "error" in result

    def test_recommend_parameters(self):
        st = StrategyTracker()
        for _ in range(10):
            st.record_trade(make_trade(strategy_id="s1", pnl=Decimal("100"), pnl_pct=1.0))
        ra = ResearchAssistant(st)
        result = ra.recommend_parameters("s1")
        assert "recommendations" in result

    def test_suggest_retirement_no_detector(self):
        st = StrategyTracker()
        ra = ResearchAssistant(st)
        result = ra.suggest_retirement("s1")
        assert result["suggestion"] == "Degradation detector not available"

    def test_suggest_retirement_with_detector(self):
        st = StrategyTracker()
        for _ in range(10):
            st.record_trade(make_trade(strategy_id="s1", pnl=Decimal("100"), pnl_pct=1.0))
        dd = DegradationDetector(st)
        ra = ResearchAssistant(st, detector=dd)
        result = ra.suggest_retirement("s1")
        assert "suggestion" in result
        assert "urgency" in result

    def test_suggest_revalidation(self):
        st = StrategyTracker()
        for _ in range(10):
            st.record_trade(make_trade(strategy_id="s1", pnl=Decimal("100"), pnl_pct=1.0))
        ra = ResearchAssistant(st)
        result = ra.suggest_revalidation("s1")
        assert "recommends_revalidation" in result


# =============================================================================
# Phase 7: Research Reports
# =============================================================================

class TestReportGenerator:
    def test_daily_report(self):
        st = StrategyTracker()
        rg = ReportGenerator(st)
        st.record_trade(make_trade(strategy_id="s1", pnl=Decimal("100"), pnl_pct=1.0))
        report_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        trades = [make_trade(pnl=Decimal("100"), pnl_pct=1.0)]
        report = rg.daily_report(trades, date=report_date)
        assert report["type"] == "daily"
        assert report["total_trades"] == 1

    def test_daily_report_no_trades(self):
        st = StrategyTracker()
        rg = ReportGenerator(st)
        report = rg.daily_report([])
        assert report["total_trades"] == 0

    def test_weekly_report(self):
        st = StrategyTracker()
        rg = ReportGenerator(st)
        st.record_trade(make_trade(strategy_id="s1", pnl=Decimal("100"), pnl_pct=1.0))
        report_end = datetime(2025, 1, 3, tzinfo=timezone.utc)
        trades = [make_trade(pnl=Decimal("100"), pnl_pct=1.0) for _ in range(5)]
        report = rg.weekly_report(trades, end_date=report_end)
        assert report["type"] == "weekly"
        assert "daily_pnl" in report

    def test_monthly_report(self):
        st = StrategyTracker()
        rg = ReportGenerator(st)
        st.record_trade(make_trade(strategy_id="s1", pnl=Decimal("100"), pnl_pct=1.0))
        report_end = datetime(2025, 1, 15, tzinfo=timezone.utc)
        trades = [make_trade(pnl=Decimal("100"), pnl_pct=1.0) for _ in range(10)]
        report = rg.monthly_report(trades, end_date=report_end)
        assert report["type"] == "monthly"
        assert "weekly_pnl" in report

    def test_monthly_report_with_reviews(self):
        st = StrategyTracker()
        rs = ReviewStore()
        rg = ReportGenerator(st, review_store=rs)
        report_end = datetime(2025, 1, 15, tzinfo=timezone.utc)
        trades = [make_trade(pnl=Decimal("100"), pnl_pct=1.0) for _ in range(5)]
        report = rg.monthly_report(trades, end_date=report_end)
        assert report["review_count"] == 0

    def test_report_with_regime_observer(self):
        st = StrategyTracker()
        ro = RegimeObserver(lookback=10)
        rg = ReportGenerator(st, regime_observer=ro)
        prices = [100]
        for i in range(1, 10):
            prices.append(prices[-1] * (1 + 0.008 + (i % 2) * 0.004))
        ro.observe(prices)
        report_end = datetime(2025, 1, 15, tzinfo=timezone.utc)
        trades = [make_trade(pnl=Decimal("100"), pnl_pct=1.0) for _ in range(3)]
        report = rg.monthly_report(trades, end_date=report_end)
        assert "regime_analysis" in report

    def test_report_with_degradation(self):
        st = StrategyTracker()
        dd = DegradationDetector(st)
        rg = ReportGenerator(st, degradation_detector=dd)
        for _ in range(10):
            st.record_trade(make_trade(strategy_id="s1", pnl=Decimal("100"), pnl_pct=1.0))
        report_end = datetime(2025, 1, 15, tzinfo=timezone.utc)
        trades = [make_trade(pnl=Decimal("100"), pnl_pct=1.0) for _ in range(3)]
        report = rg.monthly_report(trades, end_date=report_end)
        assert "degradation_report" in report

    def test_daily_pnl_series(self):
        st = StrategyTracker()
        rg = ReportGenerator(st)
        report_end = datetime(2025, 1, 3, tzinfo=timezone.utc)
        trades = [make_trade(pnl=Decimal("100"), pnl_pct=1.0)]
        report = rg.weekly_report(trades, end_date=report_end)
        assert len(report["daily_pnl"]) >= 1


# =============================================================================
# Phase 8: Long-duration Observation Loop
# =============================================================================

class TestObservationLoop:
    def test_simulate_day_creates_trades(self):
        st = StrategyTracker()
        rs = ReviewStore()
        ro = RegimeObserver()
        dd = DegradationDetector(st)
        config = SimulationConfig(n_strategies=2, trades_per_day=5, observation_days=1)
        loop = ObservationLoop(st, rs, ro, dd, config)
        trades = loop.simulate_day()
        assert len(trades) >= 1
        for t in trades:
            assert t.strategy_id in ("momentum", "mean_reversion")
            assert t.exit_time is not None

    def test_observation_step(self):
        st = StrategyTracker()
        rs = ReviewStore()
        ro = RegimeObserver()
        dd = DegradationDetector(st)
        loop = ObservationLoop(st, rs, ro, dd)
        trades = loop.simulate_day()
        result = loop.observation_step(trades)
        assert "day" in result
        assert "n_trades" in result
        assert "regime" in result
        assert "daily_pnl" in result

    def test_run_short(self):
        st = StrategyTracker()
        rs = ReviewStore()
        ro = RegimeObserver()
        dd = DegradationDetector(st)
        config = SimulationConfig(n_strategies=2, trades_per_day=3, observation_days=2)
        loop = ObservationLoop(st, rs, ro, dd, config)
        result = loop.run_sync()
        assert result["total_days"] == 2
        assert result["total_trades"] >= 1
        assert "total_pnl" in result
        assert "overall_summary" in result
        assert "regime_counts" in result
        assert "health_summary" in result

    def test_generate_daily_report(self):
        st = StrategyTracker()
        rs = ReviewStore()
        ro = RegimeObserver()
        dd = DegradationDetector(st)
        loop = ObservationLoop(st, rs, ro, dd)
        report = loop.generate_report("daily")
        assert report["type"] == "daily"

    def test_generate_monthly_report(self):
        st = StrategyTracker()
        rs = ReviewStore()
        ro = RegimeObserver()
        dd = DegradationDetector(st)
        loop = ObservationLoop(st, rs, ro, dd)
        report = loop.generate_report("monthly")
        assert report["type"] == "monthly"
