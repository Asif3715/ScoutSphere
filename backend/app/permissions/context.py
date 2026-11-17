import uuid
from dataclasses import dataclass, field

from app.core.errors import AppError


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

    def require(self, permission: str) -> None:
        """Service-layer check, so permissions hold even when a service is called by the
        agent rather than a route."""
        if permission not in self.permissions:
            raise AppError(403, "forbidden", "You do not have permission to perform this action")

    def require_scoped(self, permission: str) -> None:
        """For data that is either organization-private or global (competitions, matches).
        With an active organization the org permission is required; without one, only a
        platform admin may act (on global data)."""
        if self.organization_id is None:
            if "platform:orgs_manage" not in self.permissions:
                raise AppError(
                    403, "forbidden", "You do not have permission to perform this action"
                )
        else:
            self.require(permission)

    def require_org(self) -> uuid.UUID:
        if self.organization_id is None:
            raise AppError(400, "organization_required", "An active organization is required")
        return self.organization_id

    @property
    def is_platform_admin(self) -> bool:
        return self.platform_role == "super_admin"
