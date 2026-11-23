import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domain.football import POSITION_GROUPS, POSITION_TO_GROUP, age_on, is_minor
from app.models.club import Club
from app.models.player import Player, PlayerCareer
from app.models.team import Team, TeamPlayer
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.repositories.clubs import ClubRepository
from app.repositories.players import PlayerRepository
from app.schemas.teams import (
    SquadAdd,
    SquadOut,
    SquadPlayerOut,
    SquadUpdate,
    TeamCreate,
    TeamOut,
    TeamUpdate,
)
from app.services.audit import record_audit
from app.services.notifications import notify

TEAM_NOT_FOUND = AppError(404, "not_found", "Team not found")
MEMBER_NOT_FOUND = AppError(404, "not_found", "Squad member not found")
TEAM_EXISTS = AppError(409, "team_exists", "This club already has a team with that name")
NUMBER_TAKEN = AppError(409, "squad_number_taken", "That squad number is already in use")


def _today() -> date:
    return datetime.now(UTC).date()


# ---- helpers -------------------------------------------------------------------------
async def _team(db: AsyncSession, ctx: AuthContext, team_id: uuid.UUID) -> Team:
    team = await db.scalar(
        select(Team).where(
            Team.id == team_id,
            Team.organization_id == ctx.require_org(),
            Team.archived_at.is_(None),
        )
    )
    if team is None:
        raise TEAM_NOT_FOUND
    return team


async def _team_out(db: AsyncSession, team: Team) -> TeamOut:
    club_name = await db.scalar(select(Club.name).where(Club.id == team.club_id))
    active = await db.scalar(
        select(func.count(TeamPlayer.id)).where(
            TeamPlayer.team_id == team.id, TeamPlayer.status == "active"
        )
    )
    return TeamOut(
        id=team.id, club_id=team.club_id, club_name=club_name or "", name=team.name,
        team_type=team.team_type, active_players=active or 0, created_at=team.created_at,
    )  # fmt: skip


async def _number_free(
    db: AsyncSession, team_id: uuid.UUID, number: int | None, exclude: uuid.UUID | None = None
) -> None:
    if number is None:
        return
    stmt = select(TeamPlayer.id).where(
        TeamPlayer.team_id == team_id,
        TeamPlayer.squad_number == number,
        TeamPlayer.status == "active",
    )
    if exclude:
        stmt = stmt.where(TeamPlayer.id != exclude)
    if await db.scalar(stmt):
        raise NUMBER_TAKEN


# ---- teams ---------------------------------------------------------------------------
async def list_teams(
    db: AsyncSession, ctx: AuthContext, club_id: uuid.UUID | None = None
) -> list[TeamOut]:
    ctx.require(catalog.CLUBS_READ)
    stmt = select(Team).where(Team.organization_id == ctx.require_org(), Team.archived_at.is_(None))
    if club_id:
        stmt = stmt.where(Team.club_id == club_id)
    teams = (await db.scalars(stmt.order_by(Team.club_id, func.lower(Team.name)))).all()
    return [await _team_out(db, t) for t in teams]


async def get_team(db: AsyncSession, ctx: AuthContext, team_id: uuid.UUID) -> TeamOut:
    ctx.require(catalog.CLUBS_READ)
    return await _team_out(db, await _team(db, ctx, team_id))


async def create_team(db: AsyncSession, ctx: AuthContext, data: TeamCreate) -> TeamOut:
    ctx.require(catalog.CLUBS_MANAGE)
    club = await ClubRepository(db, ctx).get_managed(data.club_id)  # own managed clubs only
    if club is None:
        raise AppError(422, "invalid_club", "Club not found")
    team = Team(
        organization_id=ctx.require_org(), club_id=club.id,
        name=data.name.strip(), team_type=data.team_type,
    )  # fmt: skip
    db.add(team)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise TEAM_EXISTS from None
    await record_audit(
        db, action="team.create", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="team", target_id=str(team.id),
    )  # fmt: skip
    await db.commit()
    return await _team_out(db, team)


async def update_team(
    db: AsyncSession, ctx: AuthContext, team_id: uuid.UUID, data: TeamUpdate
) -> TeamOut:
    ctx.require(catalog.CLUBS_MANAGE)
    team = await _team(db, ctx, team_id)
    changes = data.model_dump(exclude_unset=True)
    if None in (changes.get("name", "x"), changes.get("team_type", "x")):
        raise AppError(422, "validation_error", "Fields cannot be empty")
    for field, value in changes.items():
        setattr(team, field, value.strip() if field == "name" else value)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise TEAM_EXISTS from None
    await record_audit(
        db, action="team.update", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="team", target_id=str(team.id),
        metadata={"fields": sorted(changes)},
    )  # fmt: skip
    await db.commit()
    return await _team_out(db, team)


