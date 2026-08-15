"""AI Research Assistant — deterministic strategy analysis and recommendations."""

from typing import Any

from packages.analytics.strategy_tracker import StrategyTracker
from packages.analytics.degradation import DegradationDetector, StrategyHealth


class ResearchAssistant:
    def __init__(self, tracker: StrategyTracker, detector: DegradationDetector | None = None):
        self.tracker = tracker
        self.detector = detector

    def compare_strategies(self, strategy_ids: list[str]) -> dict[str, Any]:
        performances = {}
        for sid in strategy_ids:
            perf = self.tracker.get(sid)
            if perf:
                performances[sid] = perf.performance_summary()

        if not performances:
            return {"strategies": [], "comparison": "No data available"}

        rankings = []
        for sid, data in performances.items():
            lifetime = data["lifetime"]
            score = (
                lifetime.get("sharpe_ratio", 0) * 0.3
                + (lifetime.get("win_rate", 0) / 100) * 0.2
                + lifetime.get("profit_factor", 0) * 0.2
                - lifetime.get("max_drawdown", 0) * 0.2
                + data["stability_score"] * 0.1
            )
            rankings.append({"strategy_id": sid, "score": round(score, 4), "metrics": lifetime})

        rankings.sort(key=lambda x: x["score"], reverse=True)
        return {
            "strategies": rankings,
            "comparison": self._comparison_text(rankings),
            "best_strategy": rankings[0]["strategy_id"] if rankings else None,
        }

    def _comparison_text(self, rankings: list[dict]) -> str:
        if len(rankings) < 2:
            if rankings:
                return f"Only one strategy available: {rankings[0]['strategy_id']} with score {rankings[0]['score']:.2f}."
            return "No strategies to compare."
        best = rankings[0]
        second = rankings[1]
        diff_pct = ((best["score"] - second["score"]) / max(abs(second["score"]), 0.001)) * 100
        return (
            f"{best['strategy_id']} ranks highest with score {best['score']:.2f}, "
            f"{diff_pct:.1f}% ahead of {second['strategy_id']} ({second['score']:.2f}). "
            f"Across {len(rankings)} strategies evaluated."
        )

    def explain_performance(self, strategy_id: str) -> dict[str, Any]:
        perf = self.tracker.get(strategy_id)
        if not perf:
            return {"strategy_id": strategy_id, "error": "Strategy not found"}

        life = perf.lifetime()
        rec = perf.recent()
        explanations = []

        sharpe = life.get("sharpe_ratio", 0)
        if sharpe >= 2.0:
            explanations.append(
                f"Excellent Sharpe ratio ({sharpe:.2f}). Strategy has strong risk-adjusted returns."
            )
        elif sharpe >= 1.0:
            explanations.append(
                f"Good Sharpe ratio ({sharpe:.2f}). Strategy has acceptable risk-adjusted returns."
            )
        elif sharpe >= 0:
            explanations.append(
                f"Below-average Sharpe ratio ({sharpe:.2f}). Risk-adjusted returns need improvement."
            )
        else:
            explanations.append(
                f"Negative Sharpe ratio ({sharpe:.2f}). Strategy is destroying risk-adjusted value."
            )

        wr = life.get("win_rate", 0)
        if wr >= 60:
            explanations.append(f"High win rate ({wr:.1f}%). Strategy wins more than it loses.")
        elif wr >= 40:
            explanations.append(f"Moderate win rate ({wr:.1f}%). Win/loss balance is reasonable.")
        else:
            explanations.append(f"Low win rate ({wr:.1f}%). Consider adjusting entry criteria.")

        pf = life.get("profit_factor", 0)
        if pf >= 2.0:
            explanations.append(
                f"Strong profit factor ({pf:.2f}). Wins significantly outweigh losses."
            )
        elif pf >= 1.5:
            explanations.append(f"Good profit factor ({pf:.2f}). Profitable overall.")
        elif pf >= 1.0:
            explanations.append(
                f"Barely profitable (profit factor: {pf:.2f}). Marginally above breakeven."
            )
        else:
            explanations.append(f"Unprofitable (profit factor: {pf:.2f}). Losses exceed gains.")

        if life.get("total_trades", 0) >= 10:
            r_sharpe = rec.get("sharpe_ratio", 0)
            if abs(r_sharpe - sharpe) > 0.5:
                direction = "improving" if r_sharpe > sharpe else "declining"
                explanations.append(
                    f"Recent performance is {direction} ({r_sharpe:.2f} vs lifetime {sharpe:.2f})."
                )

        return {"strategy_id": strategy_id, "explanations": explanations, "metrics": life}

    def recommend_parameters(self, strategy_id: str) -> dict[str, Any]:
        perf = self.tracker.get(strategy_id)
        if not perf:
            return {"strategy_id": strategy_id, "error": "Strategy not found"}

        life = perf.lifetime()
        rec = perf.recent()
        recommendations = []

        if life.get("max_drawdown", 0) > 0.2:
            recommendations.append("Reduce position size to limit drawdown exposure.")
        if life.get("profit_factor", 0) < 1.2:
            recommendations.append("Consider tightening stop losses or taking profits earlier.")
        if life.get("win_rate", 0) < 35:
            recommendations.append(
                "Review entry conditions. Current entries may be too aggressive."
            )
        if rec.get("sharpe_ratio", 0) < life.get("sharpe_ratio", 0) * 0.7:
            recommendations.append(
                "Recent deterioration detected. Consider pausing strategy for revalidation."
            )
        if len(perf.closed_trades) < 10:
            recommendations.append(
                "Insufficient trades for reliable analysis. Continue collecting data."
            )

        return {"strategy_id": strategy_id, "recommendations": recommendations}

    def suggest_retirement(self, strategy_id: str) -> dict[str, Any]:
        if not self.detector:
            return {"strategy_id": strategy_id, "suggestion": "Degradation detector not available"}
        health, failures = self.detector.evaluate(strategy_id)
        result = {"strategy_id": strategy_id, "health": health.value, "failures": failures}
        if health in (StrategyHealth.RETIRED, StrategyHealth.DEGRADED):
            result["suggestion"] = (
                f"Strategy should be {'retired' if health == StrategyHealth.RETIRED else 'moved to watchlist'}."
            )
            result["urgency"] = "high" if health == StrategyHealth.RETIRED else "medium"
        elif health == StrategyHealth.WATCHLIST:
            result["suggestion"] = "Strategy needs monitoring. Early signs of degradation detected."
            result["urgency"] = "low"
        else:
            result["suggestion"] = (
                "No action needed. Strategy performing within acceptable parameters."
            )
            result["urgency"] = "none"
        return result

    def suggest_revalidation(self, strategy_id: str) -> dict[str, Any]:
        perf = self.tracker.get(strategy_id)
        if not perf:
            return {"strategy_id": strategy_id, "suggestion": "Strategy not found"}
        life = perf.lifetime()
        reasons = []
        if life.get("total_trades", 0) > 50:
            reasons.append(
                f"Strategy has {life['total_trades']} trades — sufficient data for revalidation"
            )
        if life.get("sharpe_ratio", 0) < 0.5:
            reasons.append(
                f"Sharpe ratio declining ({life['sharpe_ratio']:.2f}) — revalidation recommended"
            )
        if self.detector:
            health, _ = self.detector.evaluate(strategy_id)
            if health in (StrategyHealth.WATCHLIST, StrategyHealth.DEGRADED):
                reasons.append(f"Strategy health is {health.value} — revalidation needed")
        needs = len(reasons) >= 1
        return {
            "strategy_id": strategy_id,
            "recommends_revalidation": needs,
            "reasons": reasons,
        }
