"""Tests for Gate 3.5 — Candidate Discovery & Stress Testing."""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone

from packages.domain.models import Bar
from packages.strategies.templates import (
    StrategyTemplate, IndicatorTemplate, EntryRuleTemplate, ExitTemplate,
    sma, ema, rsi,
)
from packages.strategies.generator import SearchSpace, StrategyGenerator
from packages.strategies.runner import run_strategy, run_batch
from packages.stress.injector import StressInjector, StressConfig
from packages.stress.perturber import ParameterPerturber
from packages.review import generate_review, generate_batch_reviews
from packages.candidates.library import StrategyLibrary
from packages.candidates.ranking import StrategyRanker


@pytest.fixture
def sample_bars():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = []
    for i in range(400):
        price = 100 + i * 0.15 + (i % 20) * 0.5
        bars.append(Bar(
            timestamp=start + timedelta(days=i),
            open=Decimal(str(round(price, 2))),
            high=Decimal(str(round(price + 1.5, 2))),
            low=Decimal(str(round(price - 1.5, 2))),
            close=Decimal(str(round(price, 2))),
            volume=1_000_000,
            symbol="TEST",
        ))
    return bars


@pytest.fixture
def sma_cross_template():
    return StrategyTemplate(
        id="test_sma_10_30",
        name="SMA 10/30 Cross",
        indicators=[
            IndicatorTemplate(name="sma_10", factory="sma", params={"period": 10}),
            IndicatorTemplate(name="sma_30", factory="sma", params={"period": 30}),
        ],
        entry=EntryRuleTemplate(
            indicator_a="sma_10",
            operator="cross_above",
            indicator_b="sma_30",
        ),
        description="SMA 10/30 crossover",
    )


class TestStrategyTemplate:
    def test_build_indicator(self):
        fn = sma(period=10)
        import pandas as pd
        df = pd.DataFrame({"close": [1.0] * 20})
        result = fn(df)
        assert len(result) == 20
        assert not result.isna().all()

    def test_ema_indicator(self):
        fn = ema(period=14)
        import pandas as pd
        df = pd.DataFrame({"close": [float(i) for i in range(30)]})
        result = fn(df)
        assert len(result) == 30

    def test_rsi_indicator(self):
        fn = rsi(period=14)
        import pandas as pd
        df = pd.DataFrame({"close": [float(100 + (i % 10) * 2) for i in range(30)]})
        result = fn(df)
        assert len(result) == 30

    def test_strategy_template_creation(self, sma_cross_template):
        assert sma_cross_template.id == "test_sma_10_30"
        assert len(sma_cross_template.indicators) == 2
        assert sma_cross_template.entry.operator == "cross_above"


class TestStrategySearchSpace:
    def test_estimate_size(self):
        gen = StrategyGenerator()
        size = gen.estimate_size()
        assert size > 100

    def test_generate_candidates(self):
        gen = StrategyGenerator()
        candidates = gen.generate(max_candidates=50)
        assert len(candidates) == 50
        assert all(c.id.startswith("candidate_") for c in candidates)

    def test_generated_candidates_have_signal_fn(self):
        gen = StrategyGenerator()
        candidates = gen.generate(max_candidates=10)
        for c in candidates:
            fn = c.build_signal_fn()
            assert callable(fn)

    def test_generated_candidates_precompute(self, sample_bars):
        gen = StrategyGenerator()
        candidates = gen.generate(max_candidates=5)
        for c in candidates:
            df = c.precompute_indicators(sample_bars)
            assert len(df) == len(sample_bars)


class TestBatchBacktesting:
    @pytest.mark.asyncio
    async def test_run_single_strategy(self, sma_cross_template, sample_bars):
        result = await run_strategy(sma_cross_template, "TEST", sample_bars)
        assert result.strategy_id == "test_sma_10_30"
        assert hasattr(result, "sharpe_ratio")
        assert hasattr(result, "total_trades")

    @pytest.mark.asyncio
    async def test_run_batch(self, sample_bars):
        gen = StrategyGenerator()
        candidates = gen.generate(max_candidates=5)
        results = await run_batch(candidates, "TEST", sample_bars, max_concurrent=3)
        assert len(results) == 5
        for r in results:
            assert hasattr(r, "sharpe_ratio")

    @pytest.mark.asyncio
    async def test_runner_handles_empty_bars(self, sma_cross_template):
        result = await run_strategy(sma_cross_template, "TEST", [])
        assert result.total_trades == 0


