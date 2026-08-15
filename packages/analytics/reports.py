"""Research Reports — daily, weekly, and monthly performance reports."""

from datetime import datetime, timedelta, timezone
from typing import Any

from packages.analytics.engine import TradeAnalytics
from packages.analytics.regime_observer import RegimeObserver
from packages.analytics.strategy_tracker import StrategyTracker
from packages.analytics.self_review import ReviewStore
from packages.analytics.degradation import DegradationDetector
from packages.domain.models import Trade


class ReportGenerator:
    def __init__(
        self,
        tracker: StrategyTracker,
        review_store: ReviewStore | None = None,
        regime_observer: RegimeObserver | None = None,
        degradation_detector: DegradationDetector | None = None,
    ):
        self.tracker = tracker
        self.review_store = review_store
        self.regime_observer = regime_observer
        self.degradation_detector = degradation_detector

    def daily_report(self, trades: list[Trade], date: datetime | None = None) -> dict[str, Any]:
        target = date or datetime.now(timezone.utc)
        day_start = target.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        day_trades = (
            [t for t in trades if day_start <= t.entry_time.replace(tzinfo=timezone.utc) < day_end]
            if trades
            else []
        )

        analytics = TradeAnalytics(day_trades) if day_trades else None
        return {
            "type": "daily",
            "date": day_start.date().isoformat(),
            "total_trades": len(day_trades),
            "summary": analytics.summary() if analytics else None,
            "top_strategies": self._top_strategies(limit=3),
        }

    def weekly_report(
        self, trades: list[Trade], end_date: datetime | None = None
    ) -> dict[str, Any]:
        target = end_date or datetime.now(timezone.utc)
        week_start = target - timedelta(days=7)
        week_trades = (
            [t for t in trades if week_start <= t.entry_time.replace(tzinfo=timezone.utc) <= target]
            if trades
            else []
        )

        analytics = TradeAnalytics(week_trades) if week_trades else None
        daily_pnl = self._daily_pnl_series(week_trades)
        return {
            "type": "weekly",
            "start_date": week_start.date().isoformat(),
            "end_date": target.date().isoformat(),
            "total_trades": len(week_trades),
            "summary": analytics.summary() if analytics else None,
            "daily_pnl": daily_pnl,
            "top_strategies": self._top_strategies(limit=5),
            "degradation_alerts": self._degradation_alerts(),
        }

    def monthly_report(
        self, trades: list[Trade], end_date: datetime | None = None
    ) -> dict[str, Any]:
        target = end_date or datetime.now(timezone.utc)
        month_start = target.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_trades = (
            [
                t
                for t in trades
                if month_start <= t.entry_time.replace(tzinfo=timezone.utc) <= target
            ]
            if trades
            else []
        )

        analytics = TradeAnalytics(month_trades) if month_trades else None
        weekly_pnl = self._weekly_pnl_series(month_trades)
        regime_analysis = self._regime_summary(month_trades)
        return {
            "type": "monthly",
            "month": month_start.strftime("%Y-%m"),
            "total_trades": len(month_trades),
            "summary": analytics.summary() if analytics else None,
            "weekly_pnl": weekly_pnl,
            "top_strategies": self._top_strategies(limit=10),
            "regime_analysis": regime_analysis,
            "degradation_report": self._full_degradation_report(),
            "review_count": self.review_store.count() if self.review_store else 0,
        }

    def _top_strategies(self, limit: int = 5) -> list[dict[str, Any]]:
        top = self.tracker.top_strategies(n=limit)
        return [
            {
                "strategy_id": sid,
                "score": score,
                "summary": self.tracker.get(sid).performance_summary()
                if self.tracker.get(sid)
                else {},
            }
            for sid, score in top
        ]

    def _degradation_alerts(self) -> list[dict[str, Any]]:
        if not self.degradation_detector:
            return []
        return [
            {"strategy_id": sid, "health": h.value, "failures": f}
            for sid, h, f in self.degradation_detector.get_degraded_strategies()
        ]

    def _regime_summary(self, trades: list[Trade]) -> dict[str, Any]:
        if not self.regime_observer:
            return {}
        counts = self.regime_observer.regime_counts()
        current = self.regime_observer.current_regime.value
        return {
            "current_regime": current,
            "regime_distribution": counts,
            "most_common": self.regime_observer.most_common_regime(),
        }

    def _daily_pnl_series(self, trades: list[Trade]) -> list[dict[str, Any]]:
        daily: dict[str, float] = {}
        for t in trades:
            day_key = t.entry_time.replace(tzinfo=timezone.utc).date().isoformat()
            daily[day_key] = daily.get(day_key, 0) + float(t.pnl)
        return [{"date": d, "pnl": round(pnl, 2)} for d, pnl in sorted(daily.items())]

    def _weekly_pnl_series(self, trades: list[Trade]) -> list[dict[str, Any]]:
        weekly: dict[str, float] = {}
        for t in trades:
            entry = t.entry_time.replace(tzinfo=timezone.utc)
            iso = entry.isocalendar()
            week_key = f"{iso[0]}-W{iso[1]:02d}"
            weekly[week_key] = weekly.get(week_key, 0) + float(t.pnl)
        return [{"week": w, "pnl": round(pnl, 2)} for w, pnl in sorted(weekly.items())]

    def _full_degradation_report(self) -> dict[str, Any]:
        if not self.degradation_detector:
            return {}
        summary = self.degradation_detector.health_summary()
        degraded = self.degradation_detector.get_degraded_strategies()
        return {
            "health_summary": summary,
            "degraded_strategies": [
                {"strategy_id": sid, "health": h.value, "failures": f} for sid, h, f in degraded
            ],
        }
