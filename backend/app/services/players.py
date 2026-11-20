import uuid

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domain.football import age_on, is_minor
from app.models.player import Player, PlayerPosition
from app.models.team import TeamPlayer
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.repositories.players import PlayerFilters, PlayerRepository
from app.schemas.common import Page, PageParams
from app.schemas.players import (
    CurrentClub,
    DuplicateCandidate,
    PlayerCreate,
    PlayerOut,
    PlayerSummary,
    PlayerUpdate,
)
from app.services import media
from app.services.audit import record_audit

NOT_FOUND = AppError(404, "not_found", "Player not found")


# ---- serialization -------------------------------------------------------------------
def _club(clubs: dict, pid: uuid.UUID) -> CurrentClub | None:
    return CurrentClub(club_id=clubs[pid][0], club_name=clubs[pid][1]) if pid in clubs else None


def _photo(p: Player, *, thumb: bool) -> str | None:
    if p.photo_key:
        return media.signed_path(media.thumb_key(p.photo_key) if thumb else p.photo_key)
    return p.profile_picture_url


def _photo_hidden(p: Player, ctx: AuthContext) -> bool:
    """Other organizations never see a minor's photo (PRD 0.1)."""
    return is_minor(p.date_of_birth) and p.owner_organization_id != ctx.organization_id


def photo_thumb(p: Player, ctx: AuthContext) -> str | None:
    """Thumbnail path for list views, honouring minor protection."""
    return None if _photo_hidden(p, ctx) else _photo(p, thumb=True)


def build_out(p: Player, ctx: AuthContext, clubs: dict, secondaries: dict) -> PlayerOut:
    """Applies minor-protection redaction: other organizations never receive a minor's
    biography or photo (PRD 0.1)."""
    owner = p.owner_organization_id == ctx.organization_id
    minor = is_minor(p.date_of_birth)
    hide = minor and not owner
    return PlayerOut(
        id=p.id, full_name=p.full_name, date_of_birth=p.date_of_birth,
        age=age_on(p.date_of_birth), is_minor=minor, nationality=p.nationality,
        height_cm=p.height_cm, weight_kg=p.weight_kg, preferred_foot=p.preferred_foot,
        primary_position=p.primary_position, secondary_positions=secondaries.get(p.id, []),
        biography=None if hide else p.biography,
        profile_picture_url=None if hide else p.profile_picture_url,
        photo_url=None if hide else _photo(p, thumb=False),
        photo_thumb_url=None if hide else _photo(p, thumb=True),
        has_uploaded_photo=p.photo_key is not None and not hide,
        visibility=p.visibility,
        is_owner=owner, current_club=_club(clubs, p.id), created_at=p.created_at,
    )  # fmt: skip


def build_summary(p: Player, ctx: AuthContext, clubs: dict) -> PlayerSummary:
    return PlayerSummary(
        id=p.id, full_name=p.full_name, age=age_on(p.date_of_birth),
        is_minor=is_minor(p.date_of_birth), nationality=p.nationality,
        primary_position=p.primary_position, current_club=_club(clubs, p.id),
        is_owner=p.owner_organization_id == ctx.organization_id,
        photo_thumb_url=photo_thumb(p, ctx),
    )  # fmt: skip


async def _one(db: AsyncSession, ctx: AuthContext, repo: PlayerRepository, p: Player) -> PlayerOut:
    clubs = await repo.current_clubs([p.id])
    secs = await repo.secondary_positions([p.id])
    return build_out(p, ctx, clubs, secs)


# ---- queries -------------------------------------------------------------------------
async def list_players(
    db: AsyncSession, ctx: AuthContext, filters: PlayerFilters, page: PageParams
) -> Page[PlayerSummary]:
    ctx.require(catalog.PLAYERS_READ)
    repo = PlayerRepository(db, ctx)
    players, total = await repo.search(filters, page)
    clubs = await repo.current_clubs([p.id for p in players])
    return Page(
        items=[build_summary(p, ctx, clubs) for p in players],
        total=total, page=page.page, page_size=page.page_size,
    )  # fmt: skip


async def get_player(db: AsyncSession, ctx: AuthContext, player_id: uuid.UUID) -> PlayerOut:
    ctx.require(catalog.PLAYERS_READ)
    repo = PlayerRepository(db, ctx)
    player = await repo.get_visible(player_id)
    if player is None:  # missing and "not visible to you" are indistinguishable
        raise NOT_FOUND
    return await _one(db, ctx, repo, player)


# ---- commands ------------------------------------------------------------------------
def _assert_visibility_allowed(visibility: str, dob) -> None:
    if visibility == "public" and is_minor(dob):
        raise AppError(
            422, "minor_cannot_be_public", "Players under 18 cannot have a public profile"
        )


async def create_player(db: AsyncSession, ctx: AuthContext, data: PlayerCreate) -> PlayerOut:
    ctx.require(catalog.PLAYERS_WRITE)
    org_id = ctx.require_org()
    _assert_visibility_allowed(data.visibility, data.date_of_birth)
    repo = PlayerRepository(db, ctx)

    if not data.allow_duplicate:
        dups = await repo.find_duplicates(data.full_name, data.date_of_birth)
        if dups:
            raise AppError(
                409, "possible_duplicate",
                "A similar player already exists. Review it or confirm this is a different person.",
                [
                    DuplicateCandidate(
                        id=p.id, full_name=p.full_name, date_of_birth=p.date_of_birth,
                        nationality=p.nationality, similarity=round(s, 2),
                    ).model_dump(mode="json")
                    for p, s in dups
                ],
            )  # fmt: skip

    fields = data.model_dump(exclude={"allow_duplicate", "secondary_positions"})
    player = Player(owner_organization_id=org_id, **fields)
    db.add(player)
    await db.flush()
    db.add_all(
        PlayerPosition(player_id=player.id, position=pos) for pos in data.secondary_positions
    )
    await record_audit(
        db, action="player.create", outcome="success", actor_user_id=ctx.user_id,
        organization_id=org_id, target_type="player", target_id=str(player.id),
        metadata={"duplicate_override": data.allow_duplicate},
    )  # fmt: skip
    await db.commit()
    return await _one(db, ctx, repo, player)


