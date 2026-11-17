import uuid

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.organization import OrganizationMember
from app.models.rbac import Role
from app.models.scout import ScoutProfile, ScoutSpecialization
from app.models.user import User
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.repositories.clubs import escape_like
from app.schemas.common import Page, PageParams
from app.schemas.scouts import ScoutCreate, ScoutOut, ScoutUpdate
from app.services.audit import record_audit

NOT_FOUND = AppError(404, "not_found", "Scout not found")


def _base_query(org_id: uuid.UUID):
    """Profiles of *active members* of this organization only."""
    return (
        select(ScoutProfile, User, Role.key)
        .join(User, User.id == ScoutProfile.user_id)
        .join(
            OrganizationMember,
            (OrganizationMember.user_id == ScoutProfile.user_id)
            & (OrganizationMember.organization_id == ScoutProfile.organization_id),
        )
        .join(Role, Role.id == OrganizationMember.role_id)
        .where(ScoutProfile.organization_id == org_id, OrganizationMember.status == "active")
    )


async def _specs(db: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, list[str]]]:
    out: dict[uuid.UUID, dict[str, list[str]]] = {
        i: {"position": [], "age_group": [], "region": []} for i in ids
    }
    if ids:
        rows = await db.execute(
            select(ScoutSpecialization).where(ScoutSpecialization.scout_profile_id.in_(ids))
        )
        for (sp,) in rows:
            out[sp.scout_profile_id][sp.kind].append(sp.value)
        for d in out.values():
            for v in d.values():
                v.sort()
    return out


def _can_edit(ctx: AuthContext, profile: ScoutProfile) -> bool:
    return ctx.has(catalog.SCOUTS_MANAGE) or profile.user_id == ctx.user_id


def _out(ctx: AuthContext, p: ScoutProfile, u: User, role: str, specs: dict) -> ScoutOut:
    return ScoutOut(
        id=p.id, user_id=u.id, full_name=u.full_name, email=u.email, org_role=role,
        bio=p.bio, experience_years=p.experience_years, positions=specs["position"],
        age_groups=specs["age_group"], regions=specs["region"], is_active=p.is_active,
        can_edit=_can_edit(ctx, p), created_at=p.created_at,
    )  # fmt: skip


async def list_scouts(
    db: AsyncSession, ctx: AuthContext, page: PageParams, *, q=None, position=None,
    age_group=None, region=None, min_experience=None, active: bool | None = True,
) -> Page[ScoutOut]:  # fmt: skip
    ctx.require(catalog.SCOUTS_READ)
    stmt = _base_query(ctx.require_org())
    if q:
        stmt = stmt.where(User.full_name.ilike(f"%{escape_like(q)}%", escape="\\"))
    if active is not None:
        stmt = stmt.where(ScoutProfile.is_active == active)
    if min_experience is not None:
        stmt = stmt.where(ScoutProfile.experience_years >= min_experience)
    for kind, value in (("position", position), ("age_group", age_group), ("region", region)):
        if value:
            cond = ScoutSpecialization.value == value
            if kind == "region":
                cond = func.lower(ScoutSpecialization.value) == value.lower()
            stmt = stmt.where(
                exists().where(
                    ScoutSpecialization.scout_profile_id == ScoutProfile.id,
                    ScoutSpecialization.kind == kind,
                    cond,
                )
            )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        await db.execute(
            stmt.order_by(func.lower(User.full_name), ScoutProfile.id)
            .offset(page.offset)
            .limit(page.page_size)
        )
    ).all()
    specs = await _specs(db, [p.id for p, _, _ in rows])
    return Page(
        items=[_out(ctx, p, u, r, specs[p.id]) for p, u, r in rows],
        total=total, page=page.page, page_size=page.page_size,
    )  # fmt: skip


async def _load(db: AsyncSession, ctx: AuthContext, scout_id: uuid.UUID):
    row = (
        await db.execute(_base_query(ctx.require_org()).where(ScoutProfile.id == scout_id))
    ).first()
    if row is None:
        raise NOT_FOUND
    return row


