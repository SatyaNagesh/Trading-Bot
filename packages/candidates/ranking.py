"""Strategy ranker — sort candidates by composite score."""

from dataclasses import dataclass

from packages.candidates.library import LibraryEntry


@dataclass
class RankedEntry:
    rank: int
    entry: LibraryEntry


class StrategyRanker:
    def __init__(self):
        self.score_weights = {
            "sharpe": 0.25,
            "return": 0.10,
            "win_rate": 0.10,
            "profit_factor": 0.15,
            "drawdown": 0.10,
            "trades": 0.05,
            "stress": 0.15,
            "confidence": 0.10,
        }

    def compute_score(self, entry: LibraryEntry) -> float:
        r = entry.result
        score = 0.0

        sharpe_score = min(max((r.sharpe_ratio + 1) / 3, 0), 1)
        score += sharpe_score * self.score_weights["sharpe"] * 100

        ret_score = min(max((r.total_return + 50) / 100, 0), 1)
        score += ret_score * self.score_weights["return"] * 100

        wr_score = r.win_rate / 100
        score += wr_score * self.score_weights["win_rate"] * 100

        pf_score = min(r.profit_factor / 5, 1)
        score += pf_score * self.score_weights["profit_factor"] * 100

        dd_score = 1 - min(abs(r.max_drawdown) / 50, 1)
        score += dd_score * self.score_weights["drawdown"] * 100

        trades_score = min(r.total_trades / 100, 1)
        score += trades_score * self.score_weights["trades"] * 100

        stress_score = 1.0 if entry.stress_passed else 0.0
        score += stress_score * self.score_weights["stress"] * 100

        if entry.review:
            conf_map = {"high": 1.0, "medium": 0.6, "low": 0.2}
            conf_score = conf_map.get(entry.review.confidence_level, 0.5)
            score += conf_score * self.score_weights["confidence"] * 100

        return round(score, 2)

    def rank(self, entries: list[LibraryEntry]) -> list[RankedEntry]:
        scored = []
        for e in entries:
            e.composite_score = self.compute_score(e)
            scored.append(e)

        scored.sort(key=lambda x: x.composite_score, reverse=True)

        return [RankedEntry(rank=i + 1, entry=e) for i, e in enumerate(scored)]

    def top_n(self, entries: list[LibraryEntry], n: int) -> list[RankedEntry]:
        ranked = self.rank(entries)
        return ranked[:n]
