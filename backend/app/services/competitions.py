import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.club import Club
from app.models.competition import Competition, CompetitionParticipant, CompetitionSeason, Match
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.repositories.clubs import escape_like
from app.repositories.scoped import owned, usable_club, visible
from app.schemas.common import Page, PageParams
from app.schemas.competitions import (
    CompetitionCreate,
    CompetitionDetail,
    CompetitionOut,
    CompetitionUpdate,
    ParticipantOut,
    SeasonCreate,
    SeasonDetail,
    SeasonOut,
    SeasonUpdate,
)
from app.services.audit import record_audit

NOT_FOUND = AppError(404, "not_found", "Competition not found")
SEASON_NOT_FOUND = AppError(404, "not_found", "Season not found")


def _can_manage(ctx: AuthContext, comp: Competition) -> bool:
    """Tenants manage their own competitions; global ones belong to platform admins."""
    if ctx.organization_id is None:
        return comp.organization_id is None and ctx.has("platform:orgs_manage")
    return comp.organization_id == ctx.organization_id and ctx.has(catalog.MATCHES_MANAGE)


async def get_visible_competition(
    db: AsyncSession, ctx: AuthContext, competition_id: uuid.UUID
) -> Competition:
    comp = await db.scalar(
        select(Competition).where(
            Competition.id == competition_id,
            visible(Competition.organization_id, ctx.organization_id),
        )
    )
    if comp is None:
        raise NOT_FOUND
    return comp


async def _manageable(db: AsyncSession, ctx: AuthContext, competition_id: uuid.UUID) -> Competition:
    ctx.require_scoped(catalog.MATCHES_MANAGE)
    comp = await db.scalar(
        select(Competition).where(
            Competition.id == competition_id,
            Competition.archived_at.is_(None),
            owned(Competition.organization_id, ctx.organization_id),
        )
    )
    if comp is None:  # global/other-tenant competitions look "not found" to tenants
        raise NOT_FOUND
    return comp


async def _season_out(db: AsyncSession, s: CompetitionSeason) -> SeasonOut:
    participants = await db.scalar(
        select(func.count())
        .select_from(CompetitionParticipant)
        .where(CompetitionParticipant.season_id == s.id)
    )
    matches = await db.scalar(select(func.count(Match.id)).where(Match.season_id == s.id))
    return SeasonOut(
        id=s.id, competition_id=s.competition_id, name=s.name, start_date=s.start_date,
        end_date=s.end_date, participant_count=participants or 0, match_count=matches or 0,
    )  # fmt: skip


def _comp_out(ctx: AuthContext, c: Competition, season_count: int) -> CompetitionOut:
    return CompetitionOut(
        id=c.id, name=c.name, country=c.country, competition_type=c.competition_type,
        is_global=c.organization_id is None, editable=_can_manage(ctx, c),
        season_count=season_count, created_at=c.created_at,
    )  # fmt: skip


async def _season_count(db: AsyncSession, competition_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count(CompetitionSeason.id)).where(
                CompetitionSeason.competition_id == competition_id
            )
        )
    ) or 0


# ---- competitions --------------------------------------------------------------------
async def list_competitions(
    db: AsyncSession, ctx: AuthContext, page: PageParams, q=None, country=None, ctype=None
) -> Page[CompetitionOut]:
    ctx.require_scoped(catalog.MATCHES_READ)
    stmt = select(Competition).where(
        Competition.archived_at.is_(None), visible(Competition.organization_id, ctx.organization_id)
    )
    if q:
        stmt = stmt.where(Competition.name.ilike(f"%{escape_like(q)}%", escape="\\"))
    if country:
        stmt = stmt.where(func.lower(Competition.country) == country.lower())
    if ctype:
        stmt = stmt.where(Competition.competition_type == ctype)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await db.scalars(
        stmt.order_by(func.lower(Competition.name)).offset(page.offset).limit(page.page_size)
    )
    items = [_comp_out(ctx, c, await _season_count(db, c.id)) for c in rows]
    return Page(items=items, total=total, page=page.page, page_size=page.page_size)


