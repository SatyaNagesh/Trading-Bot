"""Literature review integration — paper tracking and citation management."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from packages.core.logging import get_logger

logger = get_logger("literature")


@dataclass
class Paper:
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int = 0
    journal: str = ""
    doi: str = ""
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    strategies: list[str] = field(default_factory=list)
    url: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LiteratureManager:
    def __init__(self):
        self.papers: dict[str, Paper] = {}
        self._keyword_index: dict[str, list[str]] = {}

    def add_paper(self, paper: Paper) -> str:
        self.papers[paper.id] = paper
        for kw in paper.keywords:
            self._keyword_index.setdefault(kw.lower(), []).append(paper.id)
        logger.info("paper_added", title=paper.title)
        return paper.id

    def search_by_keyword(self, keyword: str) -> list[Paper]:
        ids = self._keyword_index.get(keyword.lower(), [])
        return [self.papers[pid] for pid in ids if pid in self.papers]

    def search_by_strategy(self, strategy_name: str) -> list[Paper]:
        return [p for p in self.papers.values() if strategy_name.lower() in [s.lower() for s in p.strategies]]

    def list_papers(self, limit: int = 20) -> list[dict]:
        return [
            {"id": p.id, "title": p.title, "year": p.year, "authors": p.authors}
            for p in list(self.papers.values())[:limit]
        ]


LITERATURE_SEEDS = [
    Paper(
        title="Momentum Strategies in Emerging Markets",
        authors=["Smith, J.", "Patel, R."],
        year=2023, keywords=["momentum", "emerging markets"],
        strategies=["sma_crossover"],
    ),
    Paper(
        title="Mean Reversion in High Frequency Data",
        authors=["Zhang, L."],
        year=2024, keywords=["mean-reversion", "high-frequency"],
        strategies=["rsi_reversal"],
    ),
    Paper(
        title="Machine Learning for Volatility Forecasting",
        authors=["Brown, A.", "Lee, K."],
        year=2024, keywords=["volatility", "ml"],
        strategies=[],
    ),
]