async def update_player(
    db: AsyncSession, ctx: AuthContext, player_id: uuid.UUID, data: PlayerUpdate
) -> PlayerOut:
    ctx.require(catalog.PLAYERS_WRITE)
    repo = PlayerRepository(db, ctx)
    player = await repo.get_owned(player_id)
    if player is None:
        # Visible-but-not-owned players: cannot edit, and we do not reveal more than "not found".
        raise NOT_FOUND
    changes = data.model_dump(exclude_unset=True)
    for required in ("full_name", "date_of_birth"):
        if required in changes and changes[required] is None:
            raise AppError(422, "validation_error", f"{required} cannot be empty")

    secondaries = changes.pop("secondary_positions", None)
    old_visibility = player.visibility
    for field, value in changes.items():
        setattr(player, field, value)
    _assert_visibility_allowed(player.visibility, player.date_of_birth)

    if secondaries is not None:
        secondaries = [s for s in dict.fromkeys(secondaries) if s != player.primary_position]
        await db.execute(delete(PlayerPosition).where(PlayerPosition.player_id == player.id))
        db.add_all(PlayerPosition(player_id=player.id, position=s) for s in secondaries)
    elif player.primary_position:  # a new primary position must not remain a secondary
        await db.execute(
            delete(PlayerPosition).where(
                PlayerPosition.player_id == player.id,
                PlayerPosition.position == player.primary_position,
            )
        )

    meta = {
        "fields": sorted(changes) + (["secondary_positions"] if secondaries is not None else [])
    }
    await record_audit(
        db, action="player.update", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="player", target_id=str(player.id),
        metadata=meta,
    )  # fmt: skip
    if player.visibility != old_visibility:  # sensitive: audited separately
        await record_audit(
            db, action="player.set_visibility", outcome="success", actor_user_id=ctx.user_id,
            organization_id=ctx.organization_id, target_type="player", target_id=str(player.id),
            metadata={"from": old_visibility, "to": player.visibility},
        )  # fmt: skip
    await db.commit()
    return await _one(db, ctx, repo, player)


async def archive_player(db: AsyncSession, ctx: AuthContext, player_id: uuid.UUID) -> None:
    from datetime import UTC, datetime

    ctx.require(catalog.PLAYERS_WRITE)
    repo = PlayerRepository(db, ctx)
    player = await repo.get_owned(player_id, for_update=True)
    if player is None:
        raise NOT_FOUND
    in_squad = await db.scalar(
        select(exists().where(TeamPlayer.player_id == player.id, TeamPlayer.status == "active"))
    )
    if in_squad:
        raise AppError(
            409, "player_in_squad", "Release the player from all squads before archiving"
        )
    player.archived_at = datetime.now(UTC)
    await record_audit(
        db, action="player.archive", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="player", target_id=str(player.id),
    )  # fmt: skip
    await db.commit()


# ---- photo ---------------------------------------------------------------------------
async def set_photo(
    db: AsyncSession, ctx: AuthContext, player_id: uuid.UUID, data: bytes, crop: media.Crop | None
) -> PlayerOut:
    """Stores a new photo (replacing any previous one). Same rights as editing the player."""
    from datetime import UTC, datetime

    ctx.require(catalog.PLAYERS_WRITE)
    repo = PlayerRepository(db, ctx)
    player = await repo.get_owned(player_id, for_update=True)
    if player is None:
        raise NOT_FOUND
    full, thumb = media.process_photo(data, crop)  # validates before anything is written
    store = media.storage()
    key, tkey = media.new_photo_keys(player.id)
    store.save(key, full)
    store.save(tkey, thumb)
    old = player.photo_key
    player.photo_key, player.photo_updated_at = key, datetime.now(UTC)
    await record_audit(
        db, action="player.photo_update", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="player", target_id=str(player.id),
        metadata={"bytes": len(data)},
    )  # fmt: skip
    try:
        await db.commit()
    except Exception:
        store.delete(key)  # nothing points at the new files; do not leave them behind
        store.delete(tkey)
        raise
    if old:
        store.delete(old)
        store.delete(media.thumb_key(old))
    return await _one(db, ctx, repo, player)


async def remove_photo(db: AsyncSession, ctx: AuthContext, player_id: uuid.UUID) -> PlayerOut:
    ctx.require(catalog.PLAYERS_WRITE)
    repo = PlayerRepository(db, ctx)
    player = await repo.get_owned(player_id, for_update=True)
    if player is None:
        raise NOT_FOUND
    old = player.photo_key
    if old is None and player.profile_picture_url is None:
        return await _one(db, ctx, repo, player)
    player.photo_key, player.photo_updated_at, player.profile_picture_url = None, None, None
    await record_audit(
        db, action="player.photo_remove", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="player", target_id=str(player.id),
    )  # fmt: skip
    await db.commit()
    if old:
        store = media.storage()
        store.delete(old)
        store.delete(media.thumb_key(old))
    return await _one(db, ctx, repo, player)
