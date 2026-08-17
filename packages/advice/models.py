"""Trade-proposal domain model — human-in-the-loop approval state."""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TradeProposal(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    symbol: str
    company_name: str = ""
    sector: str = ""
    strategy: str
    direction: str = "long"
    current_price: float
    expected_price: float
    stop_price: float
    expected_return_pct: float
    downside_pct: float
    confidence: float
    risk_reward: float
    reason: str
    indicators: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    decided_at: datetime | None = None
    status: ProposalStatus = ProposalStatus.PENDING

    @property
    def is_open(self) -> bool:
        return self.status == ProposalStatus.PENDING

    @property
    def expired(self) -> bool:
        return (
            self.status == ProposalStatus.PENDING
            and self.expires_at is not None
            and datetime.now(timezone.utc) >= self.expires_at
        )

    def approve(self) -> None:
        self.status = ProposalStatus.APPROVED
        self.decided_at = datetime.now(timezone.utc)

    def reject(self) -> None:
        self.status = ProposalStatus.REJECTED
        self.decided_at = datetime.now(timezone.utc)

    def expire(self) -> None:
        self.status = ProposalStatus.EXPIRED
        self.decided_at = datetime.now(timezone.utc)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "company_name": self.company_name,
            "sector": self.sector,
            "strategy": self.strategy,
            "direction": self.direction,
            "current_price": self.current_price,
            "expected_price": self.expected_price,
            "stop_price": self.stop_price,
            "expected_return_pct": self.expected_return_pct,
            "downside_pct": self.downside_pct,
            "confidence": self.confidence,
            "risk_reward": self.risk_reward,
            "reason": self.reason,
            "indicators": self.indicators,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status.value,
        }