async def get_competition(
    db: AsyncSession, ctx: AuthContext, competition_id: uuid.UUID
) -> CompetitionDetail:
    ctx.require_scoped(catalog.MATCHES_READ)
    comp = await get_visible_competition(db, ctx, competition_id)
    seasons = (
        await db.scalars(
            select(CompetitionSeason)
            .where(CompetitionSeason.competition_id == comp.id)
            .order_by(CompetitionSeason.start_date.desc())
        )
    ).all()
    out = _comp_out(ctx, comp, len(seasons))
    return CompetitionDetail(
        **out.model_dump(), seasons=[await _season_out(db, s) for s in seasons]
    )


async def create_competition(
    db: AsyncSession, ctx: AuthContext, data: CompetitionCreate
) -> CompetitionOut:
    ctx.require_scoped(catalog.MATCHES_MANAGE)
    comp = Competition(organization_id=ctx.organization_id, **data.model_dump())
    db.add(comp)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise AppError(
            409, "competition_exists", "A competition with this name already exists"
        ) from None
    await record_audit(
        db, action="competition.create", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="competition", target_id=str(comp.id),
    )  # fmt: skip
    await db.commit()
    return _comp_out(ctx, comp, 0)


async def update_competition(
    db: AsyncSession, ctx: AuthContext, competition_id: uuid.UUID, data: CompetitionUpdate
) -> CompetitionOut:
    comp = await _manageable(db, ctx, competition_id)
    changes = data.model_dump(exclude_unset=True)
    if None in (changes.get("name", "x"), changes.get("competition_type", "x")):
        raise AppError(422, "validation_error", "Fields cannot be empty")
    for field, value in changes.items():
        setattr(comp, field, value)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise AppError(
            409, "competition_exists", "A competition with this name already exists"
        ) from None
    await record_audit(
        db, action="competition.update", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="competition", target_id=str(comp.id),
        metadata={"fields": sorted(changes)},
    )  # fmt: skip
    await db.commit()
    return _comp_out(ctx, comp, await _season_count(db, comp.id))


async def archive_competition(
    db: AsyncSession, ctx: AuthContext, competition_id: uuid.UUID
) -> None:
    from datetime import UTC, datetime

    comp = await _manageable(db, ctx, competition_id)
    comp.archived_at = datetime.now(UTC)
    await record_audit(
        db, action="competition.archive", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="competition", target_id=str(comp.id),
    )  # fmt: skip
    await db.commit()


# ---- seasons -------------------------------------------------------------------------
async def create_season(
    db: AsyncSession, ctx: AuthContext, competition_id: uuid.UUID, data: SeasonCreate
) -> SeasonOut:
    comp = await _manageable(db, ctx, competition_id)
    season = CompetitionSeason(competition_id=comp.id, **data.model_dump())
    db.add(season)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise AppError(
            409, "season_exists", "This competition already has a season with that name"
        ) from None
    await record_audit(
        db, action="season.create", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="season", target_id=str(season.id),
    )  # fmt: skip
    await db.commit()
    return await _season_out(db, season)


async def _season_for(
    db: AsyncSession, ctx: AuthContext, season_id: uuid.UUID
) -> tuple[CompetitionSeason, Competition]:
    row = (
        await db.execute(
            select(CompetitionSeason, Competition)
            .join(Competition, Competition.id == CompetitionSeason.competition_id)
            .where(
                CompetitionSeason.id == season_id,
                visible(Competition.organization_id, ctx.organization_id),
            )
        )
    ).first()
    if row is None:
        raise SEASON_NOT_FOUND
    return row[0], row[1]


async def get_season(db: AsyncSession, ctx: AuthContext, season_id: uuid.UUID) -> SeasonDetail:
    ctx.require_scoped(catalog.MATCHES_READ)
    season, comp = await _season_for(db, ctx, season_id)
    rows = await db.execute(
        select(Club)
        .join(CompetitionParticipant, CompetitionParticipant.club_id == Club.id)
        .where(CompetitionParticipant.season_id == season.id)
        .order_by(func.lower(Club.name))
    )
    base = await _season_out(db, season)
    return SeasonDetail(
        **base.model_dump(), competition_name=comp.name, editable=_can_manage(ctx, comp),
        participants=[
            ParticipantOut(club_id=c.id, club_name=c.name, is_reference=c.organization_id is None)
            for (c,) in rows
        ],
    )  # fmt: skip


