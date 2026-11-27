"""Shortlists: private to their creator until explicitly shared with colleagues."""

import uuid

from sqlalchemy import ColumnElement, exists, false, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.organization import OrganizationMember
from app.models.player import Player
from app.models.rbac import Role
from app.models.recruitment import (
    RecruitmentCandidate,
    RecruitmentRequirement,
    Shortlist,
    ShortlistPlayer,
    ShortlistShare,
)
from app.models.user import User
from app.permissions import catalog
from app.permissions.catalog import ROLES
from app.permissions.context import AuthContext
from app.repositories.clubs import escape_like
from app.repositories.players import PlayerRepository
from app.schemas.common import Page, PageParams
from app.schemas.recruitment import (
    PipelineRef,
    SharedWith,
    ShortlistCreate,
    ShortlistDetail,
    ShortlistPlayerAdd,
    ShortlistPlayerOut,
    ShortlistPlayerUpdate,
    ShortlistSummary,
    ShortlistUpdate,
)
from app.services.audit import record_audit
from app.services.notifications import notify
from app.services.players import build_summary

NOT_FOUND = AppError(404, "not_found", "Shortlist not found")


def _visible(ctx: AuthContext) -> ColumnElement[bool]:
    """Only the creator and the people it was shared with. Even organization owners cannot see
    a colleague's private shortlist."""
    return (Shortlist.organization_id == ctx.require_org()) & or_(
        Shortlist.created_by_user_id == ctx.user_id,
        exists().where(
            ShortlistShare.shortlist_id == Shortlist.id, ShortlistShare.user_id == ctx.user_id
        ),
    )


async def _load(
    db: AsyncSession, ctx: AuthContext, shortlist_id: uuid.UUID, *, owner_only: bool = False,
    lock: bool = False,
) -> Shortlist:  # fmt: skip
    ctx.require(catalog.RECRUITMENT_READ)
    stmt = select(Shortlist).where(Shortlist.id == shortlist_id, _visible(ctx))
    s = await db.scalar(stmt.with_for_update() if lock else stmt)
    if s is None:
        raise NOT_FOUND
    if owner_only and s.created_by_user_id != ctx.user_id:
        raise AppError(403, "forbidden", "Only the creator can change this shortlist")
    return s


async def _requirement_title(db: AsyncSession, ctx: AuthContext, requirement_id: uuid.UUID | None):
    if requirement_id is None:
        return None
    title = await db.scalar(
        select(RecruitmentRequirement.title).where(
            RecruitmentRequirement.id == requirement_id,
            RecruitmentRequirement.organization_id == ctx.require_org(),
        )
    )
    if title is None:
        raise AppError(422, "invalid_requirement", "Requirement not found")
    return title


async def _summaries(
    db: AsyncSession, ctx: AuthContext, rows: list[Shortlist]
) -> list[ShortlistSummary]:
    if not rows:
        return []
    ids = [s.id for s in rows]
    counts = dict(
        (
            await db.execute(
                select(ShortlistPlayer.shortlist_id, func.count(ShortlistPlayer.id))
                .where(ShortlistPlayer.shortlist_id.in_(ids))
                .group_by(ShortlistPlayer.shortlist_id)
            )
        ).all()
    )
    owners = dict(
        (
            await db.execute(
                select(User.id, User.full_name).where(
                    User.id.in_({s.created_by_user_id for s in rows})
                )
            )
        ).all()
    )
    req_ids = {s.requirement_id for s in rows if s.requirement_id}
    titles = (
        dict(
            (
                await db.execute(
                    select(RecruitmentRequirement.id, RecruitmentRequirement.title).where(
                        RecruitmentRequirement.id.in_(req_ids)
                    )
                )
            ).all()
        )
        if req_ids
        else {}
    )
    return [
        ShortlistSummary(
            id=s.id, name=s.name, description=s.description, priority=s.priority,
            requirement_id=s.requirement_id,
            requirement_title=titles.get(s.requirement_id) if s.requirement_id else None,
            player_count=counts.get(s.id, 0), is_owner=s.created_by_user_id == ctx.user_id,
            owner_name=owners.get(s.created_by_user_id), created_at=s.created_at,
        )
        for s in rows
    ]  # fmt: skip


async def create_shortlist(
    db: AsyncSession, ctx: AuthContext, data: ShortlistCreate
) -> ShortlistDetail:
    ctx.require(catalog.RECRUITMENT_MANAGE)
    await _requirement_title(db, ctx, data.requirement_id)
    s = Shortlist(
        organization_id=ctx.require_org(), created_by_user_id=ctx.user_id, **data.model_dump()
    )
    db.add(s)
    await db.flush()
    await record_audit(
        db, action="shortlist.create", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="shortlist", target_id=str(s.id),
    )  # fmt: skip
    await db.commit()
    return await get_shortlist(db, ctx, s.id)


