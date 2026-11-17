import uuid
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domain.football import MATCH_TRANSITIONS
from app.models.club import Club
from app.models.competition import (
    Competition,
    CompetitionParticipant,
    CompetitionSeason,
    Match,
    MatchEvent,
    MatchStatistics,
)
from app.models.player import Player
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.repositories.players import PlayerRepository
from app.repositories.scoped import owned, visible
from app.schemas.common import Page, PageParams
from app.schemas.matches import (
    EventCreate,
    EventOut,
    MatchCreate,
    MatchDetail,
    MatchFilters,
    MatchOut,
    MatchUpdate,
    StatsBody,
    StatsOut,
    StatsSide,
)
from app.services.audit import record_audit
from app.services.competitions import get_visible_competition

NOT_FOUND = AppError(404, "not_found", "Match not found")
STAT_FIELDS = list(StatsSide.model_fields)


def _can_manage(ctx: AuthContext, m: Match) -> bool:
    if ctx.organization_id is None:
        return m.organization_id is None and ctx.has("platform:orgs_manage")
    return m.organization_id == ctx.organization_id and ctx.has(catalog.MATCHES_MANAGE)


async def _outs(db: AsyncSession, ctx: AuthContext, matches: list[Match]) -> list[MatchOut]:
    if not matches:
        return []
    club_ids = {c for m in matches for c in (m.home_club_id, m.away_club_id)}
    clubs = dict((await db.execute(select(Club.id, Club.name).where(Club.id.in_(club_ids)))).all())
    comps = dict(
        (
            await db.execute(
                select(Competition.id, Competition.name).where(
                    Competition.id.in_({m.competition_id for m in matches})
                )
            )
        ).all()
    )
    seasons = dict(
        (
            await db.execute(
                select(CompetitionSeason.id, CompetitionSeason.name).where(
                    CompetitionSeason.id.in_({m.season_id for m in matches})
                )
            )
        ).all()
    )
    return [
        MatchOut(
            id=m.id, competition_id=m.competition_id, competition_name=comps[m.competition_id],
            season_id=m.season_id, season_name=seasons[m.season_id],
            home_club_id=m.home_club_id, home_club_name=clubs[m.home_club_id],
            away_club_id=m.away_club_id, away_club_name=clubs[m.away_club_id],
            kickoff_at=m.kickoff_at, venue=m.venue, round_label=m.round_label, status=m.status,
            home_score=m.home_score, away_score=m.away_score,
            is_global=m.organization_id is None, editable=_can_manage(ctx, m),
        )
        for m in matches
    ]  # fmt: skip


async def _visible_match(db: AsyncSession, ctx: AuthContext, match_id: uuid.UUID) -> Match:
    m = await db.scalar(
        select(Match).where(
            Match.id == match_id, visible(Match.organization_id, ctx.organization_id)
        )
    )
    if m is None:
        raise NOT_FOUND
    return m


async def _manageable(
    db: AsyncSession, ctx: AuthContext, match_id: uuid.UUID, *, lock: bool = False
) -> Match:
    ctx.require_scoped(catalog.MATCHES_MANAGE)
    stmt = select(Match).where(
        Match.id == match_id, owned(Match.organization_id, ctx.organization_id)
    )
    m = await db.scalar(stmt.with_for_update() if lock else stmt)
    if m is None:
        raise NOT_FOUND
    return m


