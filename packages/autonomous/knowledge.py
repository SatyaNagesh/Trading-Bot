"""Knowledge Evolver — extracts insights from paper-trading results and experiment outcomes."""

from datetime import datetime, timezone
from typing import Any


class KnowledgeEvolver:
    def __init__(self, knowledge_graph: Any | None = None):
        self.knowledge_graph = knowledge_graph
        self._insights: list[dict[str, Any]] = []
        self._patterns: list[dict[str, Any]] = []
        self._learning_cycles = 0

    def record_insight(
        self,
        category: str,
        title: str,
        description: str,
        source: str,
        metrics: dict[str, Any] | None = None,
    ) -> str:
        insight_id = f"insight-{len(self._insights) + 1}"
        self._insights.append(
            {
                "id": insight_id,
                "category": category,
                "title": title,
                "description": description,
                "source": source,
                "metrics": metrics or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        if self.knowledge_graph and hasattr(self.knowledge_graph, "add_node"):
            try:
                self.knowledge_graph.add_node(
                    node_id=insight_id,
                    labels=["Insight", category],
                    properties={
                        "title": title,
                        "description": description,
                        "source": source,
                        "metrics": str(metrics),
                    },
                )
            except Exception:
                pass

        return insight_id

    def record_pattern(
        self,
        pattern_type: str,
        description: str,
        conditions: dict[str, Any],
        outcome: str,
    ) -> str:
        pattern_id = f"pattern-{len(self._patterns) + 1}"
        self._patterns.append(
            {
                "id": pattern_id,
                "type": pattern_type,
                "description": description,
                "conditions": conditions,
                "outcome": outcome,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return pattern_id

    def learn_from_trades(
        self,
        trades: list[dict[str, Any]],
        metrics: dict[str, Any],
    ) -> list[str]:
        self._learning_cycles += 1
        insight_ids = []

        wr = metrics.get("win_rate", 0)
        if wr < 30:
            ids = self.record_insight(
                category="performance",
                title="Low win rate detected",
                description=f"Win rate {wr:.1f}% suggests strategy filter improvements needed",
                source="knowledge_evolver",
                metrics={"win_rate": wr, "cycle": self._learning_cycles},
            )
            insight_ids.append(ids)

        sharpe = metrics.get("sharpe_ratio", 0)
        if sharpe < 0.5 and metrics.get("total_trades", 0) > 20:
            ids = self.record_insight(
                category="risk",
                title="Low Sharpe ratio",
                description=f"Sharpe {sharpe:.2f} indicates poor risk-adjusted returns",
                source="knowledge_evolver",
                metrics={"sharpe": sharpe, "total_trades": metrics.get("total_trades", 0)},
            )
            insight_ids.append(ids)

        return insight_ids

    def get_insights(
        self,
        category: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        results = list(self._insights)
        if category:
            results = [i for i in results if i["category"] == category]
        return sorted(results, key=lambda i: i["created_at"], reverse=True)[:limit]

    def get_patterns(self, pattern_type: str | None = None) -> list[dict[str, Any]]:
        if pattern_type:
            return [p for p in self._patterns if p["type"] == pattern_type]
        return list(self._patterns)

    def summary(self) -> dict[str, Any]:
        return {
            "total_insights": len(self._insights),
            "total_patterns": len(self._patterns),
            "learning_cycles": self._learning_cycles,
            "by_category": {
                cat: sum(1 for i in self._insights if i["category"] == cat)
                for cat in set(i["category"] for i in self._insights)
            },
        }
