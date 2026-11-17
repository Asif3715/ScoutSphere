import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scoped
from app.db.session import get_db
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.schemas.common import Page, PageParams
from app.schemas.matches import (
    EventCreate,
    MatchCreate,
    MatchDetail,
    MatchFilters,
    MatchOut,
    MatchStatus,
    MatchUpdate,
    StatsBody,
)
from app.services import matches

router = APIRouter(prefix="/matches", tags=["matches"])
read = require_scoped(catalog.MATCHES_READ)
manage = require_scoped(catalog.MATCHES_MANAGE)


@router.get("", response_model=Page[MatchOut])
async def list_matches(
    competition_id: uuid.UUID | None = None,
    season_id: uuid.UUID | None = None,
    club_id: uuid.UUID | None = None,
    status: MatchStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: Literal["kickoff_desc", "kickoff_asc"] = "kickoff_desc",
    page: PageParams = Depends(),
    ctx: AuthContext = Depends(read),
    db: AsyncSession = Depends(get_db),
):
    filters = MatchFilters(
        competition_id=competition_id, season_id=season_id, club_id=club_id, status=status,
        date_from=date_from, date_to=date_to, sort=sort,
    )  # fmt: skip
    return await matches.list_matches(db, ctx, filters, page)


@router.post("", response_model=MatchDetail, status_code=201)
async def create_match(
    body: MatchCreate, ctx: AuthContext = Depends(manage), db: AsyncSession = Depends(get_db)
):
    return await matches.create_match(db, ctx, body)


@router.get("/{match_id}", response_model=MatchDetail)
async def get_match(
    match_id: uuid.UUID, ctx: AuthContext = Depends(read), db: AsyncSession = Depends(get_db)
):
    return await matches.get_match(db, ctx, match_id)


@router.patch("/{match_id}", response_model=MatchDetail)
async def update_match(
    match_id: uuid.UUID,
    body: MatchUpdate,
    ctx: AuthContext = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await matches.update_match(db, ctx, match_id, body)


@router.delete("/{match_id}", status_code=204)
async def delete_match(
    match_id: uuid.UUID, ctx: AuthContext = Depends(manage), db: AsyncSession = Depends(get_db)
):
    await matches.delete_match(db, ctx, match_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{match_id}/events", response_model=MatchDetail, status_code=201)
async def add_event(
    match_id: uuid.UUID,
    body: EventCreate,
    ctx: AuthContext = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await matches.add_event(db, ctx, match_id, body)


@router.delete("/{match_id}/events/{event_id}", response_model=MatchDetail)
async def delete_event(
    match_id: uuid.UUID,
    event_id: uuid.UUID,
    ctx: AuthContext = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await matches.delete_event(db, ctx, match_id, event_id)


@router.put("/{match_id}/statistics", response_model=MatchDetail)
async def put_statistics(
    match_id: uuid.UUID,
    body: StatsBody,
    ctx: AuthContext = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await matches.put_statistics(db, ctx, match_id, body)
