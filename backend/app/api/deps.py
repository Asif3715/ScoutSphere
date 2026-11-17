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
NOT_A_MEMBER = AppError(403, "not_a_member", "You are not an active member of this organization")


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


async def build_context(user: User, db: AsyncSession, org_id: uuid.UUID | None) -> AuthContext:
    """Builds the caller's AuthContext. An organization is only ever activated after
    verifying a real, active membership in an active organization."""
    perms: set[str] = set()
    if user.platform_role:
        perms |= set(ROLES[user.platform_role][2])
    if org_id is None:
        return AuthContext(
            user_id=user.id, platform_role=user.platform_role, permissions=frozenset(perms)
        )

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
        raise NOT_A_MEMBER
    perms |= set(ROLES[row[0]][2])
    return AuthContext(
        user_id=user.id,
        platform_role=user.platform_role,
        organization_id=org_id,
        org_role=row[0],
        permissions=frozenset(perms),
    )


async def get_auth_context(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_organization_id: str | None = Header(default=None),
) -> AuthContext:
    """Context for header-scoped routes (X-Organization-Id)."""
    org_id = None
    if x_organization_id is not None:
        try:
            org_id = uuid.UUID(x_organization_id)
        except ValueError:
            raise AppError(400, "invalid_organization", "Invalid X-Organization-Id") from None
    return await build_context(user, db, org_id)


async def get_path_org_context(
    org_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    """Context for routes shaped /organizations/{org_id}/...: the path id is the tenant."""
    return await build_context(user, db, org_id)


async def _deny(db: AsyncSession, request: Request, ctx: AuthContext, permission: str):
    await record_audit(
        db, action="authz.denied", outcome="denied", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="permission",
        target_id=permission, metadata={"path": request.url.path},
    )  # fmt: skip
    await db.commit()
    raise AppError(403, "forbidden", "You do not have permission to perform this action")


def require_permission(permission: str) -> Callable:
    """Route dependency (header-scoped): 403 + audit row unless the caller holds `permission`."""

    async def _check(
        request: Request,
        ctx: AuthContext = Depends(get_auth_context),
        db: AsyncSession = Depends(get_db),
    ) -> AuthContext:
        if not ctx.has(permission):
            await _deny(db, request, ctx, permission)
        return ctx

    return _check


def require_org_permission(permission: str) -> Callable:
    """Route dependency for /organizations/{org_id}/... routes."""

    async def _check(
        request: Request,
        ctx: AuthContext = Depends(get_path_org_context),
        db: AsyncSession = Depends(get_db),
    ) -> AuthContext:
        if not ctx.has(permission):
            await _deny(db, request, ctx, permission)
        return ctx

    return _check


def require_scoped(permission: str) -> Callable:
    """Route dependency for data that is organization-private or global: an organization
    member needs `permission`; with no organization, only a platform admin gets through."""

    async def _check(
        request: Request,
        ctx: AuthContext = Depends(get_auth_context),
        db: AsyncSession = Depends(get_db),
    ) -> AuthContext:
        allowed = (
            ctx.has("platform:orgs_manage") if ctx.organization_id is None else ctx.has(permission)
        )
        if not allowed:
            await _deny(db, request, ctx, permission)
        return ctx

    return _check