async def get_scout(db: AsyncSession, ctx: AuthContext, scout_id: uuid.UUID) -> ScoutOut:
    ctx.require(catalog.SCOUTS_READ)
    p, u, role = await _load(db, ctx, scout_id)
    return _out(ctx, p, u, role, (await _specs(db, [p.id]))[p.id])


async def _replace_specs(
    db: AsyncSession, profile_id: uuid.UUID, kind: str, values: list[str]
) -> None:
    existing = await db.scalars(
        select(ScoutSpecialization).where(
            ScoutSpecialization.scout_profile_id == profile_id, ScoutSpecialization.kind == kind
        )
    )
    for row in existing:
        await db.delete(row)
    await db.flush()
    db.add_all(ScoutSpecialization(scout_profile_id=profile_id, kind=kind, value=v) for v in values)


async def create_scout(db: AsyncSession, ctx: AuthContext, data: ScoutCreate) -> ScoutOut:
    org_id = ctx.require_org()
    target_id = data.user_id or ctx.user_id
    if target_id == ctx.user_id:
        # Self-service for people who can scout; managers can also profile themselves.
        if not (ctx.has(catalog.REPORTS_WRITE) or ctx.has(catalog.SCOUTS_MANAGE)):
            raise AppError(403, "forbidden", "You do not have permission to create a scout profile")
    else:
        ctx.require(catalog.SCOUTS_MANAGE)

    member = await db.scalar(
        select(OrganizationMember.id).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == target_id,
            OrganizationMember.status == "active",
        )
    )
    if member is None:
        raise AppError(
            422, "not_a_member", "That person is not an active member of this organization"
        )

    profile = ScoutProfile(
        organization_id=org_id, user_id=target_id, bio=data.bio,
        experience_years=data.experience_years,
    )  # fmt: skip
    db.add(profile)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise AppError(409, "scout_exists", "This member already has a scout profile") from None
    for kind, values in (
        ("position", data.positions), ("age_group", data.age_groups), ("region", data.regions)
    ):  # fmt: skip
        db.add_all(
            ScoutSpecialization(scout_profile_id=profile.id, kind=kind, value=v) for v in values
        )
    await record_audit(
        db, action="scout.create", outcome="success", actor_user_id=ctx.user_id,
        organization_id=org_id, target_type="scout", target_id=str(profile.id),
    )  # fmt: skip
    await db.commit()
    p, u, role = await _load(db, ctx, profile.id)
    return _out(ctx, p, u, role, (await _specs(db, [p.id]))[p.id])


async def update_scout(
    db: AsyncSession, ctx: AuthContext, scout_id: uuid.UUID, data: ScoutUpdate
) -> ScoutOut:
    profile, _, _ = await _load(db, ctx, scout_id)
    if not _can_edit(ctx, profile):
        raise AppError(403, "forbidden", "You can only edit your own scout profile")
    changes = data.model_dump(exclude_unset=True)
    if "is_active" in changes:
        ctx.require(catalog.SCOUTS_MANAGE)
        if changes["is_active"] is None:
            raise AppError(422, "validation_error", "is_active cannot be empty")
    for kind, field in (
        ("position", "positions"),
        ("age_group", "age_groups"),
        ("region", "regions"),
    ):
        values = changes.pop(field, None)
        if values is not None:
            await _replace_specs(db, profile.id, kind, list(dict.fromkeys(values)))
    for field, value in changes.items():
        setattr(profile, field, value)
    await record_audit(
        db, action="scout.update", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="scout", target_id=str(profile.id),
        metadata={"fields": sorted(data.model_dump(exclude_unset=True))},
    )  # fmt: skip
    await db.commit()
    p, u, role = await _load(db, ctx, profile.id)
    return _out(ctx, p, u, role, (await _specs(db, [p.id]))[p.id])
