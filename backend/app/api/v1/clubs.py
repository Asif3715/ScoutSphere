import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.db.session import get_db
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.schemas.clubs import ClubCreate, ClubOut, ClubUpdate
from app.schemas.common import Page, PageParams
from app.services import clubs

router = APIRouter(prefix="/clubs", tags=["clubs"])


@router.get("", response_model=Page[ClubOut])
async def list_clubs(
    scope: Literal["mine", "reference"] = "mine",
    q: str | None = Query(default=None, max_length=100),
    country: str | None = Query(default=None, max_length=100),
    page: PageParams = Depends(),
    ctx: AuthContext = Depends(require_permission(catalog.CLUBS_READ)),
    db: AsyncSession = Depends(get_db),
):
    return await clubs.list_clubs(db, ctx, page, scope, q, country)


@router.post("", response_model=ClubOut, status_code=201)
async def create_club(
    body: ClubCreate,
    ctx: AuthContext = Depends(require_permission(catalog.CLUBS_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    return await clubs.create_club(db, ctx, body)


@router.get("/{club_id}", response_model=ClubOut)
async def get_club(
    club_id: uuid.UUID,
    ctx: AuthContext = Depends(require_permission(catalog.CLUBS_READ)),
    db: AsyncSession = Depends(get_db),
):
    return await clubs.get_club(db, ctx, club_id)


@router.patch("/{club_id}", response_model=ClubOut)
async def update_club(
    club_id: uuid.UUID,
    body: ClubUpdate,
    ctx: AuthContext = Depends(require_permission(catalog.CLUBS_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    return await clubs.update_club(db, ctx, club_id, body)


@router.delete("/{club_id}", status_code=204)
async def archive_club(
    club_id: uuid.UUID,
    ctx: AuthContext = Depends(require_permission(catalog.CLUBS_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    await clubs.archive_club(db, ctx, club_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