async def archive_team(db: AsyncSession, ctx: AuthContext, team_id: uuid.UUID) -> None:
    ctx.require(catalog.CLUBS_MANAGE)
    team = await _team(db, ctx, team_id)
    active = await db.scalar(
        select(func.count(TeamPlayer.id)).where(
            TeamPlayer.team_id == team.id, TeamPlayer.status == "active"
        )
    )
    if active:
        raise AppError(409, "team_has_players", "Release all players before archiving the team")
    team.archived_at = datetime.now(UTC)
    await record_audit(
        db, action="team.archive", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="team", target_id=str(team.id),
    )  # fmt: skip
    await db.commit()


# ---- squad ---------------------------------------------------------------------------
async def squad(
    db: AsyncSession, ctx: AuthContext, team_id: uuid.UUID,
    include_left: bool = False, group: str | None = None,
) -> SquadOut:  # fmt: skip
    ctx.require(catalog.CLUBS_READ)
    ctx.require(catalog.PLAYERS_READ)
    team = await _team(db, ctx, team_id)
    stmt = (
        select(TeamPlayer, Player)
        .join(Player, Player.id == TeamPlayer.player_id)
        .where(TeamPlayer.team_id == team.id, TeamPlayer.organization_id == ctx.organization_id)
        .order_by(TeamPlayer.status, TeamPlayer.squad_number.asc().nulls_last(), Player.full_name)
    )
    if not include_left:
        stmt = stmt.where(TeamPlayer.status == "active")
    rows = (await db.execute(stmt)).all()

    players, counts = [], dict.fromkeys(POSITION_GROUPS, 0)
    for tp, p in rows:
        pos = tp.position or p.primary_position
        grp = POSITION_TO_GROUP.get(pos) if pos else None
        if group and grp != group:
            continue
        if tp.status == "active" and grp:
            counts[grp] += 1
        players.append(
            SquadPlayerOut(
                membership_id=tp.id,
                player_id=p.id,
                full_name=p.full_name,
                age=age_on(p.date_of_birth),
                is_minor=is_minor(p.date_of_birth),
                nationality=p.nationality,
                primary_position=p.primary_position,
                position=tp.position,
                position_group=grp,
                squad_number=tp.squad_number,
                registered_on=tp.registered_on,
                left_on=tp.left_on,
                status=tp.status,
            )  # fmt: skip
        )
    return SquadOut(team=await _team_out(db, team), players=players, counts_by_group=counts)


async def _register(
    db: AsyncSession, ctx: AuthContext, team: Team, player: Player,
    number: int | None, position: str | None, registered_on: date,
) -> TeamPlayer:  # fmt: skip
    """Adds a squad membership and, if the player has no open spell at this club, opens one."""
    await _number_free(db, team.id, number)
    already = await db.scalar(
        select(TeamPlayer.id).where(
            TeamPlayer.team_id == team.id,
            TeamPlayer.player_id == player.id,
            TeamPlayer.status == "active",
        )
    )
    if already:
        raise AppError(409, "already_in_squad", "This player is already in the squad")

    tp = TeamPlayer(
        organization_id=ctx.require_org(), team_id=team.id, player_id=player.id,
        squad_number=number, position=position or player.primary_position,
        registered_on=registered_on,
    )  # fmt: skip
    db.add(tp)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise NUMBER_TAKEN from None

    open_spell = await db.scalar(
        select(PlayerCareer.id).where(
            PlayerCareer.player_id == player.id,
            PlayerCareer.club_id == team.club_id,
            PlayerCareer.end_date.is_(None),
        )
    )
    if open_spell is None:
        db.add(
            PlayerCareer(
                player_id=player.id, club_id=team.club_id, team_label=team.name,
                spell_type="permanent", start_date=registered_on,
                recorded_by_organization_id=ctx.organization_id, team_player_id=tp.id,
            )
        )  # fmt: skip
    return tp


async def add_to_squad(
    db: AsyncSession, ctx: AuthContext, team_id: uuid.UUID, data: SquadAdd
) -> SquadOut:
    ctx.require(catalog.CLUBS_MANAGE)
    ctx.require(catalog.PLAYERS_READ)
    team = await _team(db, ctx, team_id)
    player = await PlayerRepository(db, ctx).get_visible(data.player_id)
    if player is None:
        raise AppError(422, "invalid_player", "Player not found")
    tp = await _register(
        db, ctx, team, player, data.squad_number, data.position, data.registered_on or _today()
    )
    await _tell_player(db, player, team, "joined")
    await record_audit(
        db, action="squad.add", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="team", target_id=str(team.id),
        metadata={"player_id": str(player.id), "membership": str(tp.id)},
    )  # fmt: skip
    await db.commit()
    return await squad(db, ctx, team_id)


