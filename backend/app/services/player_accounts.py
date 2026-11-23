"""Player accounts: claiming an existing player record, and the player's own profile.

A player account is a person, not a club. It starts with nothing; it gains a profile only when
the organization that owns a player record approves a claim. After that the player can edit a
small, safe set of fields and decides who may find them. Everything club-owned (contract,
medical notes, scouting reports, recruitment) stays out of reach of this module.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domain.football import age_on, is_minor
from app.models.club import Club
from app.models.notification import Notification
from app.models.organization import Organization, OrganizationMember
from app.models.player import Player, PlayerCareer, PlayerClaim, PlayerPosition
from app.models.rbac import Role
from app.models.user import User
from app.permissions import catalog
from app.permissions.catalog import ROLES
from app.permissions.context import AuthContext
from app.repositories.clubs import escape_like
from app.schemas.player_accounts import (
    CareerSpell,
    ClaimableOut,
    ClaimCreate,
    ClaimDecision,
    MyClaimOut,
    OrgClaimOut,
    SelfProfile,
    SelfUpdate,
)
from app.schemas.players import CurrentClub
from app.services import media
from app.services.audit import record_audit
from app.services.notifications import notify
from app.services.players import _photo

NO_PROFILE = AppError(404, "no_profile", "Your account is not linked to a player profile yet")
NOT_FOUND = AppError(404, "not_found", "Player not found")


def _require_player_account(user: User) -> None:
    if user.account_type != "player":
        raise AppError(
            403, "account_type_not_allowed", "Only player accounts can claim a player profile"
        )


async def _current_club(db: AsyncSession, player_id: uuid.UUID) -> CurrentClub | None:
    row = (
        await db.execute(
            select(Club.id, Club.name)
            .join(PlayerCareer, PlayerCareer.club_id == Club.id)
            .where(PlayerCareer.player_id == player_id, PlayerCareer.end_date.is_(None))
            .order_by(PlayerCareer.start_date.desc())
            .limit(1)
        )
    ).first()
    return CurrentClub(club_id=row[0], club_name=row[1]) if row else None


async def _org_name(db: AsyncSession, org_id: uuid.UUID | None) -> str | None:
    if org_id is None:
        return None
    return await db.scalar(select(Organization.name).where(Organization.id == org_id))


async def _reviewers(db: AsyncSession, org_id: uuid.UUID) -> list[uuid.UUID]:
    """Members of the organization who may approve claims (those who can edit players)."""
    keys = [k for k, (_, scope, perms) in ROLES.items() if catalog.PLAYERS_WRITE in perms]
    rows = await db.scalars(
        select(OrganizationMember.user_id)
        .join(Role, Role.id == OrganizationMember.role_id)
        .where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.status == "active",
            Role.key.in_(keys),
        )
    )
    return list(rows)


# ---- finding and claiming a profile ----------------------------------------------------
async def search_claimable(
    db: AsyncSession, user: User, name: str, date_of_birth: date
) -> list[ClaimableOut]:
    """Unclaimed records matching BOTH a name and the exact date of birth. Requiring the date
    of birth means nobody can browse for people, and a stranger cannot find a profile."""
    _require_player_account(user)
    rows = (
        await db.scalars(
            select(Player)
            .join(Organization, Organization.id == Player.owner_organization_id)
            .where(
                Player.archived_at.is_(None),
                Player.claimed_by_user_id.is_(None),
                Player.date_of_birth == date_of_birth,
                Player.full_name.ilike(f"%{escape_like(name)}%", escape="\\"),
                Organization.status == "active",
            )
            .order_by(Player.full_name)
            .limit(10)
        )
    ).all()
    out = []
    for p in rows:
        out.append(
            ClaimableOut(
                player_id=p.id,
                full_name=p.full_name,
                age=age_on(p.date_of_birth),
                nationality=p.nationality,
                primary_position=p.primary_position,
                current_club=await _current_club(db, p.id),
                reviewed_by=await _org_name(db, p.owner_organization_id) or "the club",
            )  # fmt: skip
        )
    return out


async def create_claim(db: AsyncSession, user: User, data: ClaimCreate) -> MyClaimOut:
    _require_player_account(user)
    if await db.scalar(select(Player.id).where(Player.claimed_by_user_id == user.id)):
        raise AppError(409, "already_claimed", "Your account is already linked to a profile")
    if await db.scalar(
        select(PlayerClaim.id).where(
            PlayerClaim.user_id == user.id, PlayerClaim.status == "pending"
        )
    ):
        raise AppError(
            409, "claim_pending", "You already have a request waiting. Cancel it to send another."
        )
    player = await db.scalar(
        select(Player).where(
            Player.id == data.player_id,
            Player.archived_at.is_(None),
            Player.claimed_by_user_id.is_(None),
            Player.owner_organization_id.is_not(None),
            Player.date_of_birth == data.date_of_birth,
        )
    )
    # Unknown, archived, already claimed and wrong date of birth all look the same.
    if player is None:
        raise NOT_FOUND
    org_id = player.owner_organization_id
    claim = PlayerClaim(
        player_id=player.id, user_id=user.id, organization_id=org_id, message=data.message
    )
    try:
        async with db.begin_nested():
            db.add(claim)
            await db.flush()
    except IntegrityError:
        raise AppError(409, "claim_pending", "You already have a request waiting") from None
    for uid in await _reviewers(db, org_id):
        await notify(
            db, user_id=uid, type="player_claim_requested",
            title=f"{user.full_name} says they are {player.full_name}",
            body="Review the request to link this player to their own account.",
            link_path="/players/claims", organization_id=org_id,
        )  # fmt: skip
    await record_audit(
        db, action="player_claim.create", outcome="success", actor_user_id=user.id,
        organization_id=org_id, target_type="player", target_id=str(player.id),
    )  # fmt: skip
    await db.commit()
    return await _my_claim(db, claim, player.full_name)


async def _my_claim(db: AsyncSession, c: PlayerClaim, player_name: str | None = None) -> MyClaimOut:
    if player_name is None:
        player_name = await db.scalar(select(Player.full_name).where(Player.id == c.player_id))
    return MyClaimOut(
        id=c.id, status=c.status, player_id=c.player_id, player_name=player_name or "",
        reviewed_by=await _org_name(db, c.organization_id) or "the club", message=c.message,
        decision_note=c.decision_note, created_at=c.created_at, decided_at=c.decided_at,
    )  # fmt: skip


async def list_my_claims(db: AsyncSession, user: User) -> list[MyClaimOut]:
    _require_player_account(user)
    rows = await db.scalars(
        select(PlayerClaim)
        .where(PlayerClaim.user_id == user.id)
        .order_by(PlayerClaim.created_at.desc())
        .limit(20)
    )
    return [await _my_claim(db, c) for c in rows]


async def cancel_claim(db: AsyncSession, user: User, claim_id: uuid.UUID) -> MyClaimOut:
    c = await db.scalar(
        select(PlayerClaim)
        .where(PlayerClaim.id == claim_id, PlayerClaim.user_id == user.id)
        .with_for_update()
    )
    if c is None:
        raise AppError(404, "not_found", "Request not found")
    if c.status != "pending":
        raise AppError(409, "not_pending", "Only a waiting request can be cancelled")
    c.status = "cancelled"
    await db.commit()
    return await _my_claim(db, c)


# ---- the organization's side ------------------------------------------------------------
async def list_org_claims(
    db: AsyncSession, ctx: AuthContext, status: str | None
) -> list[OrgClaimOut]:
    ctx.require(catalog.PLAYERS_WRITE)
    stmt = select(PlayerClaim).where(PlayerClaim.organization_id == ctx.require_org())
    if status:
        stmt = stmt.where(PlayerClaim.status == status)
    claims = (await db.scalars(stmt.order_by(PlayerClaim.created_at.desc()).limit(100))).all()
    out = []
    for c in claims:
        player = await db.get(Player, c.player_id)
        who = await db.get(User, c.user_id)
        decider = await db.get(User, c.decided_by_user_id) if c.decided_by_user_id else None
        out.append(
            OrgClaimOut(
                id=c.id,
                status=c.status,
                created_at=c.created_at,
                message=c.message,
                requester_name=who.full_name,
                requester_email=who.email,
                player_id=player.id,
                player_name=player.full_name,
                player_age=age_on(player.date_of_birth),
                player_position=player.primary_position,
                decision_note=c.decision_note,
                decided_at=c.decided_at,
                decided_by_name=decider.full_name if decider else None,
            )  # fmt: skip
        )
    return out


async def decide_claim(
    db: AsyncSession, ctx: AuthContext, claim_id: uuid.UUID, data: ClaimDecision
) -> OrgClaimOut:
    ctx.require(catalog.PLAYERS_WRITE)
    org_id = ctx.require_org()
    c = await db.scalar(
        select(PlayerClaim)
        .where(PlayerClaim.id == claim_id, PlayerClaim.organization_id == org_id)
        .with_for_update()
    )
    if c is None:  # missing and "another organization's" look the same
        raise AppError(404, "not_found", "Request not found")
    if c.status != "pending":
        raise AppError(409, "not_pending", "This request has already been decided")
    note = data.note.strip() if data.note else None
    if data.decision == "rejected" and not note:
        raise AppError(422, "comment_required", "Tell them why, so they can try again correctly")

    player = await db.scalar(select(Player).where(Player.id == c.player_id).with_for_update())
    if data.decision == "approved":
        if player.claimed_by_user_id is not None or player.archived_at is not None:
            raise AppError(409, "already_claimed", "This profile can no longer be claimed")
        player.claimed_by_user_id = c.user_id
    c.status, c.decided_by_user_id = data.decision, ctx.user_id
    c.decided_at, c.decision_note = datetime.now(UTC), note

    if data.decision == "approved":
        # anyone else asking for the same profile is turned down with a clear reason
        others = await db.scalars(
            select(PlayerClaim).where(
                PlayerClaim.player_id == c.player_id,
                PlayerClaim.status == "pending",
                PlayerClaim.id != c.id,
            )
        )
        for o in others:
            o.status, o.decided_by_user_id = "rejected", ctx.user_id
            o.decided_at = c.decided_at
            o.decision_note = "This profile has been linked to another account."
            await notify(
                db, user_id=o.user_id, type="player_claim_rejected",
                title="Your profile request was declined", body=o.decision_note,
                link_path="/player",
            )  # fmt: skip
    await notify(
        db, user_id=c.user_id,
        type="player_claim_approved" if data.decision == "approved" else "player_claim_rejected",
        title=(
            f"You are now linked to {player.full_name}"
            if data.decision == "approved"
            else "Your profile request was declined"
        ),
        body=note, link_path="/player",
    )  # fmt: skip
    await record_audit(
        db, action=f"player_claim.{data.decision}", outcome="success", actor_user_id=ctx.user_id,
        organization_id=org_id, target_type="player", target_id=str(player.id),
        metadata={"claimant": str(c.user_id)},
    )  # fmt: skip
    try:
        await db.commit()
    except IntegrityError:  # this account was linked to another profile in the meantime
        await db.rollback()
        raise AppError(
            409, "already_claimed", "That account is already linked to another profile"
        ) from None
    return next(x for x in await list_org_claims(db, ctx, None) if x.id == claim_id)


# ---- telling the club what the player changed --------------------------------------------
_FIELD_LABELS = {
    "nationality": "nationality", "height_cm": "height", "weight_kg": "weight",
    "preferred_foot": "preferred foot", "primary_position": "main position",
    "secondary_positions": "other positions", "biography": "biography", "photo": "photo",
    "visibility": "visibility", "open_to_offers": "open to offers",
    "contact_email": "contact email",
}  # fmt: skip
_PREFIX = "Changed: "


async def _tell_owner(
    db: AsyncSession, player: Player, user: User, fields: list[str], extra: str | None = None
) -> None:
    """Notifies the owning organization's staff that the player edited their own profile.
    Quick successive edits fold into one unread notification instead of piling up."""
    org_id = player.owner_organization_id
    if org_id is None or not fields:
        return
    link = f"/players/{player.id}"
    labels = [_FIELD_LABELS.get(x, x) for x in fields]
    for uid in await _reviewers(db, org_id):
        merged, note = labels, extra
        previous = await db.scalar(
            select(Notification).where(
                Notification.user_id == uid,
                Notification.type == "player_profile_updated",
                Notification.link_path == link,
                Notification.read_at.is_(None),
            )
        )
        if previous is not None:
            if previous.body and previous.body.startswith(_PREFIX):
                head, _, tail = previous.body[len(_PREFIX) :].partition(" · ")
                merged = list(dict.fromkeys(head.split(", ") + labels))
                note = extra or tail or None
            await db.delete(previous)
        body = _PREFIX + ", ".join(merged) + (f" · {note}" if note else "")
        await notify(
            db, user_id=uid, type="player_profile_updated",
            title=f"{player.full_name} updated their own profile", body=body,
            link_path=link, organization_id=org_id,
        )  # fmt: skip


# ---- the player's own profile -----------------------------------------------------------
async def _own_player(db: AsyncSession, user: User, *, lock: bool = False) -> Player:
    stmt = select(Player).where(Player.claimed_by_user_id == user.id, Player.archived_at.is_(None))
    player = await db.scalar(stmt.with_for_update() if lock else stmt)
    if player is None:
        raise NO_PROFILE
    return player


async def _profile(db: AsyncSession, p: Player) -> SelfProfile:
    secs = list(
        await db.scalars(
            select(PlayerPosition.position)
            .where(PlayerPosition.player_id == p.id)
            .order_by(PlayerPosition.position)
        )
    )
    spells = (
        await db.execute(
            select(PlayerCareer, Club.name)
            .join(Club, Club.id == PlayerCareer.club_id)
            .where(PlayerCareer.player_id == p.id)
            .order_by(PlayerCareer.start_date.desc())
        )
    ).all()
    return SelfProfile(
        player_id=p.id, full_name=p.full_name, date_of_birth=p.date_of_birth,
        age=age_on(p.date_of_birth), is_minor=is_minor(p.date_of_birth),
        nationality=p.nationality, height_cm=p.height_cm, weight_kg=p.weight_kg,
        preferred_foot=p.preferred_foot, primary_position=p.primary_position,
        secondary_positions=secs, biography=p.biography,
        photo_url=_photo(p, thumb=False), photo_thumb_url=_photo(p, thumb=True),
        has_uploaded_photo=p.photo_key is not None, visibility=p.visibility,
        open_to_offers=p.open_to_offers, contact_email=p.contact_email,
        current_club=await _current_club(db, p.id),
        managed_by=await _org_name(db, p.owner_organization_id),
        career=[
            CareerSpell(
                club_name=name, team_label=sp.team_label, spell_type=sp.spell_type,
                start_date=sp.start_date, end_date=sp.end_date, appearances=sp.appearances,
                goals=sp.goals, assists=sp.assists,
            )
            for sp, name in spells
        ],
    )  # fmt: skip


async def get_self(db: AsyncSession, user: User) -> SelfProfile:
    _require_player_account(user)
    return await _profile(db, await _own_player(db, user))


# Settings that decide who can find or contact a person. A minor's stay with the club until a
# guardian-consent flow exists.
_GUARDED = ("visibility", "open_to_offers", "contact_email")


async def update_self(db: AsyncSession, user: User, data: SelfUpdate) -> SelfProfile:
    _require_player_account(user)
    player = await _own_player(db, user, lock=True)
    changes = data.model_dump(exclude_unset=True)
    if is_minor(player.date_of_birth) and any(k in changes for k in _GUARDED):
        raise AppError(
            403, "guardian_required",
            "Players under 18 can't change who sees or contacts them yet. "
            "Ask your club, who will check with your parent or guardian.",
        )  # fmt: skip
    if changes.get("open_to_offers") and not (changes.get("contact_email") or player.contact_email):
        raise AppError(422, "contact_required", "Add a contact email so clubs can reach you")
    secondaries = changes.pop("secondary_positions", None)
    old_visibility = player.visibility
    for field, value in changes.items():
        setattr(player, field, value)
    if secondaries is not None or "primary_position" in changes:
        keep = (
            secondaries
            if secondaries is not None
            else list(
                await db.scalars(
                    select(PlayerPosition.position).where(PlayerPosition.player_id == player.id)
                )
            )
        )
        keep = [s for s in dict.fromkeys(keep) if s != player.primary_position]
        await db.execute(delete(PlayerPosition).where(PlayerPosition.player_id == player.id))
        db.add_all(PlayerPosition(player_id=player.id, position=s) for s in keep)
    await record_audit(
        db, action="player.self_update", outcome="success", actor_user_id=user.id,
        organization_id=player.owner_organization_id, target_type="player",
        target_id=str(player.id),
        metadata={"fields": sorted(changes) + (["secondary_positions"] if secondaries else [])},
    )  # fmt: skip
    if player.visibility != old_visibility:
        await record_audit(
            db, action="player.set_visibility", outcome="success", actor_user_id=user.id,
            organization_id=player.owner_organization_id, target_type="player",
            target_id=str(player.id),
            metadata={"from": old_visibility, "to": player.visibility, "by": "player"},
        )  # fmt: skip
    touched = sorted(changes) + (["secondary_positions"] if secondaries is not None else [])
    note = None
    if player.visibility != old_visibility:
        note = (
            "now visible to every organization"
            if player.visibility == "network"
            else "now visible to the club only"
        )
    await _tell_owner(db, player, user, touched, note)
    await db.commit()
    return await _profile(db, player)


async def set_self_photo(
    db: AsyncSession, user: User, data: bytes, crop: media.Crop | None
) -> SelfProfile:
    _require_player_account(user)
    player = await _own_player(db, user, lock=True)
    full, thumb = media.process_photo(data, crop)  # validates before anything is written
    store = media.storage()
    key, tkey = media.new_photo_keys(player.id)
    store.save(key, full)
    store.save(tkey, thumb)
    old = player.photo_key
    player.photo_key, player.photo_updated_at = key, datetime.now(UTC)
    await record_audit(
        db, action="player.photo_update", outcome="success", actor_user_id=user.id,
        organization_id=player.owner_organization_id, target_type="player",
        target_id=str(player.id), metadata={"bytes": len(data), "by": "player"},
    )  # fmt: skip
    await _tell_owner(db, player, user, ["photo"])
    try:
        await db.commit()
    except Exception:
        store.delete(key)
        store.delete(tkey)
        raise
    if old:
        store.delete(old)
        store.delete(media.thumb_key(old))
    return await _profile(db, player)


async def remove_self_photo(db: AsyncSession, user: User) -> SelfProfile:
    _require_player_account(user)
    player = await _own_player(db, user, lock=True)
    old = player.photo_key
    if old is not None or player.profile_picture_url is not None:
        player.photo_key, player.photo_updated_at, player.profile_picture_url = None, None, None
        await record_audit(
            db, action="player.photo_remove", outcome="success", actor_user_id=user.id,
            organization_id=player.owner_organization_id, target_type="player",
            target_id=str(player.id), metadata={"by": "player"},
        )  # fmt: skip
        await _tell_owner(db, player, user, ["photo"], "removed")
        await db.commit()
        if old:
            store = media.storage()
            store.delete(old)
            store.delete(media.thumb_key(old))
    return await _profile(db, player)