class TestStressTesting:
    def test_stress_injector_basics(self, sample_bars):
        injected = StressInjector().inject(sample_bars)
        assert len(injected) <= len(sample_bars)
        assert len(injected) >= len(sample_bars) * 0.95

    def test_stress_high_noise(self, sample_bars):
        config = StressConfig(
            missing_candle_prob=0.1,
            data_gap_prob=0.1,
            volatility_shock_prob=0.5,
            volatility_shock_magnitude=0.1,
        )
        injected = StressInjector(config).inject(sample_bars)
        assert len(injected) < len(sample_bars)

    def test_stress_config_multiplier(self):
        injector = StressInjector()
        comm, slip = injector.stress_config(Decimal("0.001"), Decimal("0.0005"))
        assert comm == Decimal("0.002")
        assert slip == Decimal("0.001")

    def test_stress_no_mutation_of_original(self, sample_bars):
        original_count = len(sample_bars)
        _ = StressInjector().inject(sample_bars)
        assert len(sample_bars) == original_count

    @pytest.mark.asyncio
    async def test_parameter_perturber(self, sma_cross_template, sample_bars):
        perturber = ParameterPerturber(max_sharpe_change=2.0)
        results = await perturber.perturb(sma_cross_template, "TEST", sample_bars)
        assert len(results) > 0
        for r in results:
            assert hasattr(r, "pass_fail")


class TestAIReview:
    def test_generate_review(self, sma_cross_template):
        from packages.strategies.runner import CandidateResult
        result = CandidateResult(
            strategy_id="test_sma_10_30",
            strategy_name="SMA 10/30 Cross",
            sharpe_ratio=1.2,
            total_return=15.5,
            win_rate=55.0,
            profit_factor=1.8,
            total_trades=45,
            max_drawdown=-8.0,
        )
        review = generate_review(sma_cross_template, result)
        assert review.strategy_id == "test_sma_10_30"
        assert "sma" in review.explanation.lower()
        assert review.confidence_level in ("high", "medium", "low")
        assert len(review.explanation) > 20

    def test_generate_batch_reviews(self, sma_cross_template):
        from packages.strategies.runner import CandidateResult
        templates = [sma_cross_template]
        results = [CandidateResult(strategy_id="test_sma_10_30", strategy_name="SMA 10/30 Cross", sharpe_ratio=0.8)]
        reviews = generate_batch_reviews(templates, results)
        assert len(reviews) == 1
        assert reviews[0].strategy_id == "test_sma_10_30"


class TestStrategyLibrary:
    def test_add_and_retrieve(self, sma_cross_template):
        lib = StrategyLibrary()
        from packages.strategies.runner import CandidateResult
        result = CandidateResult(strategy_id="test_sma_10_30", strategy_name="SMA 10/30 Cross")
        lib.add(sma_cross_template, result, composite_score=75.0)
        entry = lib.get("test_sma_10_30")
        assert entry is not None
        assert entry.composite_score == 75.0

    def test_summary(self, sma_cross_template):
        lib = StrategyLibrary()
        from packages.strategies.runner import CandidateResult
        from copy import deepcopy
        t1 = deepcopy(sma_cross_template)
        t2 = deepcopy(sma_cross_template)
        t1.id = "s1"
        t2.id = "s2"
        r1 = CandidateResult(strategy_id="s1", strategy_name="S1", sharpe_ratio=1.5)
        r2 = CandidateResult(strategy_id="s2", strategy_name="S2", sharpe_ratio=0.5)
        lib.add(t1, r1, composite_score=80.0, stress_passed=True)
        lib.add(t2, r2, composite_score=40.0, stress_passed=False)
        s = lib.summary()
        assert s["count"] == 2
        assert s["passed_stress"] == 1
        assert s["failed_stress"] == 1

    def test_empty_library(self):
        lib = StrategyLibrary()
        assert lib.count() == 0
        assert lib.summary()["count"] == 0


class TestStrategyRanker:
    def test_rank_entries(self, sma_cross_template):
        lib = StrategyLibrary()
        from packages.strategies.runner import CandidateResult
        from copy import deepcopy
        t1 = deepcopy(sma_cross_template); t1.id = "s1"
        t2 = deepcopy(sma_cross_template); t2.id = "s2"
        r1 = CandidateResult(strategy_id="s1", strategy_name="S1", sharpe_ratio=2.0, total_return=30, win_rate=60, profit_factor=3.0, max_drawdown=-5, total_trades=100)
        r2 = CandidateResult(strategy_id="s2", strategy_name="S2", sharpe_ratio=0.3, total_return=-5, win_rate=40, profit_factor=0.8, max_drawdown=-25, total_trades=10)
        lib.add(t1, r1, composite_score=90.0, stress_passed=True)
        lib.add(t2, r2, composite_score=30.0, stress_passed=False)
        ranker = StrategyRanker()
        ranked = ranker.rank(lib.all())
        assert len(ranked) == 2
        assert ranked[0].entry.composite_score >= ranked[1].entry.composite_score

    def test_top_n(self, sma_cross_template):
        lib = StrategyLibrary()
        from packages.strategies.runner import CandidateResult
        from copy import deepcopy
        for i in range(10):
            t = deepcopy(sma_cross_template)
            t.id = f"s{i}"
            lib.add(t, CandidateResult(strategy_id=f"s{i}", strategy_name=f"S{i}", sharpe_ratio=1.0), composite_score=float(50 + i))
        ranker = StrategyRanker()
        top = ranker.top_n(lib.all(), 3)
        assert len(top) == 3
        assert top[0].rank == 1

    def test_empty_ranking(self):
        ranker = StrategyRanker()
        assert ranker.rank([]) == []
