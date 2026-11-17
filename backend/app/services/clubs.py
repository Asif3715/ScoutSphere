import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.club import Club
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.repositories.clubs import ClubRepository
from app.schemas.clubs import ClubCreate, ClubOut, ClubUpdate
from app.schemas.common import Page, PageParams
from app.services.audit import record_audit

NOT_FOUND = AppError(404, "not_found", "Club not found")
DUPLICATE = AppError(409, "club_exists", "Your organization already has a club with this name")


def to_out(club: Club) -> ClubOut:
    out = ClubOut.model_validate(club)
    out.is_reference = club.organization_id is None
    return out


async def list_clubs(
    db: AsyncSession,
    ctx: AuthContext,
    page: PageParams,
    scope: str,
    q: str | None,
    country: str | None,
) -> Page[ClubOut]:
    ctx.require(catalog.CLUBS_READ)
    repo = ClubRepository(db, ctx)
    fetch = repo.list_reference if scope == "reference" else repo.list_managed
    items, total = await fetch(page, q, country)
    return Page(
        items=[to_out(c) for c in items], total=total, page=page.page, page_size=page.page_size
    )


async def get_club(db: AsyncSession, ctx: AuthContext, club_id: uuid.UUID) -> ClubOut:
    ctx.require(catalog.CLUBS_READ)
    club = await ClubRepository(db, ctx).get_visible(club_id)
    if club is None:  # not found and "belongs to another tenant" are indistinguishable
        raise NOT_FOUND
    return to_out(club)


async def create_club(db: AsyncSession, ctx: AuthContext, data: ClubCreate) -> ClubOut:
    ctx.require(catalog.CLUBS_MANAGE)
    club = Club(organization_id=ctx.require_org(), **data.model_dump())
    db.add(club)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise DUPLICATE from None
    await record_audit(
        db, action="club.create", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="club", target_id=str(club.id),
    )  # fmt: skip
    await db.commit()
    return to_out(club)


async def update_club(
    db: AsyncSession, ctx: AuthContext, club_id: uuid.UUID, data: ClubUpdate
) -> ClubOut:
    ctx.require(catalog.CLUBS_MANAGE)
    club = await ClubRepository(db, ctx).get_managed(club_id)
    if club is None:  # reference clubs and other tenants' clubs cannot be edited
        raise NOT_FOUND
    changes = data.model_dump(exclude_unset=True)
    if changes.get("name", "x") is None:
        raise AppError(422, "validation_error", "Name cannot be empty")
    for field, value in changes.items():
        setattr(club, field, value)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise DUPLICATE from None
    await record_audit(
        db, action="club.update", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="club", target_id=str(club.id),
        metadata={"fields": sorted(changes)},
    )  # fmt: skip
    await db.commit()
    return to_out(club)


async def archive_club(db: AsyncSession, ctx: AuthContext, club_id: uuid.UUID) -> None:
    """Soft delete: history (players, matches) will reference the club, so rows are kept."""
    ctx.require(catalog.CLUBS_MANAGE)
    club = await ClubRepository(db, ctx).get_managed(club_id)
    if club is None:
        raise NOT_FOUND
    club.archived_at = datetime.now(UTC)
    await record_audit(
        db, action="club.archive", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="club", target_id=str(club.id),
    )  # fmt: skip
    await db.commit()


async def create_reference_club(db: AsyncSession, ctx: AuthContext, data: ClubCreate) -> ClubOut:
    """Platform staff maintain the global directory of reference clubs."""
    ctx.require(catalog.PLATFORM_ORGS_MANAGE)
    club = Club(organization_id=None, **data.model_dump())
    db.add(club)
    await db.flush()
    await record_audit(
        db, action="club.create_reference", outcome="success", actor_user_id=ctx.user_id,
        target_type="club", target_id=str(club.id),
    )  # fmt: skip
    await db.commit()
    return to_out(club)
