"""Approval gates — pause/resume workflow for human-in-the-loop."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from packages.core.logging import get_logger

logger = get_logger("approval_gate")


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


@dataclass
class ApprovalRequest:
    id: str = field(default_factory=lambda: str(uuid4()))
    workflow_id: str = ""
    step_id: str = ""
    title: str = ""
    description: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewer: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None


class ApprovalManager:
    def __init__(self):
        self.requests: dict[str, ApprovalRequest] = {}

    def request_approval(self, req: ApprovalRequest) -> str:
        self.requests[req.id] = req
        logger.info("approval_requested", id=req.id, title=req.title)
        return req.id

    def approve(self, request_id: str, reviewer: str = "human") -> bool:
        req = self.requests.get(request_id)
        if not req or req.status != ApprovalStatus.PENDING:
            return False
        req.status = ApprovalStatus.APPROVED
        req.reviewer = reviewer
        req.decided_at = datetime.now(timezone.utc)
        logger.info("approval_granted", id=request_id)
        return True

    def reject(self, request_id: str, reviewer: str = "human") -> bool:
        req = self.requests.get(request_id)
        if not req or req.status != ApprovalStatus.PENDING:
            return False
        req.status = ApprovalStatus.REJECTED
        req.reviewer = reviewer
        req.decided_at = datetime.now(timezone.utc)
        logger.info("approval_rejected", id=request_id)
        return True

    def get_pending(self) -> list[ApprovalRequest]:
        return [r for r in self.requests.values() if r.status == ApprovalStatus.PENDING]

    def get(self, request_id: str) -> ApprovalRequest | None:
        return self.requests.get(request_id)
