import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scoped
from app.db.session import get_db
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.schemas.common import Page, PageParams
from app.schemas.competitions import (
    CompetitionCreate,
    CompetitionDetail,
    CompetitionOut,
    CompetitionType,
    CompetitionUpdate,
    ParticipantAdd,
    SeasonCreate,
    SeasonDetail,
    SeasonOut,
    SeasonUpdate,
)
from app.services import competitions

router = APIRouter(tags=["competitions"])
read = require_scoped(catalog.MATCHES_READ)
manage = require_scoped(catalog.MATCHES_MANAGE)


@router.get("/competitions", response_model=Page[CompetitionOut])
async def list_competitions(
    q: str | None = Query(default=None, max_length=100),
    country: str | None = Query(default=None, max_length=100),
    type: CompetitionType | None = None,
    page: PageParams = Depends(),
    ctx: AuthContext = Depends(read),
    db: AsyncSession = Depends(get_db),
):
    return await competitions.list_competitions(db, ctx, page, q, country, type)


@router.post("/competitions", response_model=CompetitionOut, status_code=201)
async def create_competition(
    body: CompetitionCreate, ctx: AuthContext = Depends(manage), db: AsyncSession = Depends(get_db)
):
    return await competitions.create_competition(db, ctx, body)


@router.get("/competitions/{competition_id}", response_model=CompetitionDetail)
async def get_competition(
    competition_id: uuid.UUID, ctx: AuthContext = Depends(read), db: AsyncSession = Depends(get_db)
):
    return await competitions.get_competition(db, ctx, competition_id)


@router.patch("/competitions/{competition_id}", response_model=CompetitionOut)
async def update_competition(
    competition_id: uuid.UUID,
    body: CompetitionUpdate,
    ctx: AuthContext = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await competitions.update_competition(db, ctx, competition_id, body)


@router.delete("/competitions/{competition_id}", status_code=204)
async def archive_competition(
    competition_id: uuid.UUID,
    ctx: AuthContext = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    await competitions.archive_competition(db, ctx, competition_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/competitions/{competition_id}/seasons", response_model=SeasonOut, status_code=201)
async def create_season(
    competition_id: uuid.UUID,
    body: SeasonCreate,
    ctx: AuthContext = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await competitions.create_season(db, ctx, competition_id, body)


@router.get("/seasons/{season_id}", response_model=SeasonDetail)
async def get_season(
    season_id: uuid.UUID, ctx: AuthContext = Depends(read), db: AsyncSession = Depends(get_db)
):
    return await competitions.get_season(db, ctx, season_id)


@router.patch("/seasons/{season_id}", response_model=SeasonOut)
async def update_season(
    season_id: uuid.UUID,
    body: SeasonUpdate,
    ctx: AuthContext = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await competitions.update_season(db, ctx, season_id, body)


@router.delete("/seasons/{season_id}", status_code=204)
async def delete_season(
    season_id: uuid.UUID, ctx: AuthContext = Depends(manage), db: AsyncSession = Depends(get_db)
):
    await competitions.delete_season(db, ctx, season_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/seasons/{season_id}/participants", response_model=SeasonDetail, status_code=201)
async def add_participant(
    season_id: uuid.UUID,
    body: ParticipantAdd,
    ctx: AuthContext = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await competitions.add_participant(db, ctx, season_id, body.club_id)


@router.delete("/seasons/{season_id}/participants/{club_id}", response_model=SeasonDetail)
async def remove_participant(
    season_id: uuid.UUID,
    club_id: uuid.UUID,
    ctx: AuthContext = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await competitions.remove_participant(db, ctx, season_id, club_id)