async def list_shortlists(
    db: AsyncSession, ctx: AuthContext, page: PageParams, scope: str = "all", q: str | None = None
) -> Page[ShortlistSummary]:
    ctx.require(catalog.RECRUITMENT_READ)
    stmt = select(Shortlist).where(_visible(ctx))
    if scope == "mine":
        stmt = stmt.where(Shortlist.created_by_user_id == ctx.user_id)
    elif scope == "shared":
        stmt = stmt.where(Shortlist.created_by_user_id != ctx.user_id)
    if q:
        stmt = stmt.where(Shortlist.name.ilike(f"%{escape_like(q)}%", escape="\\"))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        (
            await db.scalars(
                stmt.order_by(Shortlist.created_at.desc()).offset(page.offset).limit(page.page_size)
            )
        ).all()
    )
    return Page(
        items=await _summaries(db, ctx, rows), total=total, page=page.page, page_size=page.page_size
    )


async def get_shortlist(
    db: AsyncSession, ctx: AuthContext, shortlist_id: uuid.UUID
) -> ShortlistDetail:
    s = await _load(db, ctx, shortlist_id)
    summary = (await _summaries(db, ctx, [s]))[0]
    rows = (
        await db.execute(
            select(ShortlistPlayer, Player)
            .join(Player, Player.id == ShortlistPlayer.player_id)
            .where(ShortlistPlayer.shortlist_id == s.id)
            .order_by(ShortlistPlayer.created_at)
        )
    ).all()
    repo = PlayerRepository(db, ctx)
    clubs = await repo.current_clubs([p.id for _, p in rows])
    refs: dict[uuid.UUID, list[PipelineRef]] = {}
    if rows:
        for pid, rid, title, stage in await db.execute(
            select(
                RecruitmentCandidate.player_id,
                RecruitmentRequirement.id,
                RecruitmentRequirement.title,
                RecruitmentCandidate.stage,
            )
            .join(
                RecruitmentRequirement,
                RecruitmentRequirement.id == RecruitmentCandidate.requirement_id,
            )
            .where(
                RecruitmentCandidate.organization_id == ctx.organization_id,
                RecruitmentCandidate.player_id.in_([p.id for _, p in rows]),
            )
        ):
            refs.setdefault(pid, []).append(
                PipelineRef(requirement_id=rid, requirement_title=title, stage=stage)
            )
    shared: list[SharedWith] = []
    if s.created_by_user_id == ctx.user_id:
        shared = [
            SharedWith(user_id=uid, full_name=name)
            for uid, name in await db.execute(
                select(User.id, User.full_name)
                .join(ShortlistShare, ShortlistShare.user_id == User.id)
                .where(ShortlistShare.shortlist_id == s.id)
                .order_by(User.full_name)
            )
        ]
    return ShortlistDetail(
        **summary.model_dump(),
        players=[
            ShortlistPlayerOut(
                player=build_summary(p, ctx, clubs), notes=sp.notes, priority=sp.priority,
                added_at=sp.created_at, pipeline=refs.get(p.id, []),
            )
            for sp, p in rows
        ],
        shared_with=shared,
    )  # fmt: skip


async def update_shortlist(
    db: AsyncSession, ctx: AuthContext, shortlist_id: uuid.UUID, data: ShortlistUpdate
) -> ShortlistDetail:
    ctx.require(catalog.RECRUITMENT_MANAGE)
    s = await _load(db, ctx, shortlist_id, owner_only=True)
    changes = data.model_dump(exclude_unset=True)
    if None in (changes.get("name", "x"), changes.get("priority", "x")):
        raise AppError(422, "validation_error", "name and priority cannot be empty")
    if changes.get("requirement_id"):
        await _requirement_title(db, ctx, changes["requirement_id"])
    for k, v in changes.items():
        setattr(s, k, v)
    await record_audit(
        db, action="shortlist.update", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="shortlist", target_id=str(s.id),
        metadata={"fields": sorted(changes)},
    )  # fmt: skip
    await db.commit()
    return await get_shortlist(db, ctx, s.id)


async def delete_shortlist(db: AsyncSession, ctx: AuthContext, shortlist_id: uuid.UUID) -> None:
    ctx.require(catalog.RECRUITMENT_MANAGE)
    s = await _load(db, ctx, shortlist_id, owner_only=True)
    await db.delete(s)  # players and shares cascade; the players themselves are untouched
    await record_audit(
        db, action="shortlist.delete", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="shortlist", target_id=str(shortlist_id),
    )  # fmt: skip
    await db.commit()


async def _sharers(db: AsyncSession, shortlist_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        await db.scalars(
            select(ShortlistShare.user_id).where(ShortlistShare.shortlist_id == shortlist_id)
        )
    )


