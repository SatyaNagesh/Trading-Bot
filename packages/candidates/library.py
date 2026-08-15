"""Strategy library — persistent storage for validated candidates."""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from packages.strategies.runner import CandidateResult
from packages.strategies.templates import StrategyTemplate
from packages.review import StrategyReview


@dataclass
class LibraryEntry:
    template: StrategyTemplate
    result: CandidateResult
    review: StrategyReview | None = None
    stress_passed: bool = False
    composite_score: float = 0.0
    added_at: str = ""
    tags: list[str] = field(default_factory=list)


class StrategyLibrary:
    def __init__(self):
        self._entries: dict[str, LibraryEntry] = {}

    def add(
        self,
        template: StrategyTemplate,
        result: CandidateResult,
        review: StrategyReview | None = None,
        stress_passed: bool = False,
        composite_score: float = 0.0,
        tags: list[str] | None = None,
    ) -> str:
        entry = LibraryEntry(
            template=template,
            result=result,
            review=review,
            stress_passed=stress_passed,
            composite_score=composite_score,
            added_at=datetime.now(timezone.utc).isoformat(),
            tags=tags or [],
        )
        self._entries[template.id] = entry
        return template.id

    def get(self, strategy_id: str) -> LibraryEntry | None:
        return self._entries.get(strategy_id)

    def all(self) -> list[LibraryEntry]:
        return list(self._entries.values())

    def count(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    def summary(self) -> dict:
        entries = self.all()
        if not entries:
            return {"count": 0}
        scores = [e.composite_score for e in entries]
        return {
            "count": len(entries),
            "mean_score": round(sum(scores) / len(scores), 2) if scores else 0,
            "max_score": round(max(scores), 2) if scores else 0,
            "min_score": round(min(scores), 2) if scores else 0,
            "passed_stress": sum(1 for e in entries if e.stress_passed),
            "failed_stress": sum(1 for e in entries if not e.stress_passed),
        }

    def to_dicts(self) -> list[dict]:
        return [
            {
                "id": e.template.id,
                "name": e.template.name,
                "description": e.template.description,
                "score": e.composite_score,
                "sharpe": e.result.sharpe_ratio,
                "return": e.result.total_return,
                "max_drawdown": e.result.max_drawdown,
                "win_rate": e.result.win_rate,
                "profit_factor": e.result.profit_factor,
                "total_trades": e.result.total_trades,
                "stress_passed": e.stress_passed,
                "regime": e.review.expected_regime if e.review else "unknown",
                "risk": e.review.risk_profile if e.review else "unknown",
                "confidence": e.review.confidence_level if e.review else "unknown",
                "strengths": e.review.strengths if e.review else "",
                "weaknesses": e.review.weaknesses if e.review else "",
            }
            for e in self.all()
        ]
