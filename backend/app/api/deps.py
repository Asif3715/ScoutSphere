import uuid
from collections.abc import Callable

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.organization import Organization, OrganizationMember
from app.models.rbac import Role
from app.models.user import User
from app.permissions.catalog import ROLES
from app.permissions.context import AuthContext
from app.services.audit import record_audit

_bearer = HTTPBearer(auto_error=False)
UNAUTHENTICATED = AppError(401, "not_authenticated", "Authentication required")


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None:
        raise UNAUTHENTICATED
    user_id = decode_access_token(creds.credentials)
    if user_id is None:
        raise AppError(401, "invalid_token", "Invalid or expired access token")
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError(401, "invalid_token", "Invalid or expired access token")
    return user


async def get_auth_context(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_organization_id: str | None = Header(default=None),
) -> AuthContext:
    """Builds the caller's AuthContext. The active organization comes from a header but is
    always re-validated against a real, active membership: the header alone grants nothing."""
    perms: set[str] = set()
    if user.platform_role:
        perms |= set(ROLES[user.platform_role][2])

    if x_organization_id is None:
        return AuthContext(
            user_id=user.id, platform_role=user.platform_role, permissions=frozenset(perms)
        )

    try:
        org_id = uuid.UUID(x_organization_id)
    except ValueError:
        raise AppError(400, "invalid_organization", "Invalid X-Organization-Id") from None

    row = (
        await db.execute(
            select(Role.key, Organization.status, OrganizationMember.status)
            .join(OrganizationMember, OrganizationMember.role_id == Role.id)
            .join(Organization, Organization.id == OrganizationMember.organization_id)
            .where(OrganizationMember.user_id == user.id, Organization.id == org_id)
        )
    ).first()
    # Same error for "no such org" and "not your org": do not reveal which organizations exist.
    if row is None or row[1] != "active" or row[2] != "active":
        raise AppError(403, "not_a_member", "You are not an active member of this organization")
    role_key = row[0]
    perms |= set(ROLES[role_key][2])
    return AuthContext(
        user_id=user.id,
        platform_role=user.platform_role,
        organization_id=org_id,
        org_role=role_key,
        permissions=frozenset(perms),
    )


def require_permission(permission: str) -> Callable:
    """Route dependency: 403 (and an audit row) unless the caller holds `permission`."""

    async def _check(
        request: Request,
        ctx: AuthContext = Depends(get_auth_context),
        db: AsyncSession = Depends(get_db),
    ) -> AuthContext:
        if not ctx.has(permission):
            await record_audit(
                db, action="authz.denied", outcome="denied", actor_user_id=ctx.user_id,
                organization_id=ctx.organization_id, target_type="permission",
                target_id=permission, metadata={"path": request.url.path},
            )  # fmt: skip
            await db.commit()
            raise AppError(403, "forbidden", "You do not have permission to perform this action")
        return ctx

    return _check