async def _active_member(
    db: AsyncSession, ctx: AuthContext, team: Team, membership_id: uuid.UUID
) -> TeamPlayer:
    tp = await db.scalar(
        select(TeamPlayer)
        .where(
            TeamPlayer.id == membership_id,
            TeamPlayer.team_id == team.id,
            TeamPlayer.organization_id == ctx.organization_id,
            TeamPlayer.status == "active",
        )
        .with_for_update()
    )
    if tp is None:
        raise MEMBER_NOT_FOUND
    return tp


async def _tell_player(
    db: AsyncSession, player: Player, team: Team, kind: str, *, moved: bool = False
) -> None:
    """Lets a player with a linked account know about their own squad status. (Squad
    membership is the club's private data, but this is the player's own career.)"""
    if player.claimed_by_user_id is None:
        return
    club = await db.scalar(select(Club.name).where(Club.id == team.club_id))
    where = f"{team.name} at {club}" if club else team.name
    if kind == "joined":
        title = f"You have moved to {where}" if moved else f"You have joined {where}"
        body = "Your career history has been updated."
    else:
        title, body = f"You have left {where}", "Your career history has been updated."
    await notify(
        db, user_id=player.claimed_by_user_id,
        type="squad_joined" if kind == "joined" else "squad_left",
        title=title, body=body, link_path="/player",
    )  # fmt: skip


async def _leave(db: AsyncSession, tp: TeamPlayer) -> date:
    left_on = max(_today(), tp.registered_on)
    tp.status, tp.left_on = "left", left_on
    spell = await db.scalar(
        select(PlayerCareer).where(
            PlayerCareer.team_player_id == tp.id, PlayerCareer.end_date.is_(None)
        )
    )
    if spell is not None:  # history is closed, never deleted
        spell.end_date = max(left_on, spell.start_date)
    return left_on


async def update_squad_member(
    db: AsyncSession, ctx: AuthContext, team_id: uuid.UUID, membership_id: uuid.UUID,
    data: SquadUpdate,
) -> SquadOut:  # fmt: skip
    ctx.require(catalog.CLUBS_MANAGE)
    team = await _team(db, ctx, team_id)
    tp = await _active_member(db, ctx, team, membership_id)
    changes = data.model_dump(exclude_unset=True)
    if "squad_number" in changes:
        await _number_free(db, team.id, changes["squad_number"], exclude=tp.id)
    for field, value in changes.items():
        setattr(tp, field, value)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise NUMBER_TAKEN from None
    await record_audit(
        db, action="squad.update", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="team", target_id=str(team.id),
        metadata={"membership": str(tp.id), "fields": sorted(changes)},
    )  # fmt: skip
    await db.commit()
    return await squad(db, ctx, team_id)


async def release_from_squad(
    db: AsyncSession, ctx: AuthContext, team_id: uuid.UUID, membership_id: uuid.UUID
) -> SquadOut:
    ctx.require(catalog.CLUBS_MANAGE)
    team = await _team(db, ctx, team_id)
    tp = await _active_member(db, ctx, team, membership_id)
    await _leave(db, tp)
    released = await db.get(Player, tp.player_id)
    await _tell_player(db, released, team, "left")
    await record_audit(
        db, action="squad.release", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="team", target_id=str(team.id),
        metadata={"membership": str(tp.id), "player_id": str(tp.player_id)},
    )  # fmt: skip
    await db.commit()
    return await squad(db, ctx, team_id)


async def transfer_squad_member(
    db: AsyncSession, ctx: AuthContext, team_id: uuid.UUID, membership_id: uuid.UUID,
    to_team_id: uuid.UUID, squad_number: int | None,
) -> SquadOut:  # fmt: skip
    """Moves a player to another team of the same organization in one transaction: the old
    membership and career spell are closed, a new one is opened. No player record is copied."""
    ctx.require(catalog.CLUBS_MANAGE)
    if to_team_id == team_id:
        raise AppError(422, "same_team", "Choose a different team")
    team = await _team(db, ctx, team_id)
    target = await _team(db, ctx, to_team_id)
    tp = await _active_member(db, ctx, team, membership_id)
    player = await db.get(Player, tp.player_id)
    position = tp.position
    await _leave(db, tp)
    await _register(db, ctx, target, player, squad_number, position, _today())
    await _tell_player(db, player, target, "joined", moved=True)
    await record_audit(
        db, action="squad.transfer", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="team", target_id=str(team.id),
        metadata={"player_id": str(player.id), "to_team": str(target.id)},
    )  # fmt: skip
    await db.commit()
    return await squad(db, ctx, to_team_id)