async def _manageable_season(
    db: AsyncSession, ctx: AuthContext, season_id: uuid.UUID
) -> tuple[CompetitionSeason, Competition]:
    ctx.require_scoped(catalog.MATCHES_MANAGE)
    season, comp = await _season_for(db, ctx, season_id)
    if not _can_manage(ctx, comp) or comp.archived_at is not None:
        raise SEASON_NOT_FOUND
    return season, comp


async def update_season(
    db: AsyncSession, ctx: AuthContext, season_id: uuid.UUID, data: SeasonUpdate
) -> SeasonOut:
    season, _ = await _manageable_season(db, ctx, season_id)
    changes = data.model_dump(exclude_unset=True)
    if any(changes.get(k, "x") is None for k in ("name", "start_date", "end_date")):
        raise AppError(422, "validation_error", "Fields cannot be empty")
    for field, value in changes.items():
        setattr(season, field, value)
    if season.end_date < season.start_date:
        raise AppError(422, "validation_error", "End date cannot be before start date")
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise AppError(
            409, "season_exists", "This competition already has a season with that name"
        ) from None
    await record_audit(
        db, action="season.update", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="season", target_id=str(season.id),
        metadata={"fields": sorted(changes)},
    )  # fmt: skip
    await db.commit()
    return await _season_out(db, season)


async def delete_season(db: AsyncSession, ctx: AuthContext, season_id: uuid.UUID) -> None:
    season, _ = await _manageable_season(db, ctx, season_id)
    if await db.scalar(select(func.count(Match.id)).where(Match.season_id == season.id)):
        raise AppError(409, "season_has_matches", "Remove the season's matches first")
    await db.execute(
        CompetitionParticipant.__table__.delete().where(
            CompetitionParticipant.season_id == season.id
        )
    )
    await db.delete(season)
    await record_audit(
        db, action="season.delete", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="season", target_id=str(season_id),
    )  # fmt: skip
    await db.commit()


# ---- participants --------------------------------------------------------------------
async def add_participant(
    db: AsyncSession, ctx: AuthContext, season_id: uuid.UUID, club_id: uuid.UUID
) -> SeasonDetail:
    season, comp = await _manageable_season(db, ctx, season_id)
    # A club must be global, or belong to the same organization as the competition. A global
    # competition therefore only ever lists global clubs (no leaking of private clubs).
    club = await usable_club(db, comp.organization_id, club_id)
    if club is None:
        raise AppError(422, "invalid_club", "Club not found")
    db.add(CompetitionParticipant(season_id=season.id, club_id=club.id))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise AppError(409, "already_participant", "This club is already in the season") from None
    await record_audit(
        db, action="season.add_participant", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="season", target_id=str(season.id),
        metadata={"club_id": str(club.id)},
    )  # fmt: skip
    await db.commit()
    return await get_season(db, ctx, season_id)


async def remove_participant(
    db: AsyncSession, ctx: AuthContext, season_id: uuid.UUID, club_id: uuid.UUID
) -> SeasonDetail:
    season, _ = await _manageable_season(db, ctx, season_id)
    row = await db.scalar(
        select(CompetitionParticipant).where(
            CompetitionParticipant.season_id == season.id, CompetitionParticipant.club_id == club_id
        )
    )
    if row is None:
        raise AppError(404, "not_found", "Club is not in this season")
    played = await db.scalar(
        select(func.count(Match.id)).where(
            Match.season_id == season.id,
            (Match.home_club_id == club_id) | (Match.away_club_id == club_id),
        )
    )
    if played:
        raise AppError(409, "participant_has_matches", "This club has matches in the season")
    await db.delete(row)
    await record_audit(
        db, action="season.remove_participant", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="season", target_id=str(season.id),
        metadata={"club_id": str(club_id)},
    )  # fmt: skip
    await db.commit()
    return await get_season(db, ctx, season_id)
