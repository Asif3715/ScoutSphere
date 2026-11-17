import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthContext:
    """The authenticated caller. Built by the backend only; the AI agent receives the same
    object, so it can never hold more privilege than the user it acts for."""

    user_id: uuid.UUID
    platform_role: str | None = None
    organization_id: uuid.UUID | None = None
    org_role: str | None = None
    permissions: frozenset[str] = field(default_factory=frozenset)

    def has(self, permission: str) -> bool:
        return permission in self.permissions

    @property
    def is_platform_admin(self) -> bool:
        return self.platform_role == "super_admin"
