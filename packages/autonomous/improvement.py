"""Self-Improvement Loop — analyzes performance and recommends optimizations for strategies."""

from datetime import datetime, timezone
from typing import Any


class SelfImprovementLoop:
    def __init__(self):
        self._recommendations: list[dict[str, Any]] = []
        self._optimizations_applied = 0
        self._loop_count = 0

    def analyze(
        self,
        strategy_id: str,
        metrics: dict[str, Any],
        trades: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        self._loop_count += 1
        recs: list[dict[str, Any]] = []

        win_rate = metrics.get("win_rate", 0)
        sharpe = metrics.get("sharpe_ratio", 0)
        max_dd = metrics.get("max_drawdown", 0)
        total_trades = metrics.get("total_trades", len(trades))

        if total_trades >= self._min_trades_for_analysis():
            if win_rate < 35:
                recs.append(
                    self._make_recommendation(
                        strategy_id,
                        "entry_filter",
                        f"Win rate {win_rate:.1f}% below 35% — tighten entry conditions",
                        "medium",
                    )
                )
            if sharpe < 0.5:
                recs.append(
                    self._make_recommendation(
                        strategy_id,
                        "risk_management",
                        f"Sharpe {sharpe:.2f} below 0.5 — review stop-loss or position sizing",
                        "high",
                    )
                )
            if max_dd < -20:
                recs.append(
                    self._make_recommendation(
                        strategy_id,
                        "drawdown_control",
                        f"Max drawdown {max_dd:.1f}% exceeds 20% — add trailing stop or reduce exposure",
                        "high",
                    )
                )
            if win_rate >= 55 and sharpe >= 1.0:
                recs.append(
                    self._make_recommendation(
                        strategy_id,
                        "optimization",
                        "Strong performance — consider increasing position size or deploying to paper trading",
                        "low",
                    )
                )

        self._recommendations.extend(recs)
        return recs

    def _min_trades_for_analysis(self) -> int:
        return 10

    def _make_recommendation(
        self,
        strategy_id: str,
        category: str,
        suggestion: str,
        priority: str,
    ) -> dict[str, Any]:
        return {
            "id": f"rec-{len(self._recommendations) + 1}",
            "strategy_id": strategy_id,
            "category": category,
            "suggestion": suggestion,
            "priority": priority,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "applied": False,
        }

    def apply(self, rec_id: str) -> dict[str, Any] | None:
        for rec in self._recommendations:
            if rec["id"] == rec_id and not rec["applied"]:
                rec["applied"] = True
                rec["applied_at"] = datetime.now(timezone.utc).isoformat()
                self._optimizations_applied += 1
                return rec
        return None

    def get_recommendations(
        self,
        strategy_id: str | None = None,
        priority: str | None = None,
        only_unapplied: bool = False,
    ) -> list[dict[str, Any]]:
        results = list(self._recommendations)
        if strategy_id:
            results = [r for r in results if r["strategy_id"] == strategy_id]
        if priority:
            results = [r for r in results if r["priority"] == priority]
        if only_unapplied:
            results = [r for r in results if not r["applied"]]
        return sorted(results, key=lambda r: r["created_at"], reverse=True)

    def summary(self) -> dict[str, Any]:
        return {
            "loops_completed": self._loop_count,
            "total_recommendations": len(self._recommendations),
            "applied": self._optimizations_applied,
            "unapplied": len(self._recommendations) - self._optimizations_applied,
            "by_priority": {
                p: sum(1 for r in self._recommendations if r["priority"] == p)
                for p in set(r["priority"] for r in self._recommendations)
            },
        }
