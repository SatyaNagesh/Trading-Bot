"""Long-duration Observation Loop — simulation-based paper trading observation."""

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable
from uuid import uuid4

import numpy as np

from packages.analytics.engine import TradeAnalytics
from packages.analytics.regime_observer import RegimeObserver, MarketRegime
from packages.analytics.strategy_tracker import StrategyTracker
from packages.analytics.self_review import ReviewStore, TradeReview
from packages.analytics.degradation import DegradationDetector
from packages.analytics.reports import ReportGenerator
from packages.domain.models import Trade, Side, ExitReason


class SimulationConfig:
    def __init__(
        self,
        n_strategies: int = 3,
        trades_per_day: int = 10,
        observation_days: int = 60,
        start_price: float = 100.0,
        volatility: float = 0.015,
        regime: MarketRegime = MarketRegime.TRENDING,
        seed: int = 42,
    ):
        self.n_strategies = n_strategies
        self.trades_per_day = trades_per_day
        self.observation_days = observation_days
        self.start_price = start_price
        self.volatility = volatility
        self.regime = regime
        self.seed = seed


class StrategyProfile:
    def __init__(self, strategy_id: str, win_rate: float, avg_profit: float, avg_loss: float):
        self.strategy_id = strategy_id
        self.win_rate = win_rate
        self.avg_profit = avg_profit
        self.avg_loss = avg_loss
        self.degrade_after: int | None = None


