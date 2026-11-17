"""Career history and media links for a player."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.club import Club
from app.models.player import Player, PlayerCareer, PlayerMedia
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.repositories.clubs import ClubRepository
from app.repositories.players import PlayerRepository
from app.schemas.players import (
    CareerCreate,
    CareerOut,
    CareerUpdate,
    MediaCreate,
    MediaOut,
)
from app.services.audit import record_audit

NOT_FOUND = AppError(404, "not_found", "Player not found")


async def _visible_player(db: AsyncSession, ctx: AuthContext, player_id: uuid.UUID) -> Player:
    player = await PlayerRepository(db, ctx).get_visible(player_id)
    if player is None:
        raise NOT_FOUND
    return player


def _can_edit(ctx: AuthContext, player: Player, entry: PlayerCareer) -> bool:
    """The player's owning organization, or the organization that recorded the entry."""
    return ctx.has(catalog.PLAYERS_WRITE) and ctx.organization_id in (
        player.owner_organization_id,
        entry.recorded_by_organization_id,
    )


def _career_out(ctx: AuthContext, player: Player, e: PlayerCareer, club_name: str) -> CareerOut:
    return CareerOut(
        id=e.id, club_id=e.club_id, club_name=club_name, team_label=e.team_label,
        spell_type=e.spell_type, start_date=e.start_date, end_date=e.end_date,
        appearances=e.appearances, goals=e.goals, assists=e.assists,
        editable=_can_edit(ctx, player, e),
    )  # fmt: skip


async def list_career(db: AsyncSession, ctx: AuthContext, player_id: uuid.UUID) -> list[CareerOut]:
    ctx.require(catalog.PLAYERS_READ)
    player = await _visible_player(db, ctx, player_id)
    rows = await db.execute(
        select(PlayerCareer, Club.name)
        .join(Club, Club.id == PlayerCareer.club_id)
        .where(PlayerCareer.player_id == player.id)
        .order_by(PlayerCareer.start_date.desc(), PlayerCareer.created_at.desc())
    )
    return [_career_out(ctx, player, e, name) for e, name in rows]


async def add_career(
    db: AsyncSession, ctx: AuthContext, player_id: uuid.UUID, data: CareerCreate
) -> CareerOut:
    ctx.require(catalog.PLAYERS_WRITE)
    player = await PlayerRepository(db, ctx).get_owned(player_id)
    if player is None:
        raise NOT_FOUND
    # Only global reference clubs or the caller's own managed clubs can be referenced.
    club = await ClubRepository(db, ctx).get_visible(data.club_id)
    if club is None:
        raise AppError(422, "invalid_club", "Club not found")
    entry = PlayerCareer(
        player_id=player.id, recorded_by_organization_id=ctx.organization_id,
        **data.model_dump(),
    )  # fmt: skip
    db.add(entry)
    await db.flush()
    await record_audit(
        db, action="career.create", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="player", target_id=str(player.id),
        metadata={"club_id": str(club.id)},
    )  # fmt: skip
    await db.commit()
    return _career_out(ctx, player, entry, club.name)


async def _editable_entry(
    db: AsyncSession, ctx: AuthContext, player_id: uuid.UUID, entry_id: uuid.UUID
) -> tuple[Player, PlayerCareer]:
    ctx.require(catalog.PLAYERS_WRITE)
    player = await _visible_player(db, ctx, player_id)
    entry = await db.scalar(
        select(PlayerCareer).where(PlayerCareer.id == entry_id, PlayerCareer.player_id == player.id)
    )
    if entry is None or not _can_edit(ctx, player, entry):
        raise AppError(404, "not_found", "Career entry not found")
    return player, entry


async def update_career(
    db: AsyncSession, ctx: AuthContext, player_id: uuid.UUID, entry_id: uuid.UUID,
    data: CareerUpdate,
) -> CareerOut:  # fmt: skip
    player, entry = await _editable_entry(db, ctx, player_id, entry_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("start_date", "x") is None or changes.get("spell_type", "x") is None:
        raise AppError(422, "validation_error", "start_date and spell_type cannot be empty")
    for field, value in changes.items():
        setattr(entry, field, value)
    if entry.end_date and entry.end_date < entry.start_date:
        raise AppError(422, "validation_error", "End date cannot be before start date")
    await record_audit(
        db, action="career.update", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="player", target_id=str(player.id),
        metadata={"entry": str(entry.id), "fields": sorted(changes)},
    )  # fmt: skip
    await db.commit()
    club_name = await db.scalar(select(Club.name).where(Club.id == entry.club_id))
    return _career_out(ctx, player, entry, club_name or "")


async def delete_career(
    db: AsyncSession, ctx: AuthContext, player_id: uuid.UUID, entry_id: uuid.UUID
) -> None:
    player, entry = await _editable_entry(db, ctx, player_id, entry_id)
    if entry.team_player_id is not None:
        raise AppError(
            409, "managed_by_squad",
            "This entry is maintained by squad registration; release the player instead",
        )  # fmt: skip
    await db.delete(entry)
    await record_audit(
        db, action="career.delete", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="player", target_id=str(player.id),
        metadata={"entry": str(entry_id)},
    )  # fmt: skip
    await db.commit()


# ---- media (always private to the organization that added it) ------------------------
async def list_media(db: AsyncSession, ctx: AuthContext, player_id: uuid.UUID) -> list[MediaOut]:
    ctx.require(catalog.PLAYERS_READ)
    player = await _visible_player(db, ctx, player_id)
    rows = await db.scalars(
        select(PlayerMedia)
        .where(PlayerMedia.player_id == player.id, PlayerMedia.organization_id == ctx.require_org())
        .order_by(PlayerMedia.created_at.desc())
    )
    return [MediaOut.model_validate(m, from_attributes=True) for m in rows]


async def add_media(
    db: AsyncSession, ctx: AuthContext, player_id: uuid.UUID, data: MediaCreate
) -> MediaOut:
    ctx.require(catalog.PLAYERS_WRITE)
    player = await _visible_player(db, ctx, player_id)
    media = PlayerMedia(
        player_id=player.id, organization_id=ctx.require_org(),
        uploaded_by_user_id=ctx.user_id, **data.model_dump(),
    )  # fmt: skip
    db.add(media)
    await db.flush()
    await record_audit(
        db, action="media.create", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="player", target_id=str(player.id),
        metadata={"kind": data.kind},
    )  # fmt: skip
    await db.commit()
    return MediaOut.model_validate(media, from_attributes=True)


async def delete_media(
    db: AsyncSession, ctx: AuthContext, player_id: uuid.UUID, media_id: uuid.UUID
) -> None:
    ctx.require(catalog.PLAYERS_WRITE)
    media = await db.scalar(
        select(PlayerMedia).where(
            PlayerMedia.id == media_id,
            PlayerMedia.player_id == player_id,
            PlayerMedia.organization_id == ctx.require_org(),
        )
    )
    if media is None:
        raise AppError(404, "not_found", "Media not found")
    await db.delete(media)
    await record_audit(
        db, action="media.delete", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="player", target_id=str(player_id),
    )  # fmt: skip
    await db.commit()
