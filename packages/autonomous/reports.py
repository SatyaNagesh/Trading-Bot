"""Auto Reporter — generates structured reports on autonomous system performance and strategy results."""

from datetime import datetime, timezone
from typing import Any


class AutoReporter:
    def __init__(self):
        self._reports: list[dict[str, Any]] = []

    def generate_report(
        self,
        report_type: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        report = {
            "id": f"report-{len(self._reports) + 1}",
            "type": report_type,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        self._reports.append(report)
        return report

    def cycle_report(
        self,
        cycle_id: str,
        cycle_number: int,
        orchestrator_status: dict[str, Any],
        trader_summary: dict[str, Any],
        lifecycle_summary: dict[str, Any],
        experiment_summary: dict[str, Any],
        knowledge_summary: dict[str, Any],
        improvement_summary: dict[str, Any],
        health_summary: dict[str, Any],
    ) -> dict[str, Any]:
        return self.generate_report(
            "cycle",
            {
                "cycle_id": cycle_id,
                "cycle_number": cycle_number,
                "orchestrator": orchestrator_status,
                "trader": trader_summary,
                "lifecycle": lifecycle_summary,
                "experiments": experiment_summary,
                "knowledge": knowledge_summary,
                "improvement": improvement_summary,
                "health": health_summary,
            },
        )

    def weekly_summary(self, cycles: list[dict[str, Any]]) -> dict[str, Any]:
        if not cycles:
            return self.generate_report("weekly", {"cycles": [], "summary": "No data"})

        total_trades = sum(
            c.get("data", {}).get("trader", {}).get("total_trades", 0)
            for c in cycles
            if c.get("type") == "cycle"
        )
        total_experiments = sum(
            c.get("data", {}).get("experiments", {}).get("total", 0)
            for c in cycles
            if c.get("type") == "cycle"
        )
        total_recommendations = sum(
            c.get("data", {}).get("improvement", {}).get("total_recommendations", 0)
            for c in cycles
            if c.get("type") == "cycle"
        )

        return self.generate_report(
            "weekly",
            {
                "cycles_analyzed": len(cycles),
                "total_trades": total_trades,
                "total_experiments": total_experiments,
                "total_recommendations": total_recommendations,
                "period_start": cycles[0]["generated_at"],
                "period_end": cycles[-1]["generated_at"],
            },
        )

    def get_reports(
        self,
        report_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        results = list(self._reports)
        if report_type:
            results = [r for r in results if r["type"] == report_type]
        return sorted(results, key=lambda r: r["generated_at"], reverse=True)[:limit]

    def summary(self) -> dict[str, Any]:
        return {
            "total_reports": len(self._reports),
            "by_type": {
                t: sum(1 for r in self._reports if r["type"] == t)
                for t in set(r["type"] for r in self._reports)
            },
        }