class ObservationLoop:
    def __init__(
        self,
        tracker: StrategyTracker,
        review_store: ReviewStore,
        regime_observer: RegimeObserver,
        detector: DegradationDetector,
        config: SimulationConfig | None = None,
    ):
        self.tracker = tracker
        self.review_store = review_store
        self.regime_observer = regime_observer
        self.detector = detector
        self.config = config or SimulationConfig()
        self._rng = np.random.default_rng(self.config.seed)
        self._all_trades: list[Trade] = []
        self._day = 0
        self._current_price = float(self.config.start_price)
        self._report_gen = ReportGenerator(tracker, review_store, regime_observer, detector)

    def _simulate_price(self, day: int) -> float:
        prices = [float(self.config.start_price)]
        for d in range(1, day + 1):
            ret = self._rng.normal(0, self.config.volatility)
            if self.config.regime == MarketRegime.TRENDING:
                ret += 0.001
            elif self.config.regime == MarketRegime.MEAN_REVERTING:
                prev_log = math.log(prices[-1] / self.config.start_price)
                ret -= 0.1 * prev_log
            elif self.config.regime == MarketRegime.HIGH_VOLATILITY:
                ret = self._rng.normal(0, self.config.volatility * 2)
            elif self.config.regime == MarketRegime.CRISIS:
                ret = self._rng.normal(-0.005, self.config.volatility * 3)
            new_price = prices[-1] * (1 + ret)
            prices.append(max(new_price, 0.01))
        return prices[-1]

    def _simulate_strategy_profiles(self) -> list[StrategyProfile]:
        profiles = [
            StrategyProfile("momentum", 0.55, 2.0, 1.5),
            StrategyProfile("mean_reversion", 0.60, 1.5, 1.8),
            StrategyProfile("breakout", 0.50, 3.0, 2.0),
        ]
        profiles[2].degrade_after = int(self.config.observation_days * 0.6)
        return profiles[: self.config.n_strategies]

    def _simulate_trade(self, profile: StrategyProfile, day: int) -> Trade:
        entry_price = self._simulate_price(day)
        self._current_price = entry_price
        side = Side.BUY if self._rng.random() > 0.5 else Side.SELL
        quantity = self._rng.integers(1, 10)
        is_win = self._rng.random() < profile.win_rate
        day_offset = int(self._rng.integers(1, 5))
        exit_price = (
            entry_price * (1 + profile.avg_profit / 100)
            if is_win
            else entry_price * (1 - profile.avg_loss / 100)
        )

        if profile.degrade_after and day > profile.degrade_after:
            degrade_factor = 1 - (day - profile.degrade_after) * 0.02
            if is_win:
                exit_price = entry_price * (1 + profile.avg_profit * degrade_factor / 100)
                if self._rng.random() > 0.5:
                    exit_price = entry_price * (1 - profile.avg_loss / 100)
            else:
                exit_price = entry_price * (1 - profile.avg_loss * (2 - degrade_factor) / 100)

        pnl = (
            (exit_price - entry_price) * quantity
            if side == Side.BUY
            else (entry_price - exit_price) * quantity
        )
        pnl_pct = ((exit_price / entry_price) - 1) * 100
        if side == Side.SELL:
            pnl_pct = -pnl_pct

        entry_time = datetime(2025, 1, 1, 9, 30, 0, tzinfo=timezone.utc) + timedelta(days=day)
        exit_time = entry_time + timedelta(hours=day_offset)

        if is_win:
            exit_reason = ExitReason.TAKE_PROFIT.value
        else:
            exit_reason = ExitReason.STOP_LOSS.value

        if profile.degrade_after and day > profile.degrade_after + 10:
            exit_reason = (
                ExitReason.STOP_LOSS.value
                if self._rng.random() > 0.3
                else ExitReason.RISK_LIMIT.value
            )

        return Trade(
            id=str(uuid4()),
            strategy_id=profile.strategy_id,
            symbol="SIM",
            side=side,
            entry_price=Decimal(str(entry_price)),
            exit_price=Decimal(str(exit_price)),
            quantity=quantity,
            entry_time=entry_time,
            exit_time=exit_time,
            pnl=Decimal(str(round(pnl, 2))),
            pnl_pct=round(float(pnl_pct), 4),
            entry_reason="simulation",
            exit_reason=exit_reason,
        )

    def simulate_day(self) -> list[Trade]:
        profiles = self._simulate_strategy_profiles()
        day_trades = []
        for profile in profiles:
            n_trades = max(1, self._rng.poisson(self.config.trades_per_day) // len(profiles))
            for _ in range(n_trades):
                trade = self._simulate_trade(profile, self._day)
                day_trades.append(trade)
        return day_trades

    def observation_step(self, trades: list[Trade]) -> dict[str, Any]:
        for t in trades:
            self.tracker.record_trade(t)

        price = self._current_price
        self.regime_observer.observe([price], timestamp=datetime.now(timezone.utc))

        for t in trades:
            review = TradeReview(t).generate()
            self.review_store.record(review)

        regime = self.regime_observer.current_regime
        profiles = self._simulate_strategy_profiles()
        for p in profiles:
            self.detector.evaluate(p.strategy_id)

        step_analytics = TradeAnalytics(trades)
        return {
            "day": self._day,
            "n_trades": len(trades),
            "regime": regime.value,
            "price": price,
            "daily_pnl": round(sum(float(t.pnl) for t in trades), 2),
            "win_rate": step_analytics.win_rate,
        }

    def run(self, on_step: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        self._all_trades = []
        self._day = 0

        for d in range(self.config.observation_days):
            self._day = d + 1
            day_trades = self.simulate_day()
            self._all_trades.extend(day_trades)
            step_result = self.observation_step(day_trades)
            if on_step:
                on_step(step_result)

        all_analytics = TradeAnalytics(self._all_trades)
        final_price = self._current_price

        regimes = {}
        for p in self._simulate_strategy_profiles():
            sid = p.strategy_id
            perf = self.tracker.get(sid)
            regimes[sid] = {
                "health": self.detector.get_health(sid).value,
                "total_trades": len(perf.closed_trades) if perf else 0,
            }

        return {
            "total_days": self.config.observation_days,
            "total_trades": len(self._all_trades),
            "final_price": final_price,
            "total_pnl": round(sum(float(t.pnl) for t in self._all_trades), 2),
            "overall_summary": all_analytics.summary(),
            "strategy_regimes": regimes,
            "regime_counts": self.regime_observer.regime_counts(),
            "most_common_regime": self.regime_observer.most_common_regime(),
            "health_summary": self.detector.health_summary(),
        }

    def run_sync(self) -> dict[str, Any]:
        return self.run()

    def generate_report(self, report_type: str = "monthly") -> dict[str, Any]:
        if report_type == "daily":
            return self._report_gen.daily_report(self._all_trades)
        elif report_type == "weekly":
            return self._report_gen.weekly_report(self._all_trades)
        else:
            return self._report_gen.monthly_report(self._all_trades)