async def add_player(
    db: AsyncSession, ctx: AuthContext, shortlist_id: uuid.UUID, data: ShortlistPlayerAdd
) -> ShortlistDetail:
    ctx.require(catalog.RECRUITMENT_MANAGE)
    s = await _load(db, ctx, shortlist_id, owner_only=True)
    player = await PlayerRepository(db, ctx).get_visible(data.player_id)
    if player is None:
        raise AppError(422, "invalid_player", "Player not found")
    try:
        async with db.begin_nested():
            db.add(
                ShortlistPlayer(
                    shortlist_id=s.id,
                    player_id=player.id,
                    added_by_user_id=ctx.user_id,
                    notes=data.notes,
                    priority=data.priority,
                )
            )
            await db.flush()
    except IntegrityError:
        raise AppError(
            409, "already_shortlisted", "This player is already on the shortlist"
        ) from None
    for user_id in await _sharers(db, s.id):
        await notify(
            db, user_id=user_id, type="player_shortlisted",
            title=f"{player.full_name} added to '{s.name}'", link_path=f"/shortlists/{s.id}",
            organization_id=s.organization_id,
        )  # fmt: skip
    await record_audit(
        db, action="shortlist.add_player", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="shortlist", target_id=str(s.id),
        metadata={"player_id": str(player.id)},
    )  # fmt: skip
    await db.commit()
    return await get_shortlist(db, ctx, s.id)


async def update_player(
    db: AsyncSession, ctx: AuthContext, shortlist_id: uuid.UUID, player_id: uuid.UUID,
    data: ShortlistPlayerUpdate,
) -> ShortlistDetail:  # fmt: skip
    ctx.require(catalog.RECRUITMENT_MANAGE)
    s = await _load(db, ctx, shortlist_id, owner_only=True)
    entry = await db.scalar(
        select(ShortlistPlayer).where(
            ShortlistPlayer.shortlist_id == s.id, ShortlistPlayer.player_id == player_id
        )
    )
    if entry is None:
        raise AppError(404, "not_found", "Player is not on this shortlist")
    changes = data.model_dump(exclude_unset=True)
    if changes.get("priority", "x") is None:
        raise AppError(422, "validation_error", "priority cannot be empty")
    for k, v in changes.items():
        setattr(entry, k, v)
    await db.commit()
    return await get_shortlist(db, ctx, s.id)


async def remove_player(
    db: AsyncSession, ctx: AuthContext, shortlist_id: uuid.UUID, player_id: uuid.UUID
) -> ShortlistDetail:
    ctx.require(catalog.RECRUITMENT_MANAGE)
    s = await _load(db, ctx, shortlist_id, owner_only=True)
    entry = await db.scalar(
        select(ShortlistPlayer).where(
            ShortlistPlayer.shortlist_id == s.id, ShortlistPlayer.player_id == player_id
        )
    )
    if entry is None:
        raise AppError(404, "not_found", "Player is not on this shortlist")
    await db.delete(entry)
    await record_audit(
        db, action="shortlist.remove_player", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="shortlist", target_id=str(s.id),
        metadata={"player_id": str(player_id)},
    )  # fmt: skip
    await db.commit()
    return await get_shortlist(db, ctx, s.id)


async def set_shares(
    db: AsyncSession, ctx: AuthContext, shortlist_id: uuid.UUID, user_ids: list[uuid.UUID]
) -> ShortlistDetail:
    """Replaces the list of colleagues who can *view* this shortlist."""
    ctx.require(catalog.RECRUITMENT_MANAGE)
    s = await _load(db, ctx, shortlist_id, owner_only=True)
    wanted = set(user_ids) - {ctx.user_id}
    eligible_roles = [k for k, (_, _, perms) in ROLES.items() if catalog.RECRUITMENT_READ in perms]
    valid = (
        set(
            await db.scalars(
                select(OrganizationMember.user_id)
                .join(Role, Role.id == OrganizationMember.role_id)
                .where(
                    OrganizationMember.organization_id == s.organization_id,
                    OrganizationMember.status == "active",
                    OrganizationMember.user_id.in_(wanted) if wanted else false(),
                    Role.key.in_(eligible_roles),
                )
            )
        )
        if wanted
        else set()
    )
    if wanted - valid:
        raise AppError(
            422,
            "invalid_user",
            "Everyone you share with must be an active member with recruitment access",
        )
    current = set(await _sharers(db, s.id))
    for uid in current - valid:
        row = await db.get(ShortlistShare, (s.id, uid))
        if row is not None:
            await db.delete(row)
    for uid in valid - current:
        db.add(ShortlistShare(shortlist_id=s.id, user_id=uid))
        await notify(
            db, user_id=uid, type="shortlist_shared", title=f"Shortlist shared with you: {s.name}",
            link_path=f"/shortlists/{s.id}", organization_id=s.organization_id,
        )  # fmt: skip
    await record_audit(
        db, action="shortlist.share", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="shortlist", target_id=str(s.id),
        metadata={"shared_with": len(valid)},
    )  # fmt: skip
    await db.commit()
    return await get_shortlist(db, ctx, s.id)
