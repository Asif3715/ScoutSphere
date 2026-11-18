import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.club import Club
from app.models.invitation import Invitation
from app.models.organization import Organization, OrganizationMember
from app.models.rbac import Role
from app.models.user import User
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.schemas.common import PageParams
from app.schemas.organizations import OrganizationCreate, OrganizationUpdate
from app.services.audit import record_audit

NOT_FOUND = AppError(404, "not_found", "Organization not found")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:60] or "org"


async def get_role(db: AsyncSession, key: str) -> Role:
    role = await db.scalar(select(Role).where(Role.key == key))
    if role is None:
        raise AppError(500, "role_missing", f"Role '{key}' is not seeded")
    return role


async def create_organization(
    db: AsyncSession, user: User, data: OrganizationCreate, ip: str | None = None
) -> Organization:
    """Any individual 'standard' account can found an organization and becomes its Club Owner."""
    if user.account_type != "standard":
        raise AppError(
            403, "account_type_not_allowed", "Only club staff accounts can create organizations"
        )
    base = slugify(data.name)
    org: Organization | None = None
    for attempt in range(8):
        # Two requests can pick the same free slug at the same moment; the unique constraint
        # decides, and the loser simply retries with a fresh suffix (inside a savepoint, so the
        # rest of the transaction survives).
        slug = base if attempt == 0 else f"{base}-{uuid.uuid4().hex[:6]}"
        candidate = Organization(
            name=data.name.strip(), slug=slug, description=data.description,
            created_by_user_id=user.id,
        )  # fmt: skip
        try:
            async with db.begin_nested():
                db.add(candidate)
                await db.flush()
        except IntegrityError:
            continue
        org = candidate
        break
    if org is None:
        raise AppError(503, "slug_unavailable", "Could not allocate a unique organization address")
    owner = await get_role(db, "club_owner")
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role_id=owner.id))
    await record_audit(
        db, action="org.create", outcome="success", actor_user_id=user.id,
        organization_id=org.id, target_type="organization", target_id=str(org.id), ip_address=ip,
    )  # fmt: skip
    await db.commit()
    return org


async def get_organization(db: AsyncSession, ctx: AuthContext) -> Organization:
    ctx.require(catalog.ORG_READ)
    org = await db.get(Organization, ctx.require_org())
    if org is None:
        raise NOT_FOUND
    return org


async def update_organization(
    db: AsyncSession, ctx: AuthContext, data: OrganizationUpdate
) -> Organization:
    ctx.require(catalog.ORG_UPDATE)
    org = await db.get(Organization, ctx.require_org())
    if org is None:
        raise NOT_FOUND
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise AppError(422, "validation_error", "Name cannot be empty")
    for field, value in changes.items():
        setattr(org, field, value)
    await record_audit(
        db, action="org.update", outcome="success", actor_user_id=ctx.user_id,
        organization_id=org.id, target_type="organization", target_id=str(org.id),
        metadata={"fields": sorted(changes)},
    )  # fmt: skip
    await db.commit()
    return org


async def dashboard_counts(db: AsyncSession, ctx: AuthContext) -> dict:
    ctx.require(catalog.ORG_READ)
    org_id = ctx.require_org()
    org = await db.get(Organization, org_id)
    if org is None:
        raise NOT_FOUND

    async def count(stmt) -> int:
        return (await db.scalar(stmt)) or 0

    return {
        "organization": org,
        "clubs": await count(
            select(func.count(Club.id)).where(
                Club.organization_id == org_id, Club.archived_at.is_(None)
            )
        ),
        "members": await count(
            select(func.count(OrganizationMember.id)).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.status == "active",
            )
        ),
        "pending_invitations": await count(
            select(func.count(Invitation.id)).where(
                Invitation.organization_id == org_id,
                Invitation.status == "pending",
                Invitation.expires_at > func.now(),
            )
        ),
    }


# ---- platform administration -------------------------------------------------------
async def list_all_organizations(
    db: AsyncSession, ctx: AuthContext, page: PageParams, q: str | None
) -> tuple[list[Organization], int]:
    ctx.require(catalog.PLATFORM_ORGS_MANAGE)
    stmt = select(Organization)
    if q:
        stmt = stmt.where(Organization.name.ilike(f"%{_escape_like(q)}%", escape="\\"))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await db.scalars(
        stmt.order_by(Organization.created_at.desc()).offset(page.offset).limit(page.page_size)
    )
    return list(rows), total


async def set_organization_status(
    db: AsyncSession, ctx: AuthContext, org_id: uuid.UUID, status: str
) -> Organization:
    ctx.require(catalog.PLATFORM_ORGS_MANAGE)
    org = await db.get(Organization, org_id)
    if org is None:
        raise NOT_FOUND
    previous, org.status = org.status, status
    await record_audit(
        db, action="org.set_status", outcome="success", actor_user_id=ctx.user_id,
        organization_id=org.id, target_type="organization", target_id=str(org.id),
        metadata={"from": previous, "to": status},
    )  # fmt: skip
    await db.commit()
    return org


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
