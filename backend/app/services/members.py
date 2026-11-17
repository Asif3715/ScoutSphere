import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.organization import OrganizationMember
from app.models.rbac import Role
from app.models.user import User
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.schemas.organizations import MemberOut
from app.services.audit import record_audit
from app.services.organizations import get_role

OWNER = "club_owner"


def assert_can_assign(ctx: AuthContext, role_key: str) -> None:
    """Shared by membership changes and invitations."""
    if role_key not in catalog.ORG_ROLES:
        raise AppError(422, "invalid_role", "Unknown organization role")
    if role_key == OWNER and ctx.org_role != OWNER:
        raise AppError(403, "owner_required", "Only a Club Owner can grant or change owner access")


async def list_members(db: AsyncSession, ctx: AuthContext) -> list[MemberOut]:
    ctx.require(catalog.MEMBERS_READ)
    rows = await db.execute(
        select(OrganizationMember, User, Role.key)
        .join(User, User.id == OrganizationMember.user_id)
        .join(Role, Role.id == OrganizationMember.role_id)
        .where(
            OrganizationMember.organization_id == ctx.require_org(),
            OrganizationMember.status != "removed",
        )
        .order_by(User.full_name)
    )
    return [
        MemberOut(
            id=m.id, user_id=u.id, email=u.email, full_name=u.full_name,
            role=role_key, status=m.status, joined_at=m.created_at,
        )
        for m, u, role_key in rows
    ]  # fmt: skip


async def _target(db: AsyncSession, ctx: AuthContext, member_id: uuid.UUID):
    """Loads a membership of the *caller's* organization; anything else looks like 404."""
    row = (
        await db.execute(
            select(OrganizationMember, Role.key)
            .join(Role, Role.id == OrganizationMember.role_id)
            .where(
                OrganizationMember.id == member_id,
                OrganizationMember.organization_id == ctx.require_org(),
                OrganizationMember.status != "removed",
            )
            .with_for_update(of=OrganizationMember)
        )
    ).first()
    if row is None:
        raise AppError(404, "not_found", "Member not found")
    return row


async def _other_active_owners(db: AsyncSession, ctx: AuthContext, member_id: uuid.UUID) -> int:
    owner_role = await get_role(db, OWNER)
    return (
        await db.scalar(
            select(func.count(OrganizationMember.id)).where(
                OrganizationMember.organization_id == ctx.require_org(),
                OrganizationMember.role_id == owner_role.id,
                OrganizationMember.status == "active",
                OrganizationMember.id != member_id,
            )
        )
    ) or 0


async def change_role(
    db: AsyncSession, ctx: AuthContext, member_id: uuid.UUID, new_role_key: str
) -> None:
    ctx.require(catalog.MEMBERS_MANAGE)
    assert_can_assign(ctx, new_role_key)
    member, old_role_key = await _target(db, ctx, member_id)
    if old_role_key == OWNER and ctx.org_role != OWNER:
        raise AppError(403, "owner_required", "Only a Club Owner can change an owner")
    if old_role_key == OWNER and new_role_key != OWNER:
        if await _other_active_owners(db, ctx, member.id) == 0:
            raise AppError(409, "last_owner", "An organization must keep at least one owner")

    member.role_id = (await get_role(db, new_role_key)).id
    await record_audit(
        db, action="member.change_role", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="member", target_id=str(member.id),
        metadata={"from": old_role_key, "to": new_role_key},
    )  # fmt: skip
    await db.commit()


async def remove_member(db: AsyncSession, ctx: AuthContext, member_id: uuid.UUID) -> None:
    ctx.require(catalog.MEMBERS_MANAGE)
    member, role_key = await _target(db, ctx, member_id)
    if role_key == OWNER:
        if ctx.org_role != OWNER:
            raise AppError(403, "owner_required", "Only a Club Owner can remove an owner")
        if await _other_active_owners(db, ctx, member.id) == 0:
            raise AppError(409, "last_owner", "An organization must keep at least one owner")
    member.status = "removed"  # history kept; membership can be reactivated by a new invitation
    await record_audit(
        db, action="member.remove", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="member", target_id=str(member.id),
        metadata={"role": role_key},
    )  # fmt: skip
    await db.commit()
