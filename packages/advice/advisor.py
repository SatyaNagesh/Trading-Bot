"""Trade Advisor — scans adopted indicator strategies, proposes trades, and
governs human-in-the-loop approval.

Guarantees:
  * Nothing is ever executed without an explicit `approve()`.
  * Any pending proposal expires after TTL (default 300s) and is treated as a
    NO — the trade is skipped.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from packages.advice.models import TradeProposal
from packages.advice.strategies import Analysis, scan_symbol

DEFAULT_TTL_SECONDS = 300  # 5 minutes -> default NO
DEFAULT_TOP_N = 3
MIN_EXPECTED_RETURN_PCT = 0.5


class AdviceAdvisor:
    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        top_n: int = DEFAULT_TOP_N,
        min_return_pct: float = MIN_EXPECTED_RETURN_PCT,
        on_approve: Callable[[TradeProposal], dict[str, Any]] | None = None,
    ) -> None:
        self.ttl = ttl_seconds
        self.top_n = top_n
        self.min_return_pct = min_return_pct
        self._on_approve = on_approve
        self._proposals: dict[str, TradeProposal] = {}
        self._lock = time.time()  # keep import ordering; no rlock needed for CLI use

    # ── scan / propose ─────────────────────────────────────────────────────
    def scan(self, bars_map: dict[str, list]) -> list[TradeProposal]:
        """Run adopted strategies over every symbol; propose the top setups."""
        analyses: list[Analysis] = []
        for symbol, bars in bars_map.items():
            if not bars:
                continue
            bars[0].symbol = symbol  # normalize symbol tag on the bars
            for a in scan_symbol(bars):
                if a.expected_return_pct >= self.min_return_pct and a.risk_reward >= 1.0:
                    analyses.append(a)

        analyses.sort(key=lambda a: (-a.expected_return_pct, -a.confidence))
        created: list[TradeProposal] = []
        for a in analyses[: self.top_n]:
            p = self._proposal_from_analysis(a)
            self._proposals[p.id] = p
            created.append(p)
        return created

    def _proposal_from_analysis(self, a: Analysis) -> TradeProposal:
        now = datetime.now(timezone.utc)
        return TradeProposal(
            symbol=a.symbol,
            company_name=a.company_name,
            sector=a.sector,
            strategy=a.strategy,
            direction="long",
            current_price=a.current_price,
            expected_price=a.expected_price,
            stop_price=a.stop_price,
            expected_return_pct=a.expected_return_pct,
            downside_pct=a.downside_pct,
            confidence=a.confidence,
            risk_reward=a.risk_reward,
            reason=a.reason,
            indicators=a.indicators,
            created_at=now,
            expires_at=now + timedelta(seconds=self.ttl),
        )

    # ── query ──────────────────────────────────────────────────────────────
    def all_proposals(self) -> list[TradeProposal]:
        return list(self._proposals.values())

    def pending(self) -> list[TradeProposal]:
        return [p for p in self._proposals.values() if p.is_open]

    def get(self, proposal_id: str) -> TradeProposal | None:
        return self._proposals.get(proposal_id)

    # ── decision ───────────────────────────────────────────────────────────
    def approve(self, proposal_id: str, run: bool = True) -> dict[str, Any]:
        p = self.get(proposal_id)
        if p is None:
            return {"approved": False, "reason": "proposal not found", "status": "missing"}
        if p.expired:
            p.expire()
            return {"approved": False, "reason": "proposal expired (default NO)", "status": "expired"}
        if not p.is_open:
            return {"approved": False, "reason": f"already {p.status.value}", "status": p.status.value}
        p.approve()
        result = {"approved": True, "status": "approved", "proposal": p.summary()}
        if run and self._on_approve is not None:
            try:
                result["execution"] = self._on_approve(p)
            except Exception as e:  # surface execution errors without flipping state
                result["approved"] = False
                result["execution"] = {"error": str(e)}
        return result

    def reject(self, proposal_id: str) -> dict[str, Any]:
        p = self.get(proposal_id)
        if p is None or not p.is_open:
            return {"approved": False, "status": "not_pending"}
        p.reject()
        return {"approved": False, "status": "rejected", "proposal": p.summary()}

    def expire_old(self) -> int:
        """Expire any pending proposal past its deadline -> default NO."""
        n = 0
        for p in self.all_proposals():
            if p.is_open and p.expired:
                p.expire()
                n += 1
        return n