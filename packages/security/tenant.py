"""Multi-tenancy — organizations, role-based access control, tenant isolation."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from packages.core.logging import get_logger

logger = get_logger("security")


class Role(Enum):
    ADMIN = "admin"
    STRATEGIST = "strategist"
    ANALYST = "analyst"
    VIEWER = "viewer"


ROLE_HIERARCHY = {
    Role.ADMIN: 100,
    Role.STRATEGIST: 80,
    Role.ANALYST: 50,
    Role.VIEWER: 10,
}


@dataclass
class Organization:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    settings: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True


@dataclass
class TenantUser:
    user_id: str = ""
    org_id: str = ""
    role: Role = Role.VIEWER


class TenantManager:
    def __init__(self):
        self.orgs: dict[str, Organization] = {}
        self.members: dict[str, list[TenantUser]] = {}

    def create_org(self, name: str, settings: dict[str, Any] | None = None) -> Organization:
        org = Organization(name=name, settings=settings or {})
        self.orgs[org.id] = org
        self.members[org.id] = []
        logger.info("org_created", name=name, id=org.id)
        return org

    def add_user(self, org_id: str, user_id: str, role: Role = Role.VIEWER) -> bool:
        if org_id not in self.orgs:
            return False
        user = TenantUser(user_id=user_id, org_id=org_id, role=role)
        self.members[org_id].append(user)
        logger.info("user_added_to_org", org=org_id, user=user_id, role=role.value)
        return True

    def check_access(self, user_id: str, org_id: str, required_role: Role) -> bool:
        members = self.members.get(org_id, [])
        for m in members:
            if m.user_id == user_id:
                return ROLE_HIERARCHY.get(m.role, 0) >= ROLE_HIERARCHY.get(required_role, 0)
        return False

    def get_org(self, org_id: str) -> Organization | None:
        return self.orgs.get(org_id)

    def list_orgs(self) -> list[Organization]:
        return list(self.orgs.values())