# ---- queries -------------------------------------------------------------------------
async def list_matches(
    db: AsyncSession, ctx: AuthContext, f: MatchFilters, page: PageParams
) -> Page[MatchOut]:
    ctx.require_scoped(catalog.MATCHES_READ)
    stmt = select(Match).where(visible(Match.organization_id, ctx.organization_id))
    if f.competition_id:
        stmt = stmt.where(Match.competition_id == f.competition_id)
    if f.season_id:
        stmt = stmt.where(Match.season_id == f.season_id)
    if f.club_id:
        stmt = stmt.where(or_(Match.home_club_id == f.club_id, Match.away_club_id == f.club_id))
    if f.status:
        stmt = stmt.where(Match.status == f.status)
    if f.date_from:
        stmt = stmt.where(Match.kickoff_at >= datetime.combine(f.date_from, time.min, UTC))
    if f.date_to:  # inclusive of the whole day
        stmt = stmt.where(
            Match.kickoff_at < datetime.combine(f.date_to, time.min, UTC) + timedelta(days=1)
        )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    order = Match.kickoff_at.asc() if f.sort == "kickoff_asc" else Match.kickoff_at.desc()
    rows = (
        await db.scalars(stmt.order_by(order, Match.id).offset(page.offset).limit(page.page_size))
    ).all()
    return Page(
        items=await _outs(db, ctx, list(rows)),
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


async def _stats(db: AsyncSession, m: Match) -> StatsOut:
    rows = (await db.scalars(select(MatchStatistics).where(MatchStatistics.match_id == m.id))).all()
    by_club = {r.club_id: StatsSide(**{k: getattr(r, k) for k in STAT_FIELDS}) for r in rows}
    return StatsOut(home=by_club.get(m.home_club_id), away=by_club.get(m.away_club_id))


async def _events(db: AsyncSession, m: Match) -> list[EventOut]:
    rows = (
        await db.execute(
            select(MatchEvent, Club.name, Player.full_name)
            .join(Club, Club.id == MatchEvent.club_id)
            .outerjoin(Player, Player.id == MatchEvent.player_id)
            .where(MatchEvent.match_id == m.id)
            .order_by(MatchEvent.minute, MatchEvent.created_at)
        )
    ).all()
    return [
        EventOut(
            id=e.id, event_type=e.event_type, minute=e.minute, club_id=e.club_id, club_name=club,
            player_id=e.player_id, player_name=pname, description=e.description,
        )
        for e, club, pname in rows
    ]  # fmt: skip


async def _detail(db: AsyncSession, ctx: AuthContext, m: Match) -> MatchDetail:
    out = (await _outs(db, ctx, [m]))[0]
    return MatchDetail(
        **out.model_dump(), events=await _events(db, m), statistics=await _stats(db, m)
    )


async def get_match(db: AsyncSession, ctx: AuthContext, match_id: uuid.UUID) -> MatchDetail:
    ctx.require_scoped(catalog.MATCHES_READ)
    return await _detail(db, ctx, await _visible_match(db, ctx, match_id))


# ---- commands ------------------------------------------------------------------------
async def create_match(db: AsyncSession, ctx: AuthContext, data: MatchCreate) -> MatchDetail:
    ctx.require_scoped(catalog.MATCHES_MANAGE)
    season = await db.get(CompetitionSeason, data.season_id)
    if season is None:
        raise AppError(422, "invalid_season", "Season not found")
    try:
        comp = await get_visible_competition(db, ctx, season.competition_id)
    except AppError:
        raise AppError(422, "invalid_season", "Season not found") from None
    if comp.archived_at is not None:
        raise AppError(422, "invalid_season", "This competition is archived")

    in_season = set(
        await db.scalars(
            select(CompetitionParticipant.club_id).where(
                CompetitionParticipant.season_id == season.id,
                CompetitionParticipant.club_id.in_([data.home_club_id, data.away_club_id]),
            )
        )
    )
    if {data.home_club_id, data.away_club_id} - in_season:
        raise AppError(
            422, "club_not_in_season", "Both clubs must be participants of the selected season"
        )
    match = Match(
        organization_id=ctx.organization_id, competition_id=comp.id, season_id=season.id,
        home_club_id=data.home_club_id, away_club_id=data.away_club_id,
        kickoff_at=data.kickoff_at, venue=data.venue, round_label=data.round_label,
    )  # fmt: skip
    db.add(match)
    await db.flush()
    await record_audit(
        db, action="match.create", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="match", target_id=str(match.id),
    )  # fmt: skip
    await db.commit()
    return await _detail(db, ctx, match)


async def update_match(
    db: AsyncSession, ctx: AuthContext, match_id: uuid.UUID, data: MatchUpdate
) -> MatchDetail:
    m = await _manageable(db, ctx, match_id, lock=True)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("kickoff_at", "x") is None or changes.get("status", "x") is None:
        raise AppError(422, "validation_error", "kickoff_at and status cannot be empty")

    new_status = changes.get("status", m.status)
    if new_status != m.status and new_status not in MATCH_TRANSITIONS[m.status]:
        raise AppError(409, "invalid_transition", f"A {m.status} match cannot become {new_status}")
    home = changes.get("home_score", m.home_score)
    away = changes.get("away_score", m.away_score)

    if new_status in ("scheduled", "postponed", "cancelled"):
        if ("home_score" in changes and changes["home_score"] is not None) or (
            "away_score" in changes and changes["away_score"] is not None
        ):
            raise AppError(422, "scores_not_allowed", f"A {new_status} match has no score")
        home = away = None  # moving back from live clears any provisional score
    elif (home is None) != (away is None):
        raise AppError(422, "scores_incomplete", "Provide both the home and away score")
    elif new_status == "finished" and home is None:
        raise AppError(422, "scores_required", "A finished match needs a final score")

    for field in ("kickoff_at", "venue", "round_label"):
        if field in changes:
            setattr(m, field, changes[field])
    m.status, m.home_score, m.away_score = new_status, home, away
    await db.flush()
    await record_audit(
        db, action="match.update", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="match", target_id=str(m.id),
        metadata={"fields": sorted(changes), "status": new_status},
    )  # fmt: skip
    await db.commit()
    return await _detail(db, ctx, m)


async def delete_match(db: AsyncSession, ctx: AuthContext, match_id: uuid.UUID) -> None:
    m = await _manageable(db, ctx, match_id)
    if m.status in ("live", "finished"):
        raise AppError(409, "match_played", "Played matches cannot be deleted")
    await db.delete(m)
    await record_audit(
        db, action="match.delete", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="match", target_id=str(match_id),
    )  # fmt: skip
    await db.commit()


def _require_started(m: Match) -> None:
    if m.status not in ("live", "finished"):
        raise AppError(
            409, "match_not_started", "Events and statistics need a live or finished match"
        )


async def add_event(
    db: AsyncSession, ctx: AuthContext, match_id: uuid.UUID, data: EventCreate
) -> MatchDetail:
    m = await _manageable(db, ctx, match_id)
    _require_started(m)
    if data.club_id not in (m.home_club_id, m.away_club_id):
        raise AppError(422, "invalid_club", "The club is not playing in this match")
    if data.player_id is not None:
        if m.organization_id is None:
            raise AppError(422, "player_not_allowed", "Global matches cannot reference players")
        if await PlayerRepository(db, ctx).get_visible(data.player_id) is None:
            raise AppError(422, "invalid_player", "Player not found")
    db.add(MatchEvent(match_id=m.id, **data.model_dump()))
    await record_audit(
        db, action="match.add_event", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="match", target_id=str(m.id),
        metadata={"type": data.event_type, "minute": data.minute},
    )  # fmt: skip
    await db.commit()
    return await _detail(db, ctx, m)


async def delete_event(
    db: AsyncSession, ctx: AuthContext, match_id: uuid.UUID, event_id: uuid.UUID
) -> MatchDetail:
    m = await _manageable(db, ctx, match_id)
    ev = await db.scalar(
        select(MatchEvent).where(MatchEvent.id == event_id, MatchEvent.match_id == m.id)
    )
    if ev is None:
        raise AppError(404, "not_found", "Event not found")
    await db.delete(ev)
    await record_audit(
        db, action="match.delete_event", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="match", target_id=str(m.id),
    )  # fmt: skip
    await db.commit()
    return await _detail(db, ctx, m)


async def put_statistics(
    db: AsyncSession, ctx: AuthContext, match_id: uuid.UUID, data: StatsBody
) -> MatchDetail:
    m = await _manageable(db, ctx, match_id)
    _require_started(m)
    sent = data.model_fields_set
    sides = {"home": m.home_club_id, "away": m.away_club_id}
    merged = {k: getattr(data, k) for k in sides}
    current = await _stats(db, m)
    for k in sides:  # a side that is not sent keeps its stored value for validation purposes
        if k not in sent:
            merged[k] = getattr(current, k)
    possession = [s.possession_pct for s in merged.values() if s and s.possession_pct is not None]
    if sum(possession) > 100:
        raise AppError(422, "invalid_possession", "Combined possession cannot exceed 100%")

    for side, club_id in sides.items():
        if side not in sent:
            continue
        existing = await db.scalar(
            select(MatchStatistics).where(
                MatchStatistics.match_id == m.id, MatchStatistics.club_id == club_id
            )
        )
        payload = getattr(data, side)
        if payload is None:
            if existing is not None:
                await db.delete(existing)
            continue
        if existing is None:
            existing = MatchStatistics(match_id=m.id, club_id=club_id)
            db.add(existing)
        for field in STAT_FIELDS:
            setattr(existing, field, getattr(payload, field))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise AppError(422, "invalid_statistics", "Statistics are inconsistent") from None
    await record_audit(
        db, action="match.put_statistics", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="match", target_id=str(m.id),
    )  # fmt: skip
    await db.commit()
    return await _detail(db, ctx, m)
