import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.errors import AppError
from app.db.session import get_db
from app.domain.football import POSITION_GROUPS
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.repositories.players import PlayerFilters
from app.schemas.common import Page, PageParams
from app.schemas.players import (
    CareerCreate,
    CareerOut,
    CareerUpdate,
    Foot,
    MediaCreate,
    MediaOut,
    PlayerCreate,
    PlayerOut,
    PlayerSummary,
    PlayerUpdate,
    Position,
)
from app.services import media, player_records, players

router = APIRouter(prefix="/players", tags=["players"])
read = require_permission(catalog.PLAYERS_READ)
write = require_permission(catalog.PLAYERS_WRITE)


@router.get("", response_model=Page[PlayerSummary])
async def search_players(
    q: str | None = Query(default=None, max_length=100),
    position: Position | None = None,
    group: Literal[tuple(POSITION_GROUPS)] | None = None,  # type: ignore[valid-type]
    nationality: str | None = Query(default=None, max_length=100),
    foot: Foot | None = None,
    min_age: int | None = Query(default=None, ge=8, le=60),
    max_age: int | None = Query(default=None, ge=8, le=60),
    min_height: int | None = Query(default=None, ge=100, le=250),
    max_height: int | None = Query(default=None, ge=100, le=250),
    club_id: uuid.UUID | None = None,
    team_id: uuid.UUID | None = None,
    scope: Literal["all", "mine", "network"] = "all",
    sort: Literal["name", "age_asc", "age_desc", "newest"] = "name",
    page: PageParams = Depends(),
    ctx: AuthContext = Depends(read),
    db: AsyncSession = Depends(get_db),
):
    filters = PlayerFilters(
        q=q, position=position, group=group, nationality=nationality, foot=foot,
        min_age=min_age, max_age=max_age, min_height=min_height, max_height=max_height,
        club_id=club_id, team_id=team_id, scope=scope, sort=sort,
    )  # fmt: skip
    return await players.list_players(db, ctx, filters, page)


@router.post("", response_model=PlayerOut, status_code=201)
async def create_player(
    body: PlayerCreate, ctx: AuthContext = Depends(write), db: AsyncSession = Depends(get_db)
):
    return await players.create_player(db, ctx, body)


@router.get("/{player_id}", response_model=PlayerOut)
async def get_player(
    player_id: uuid.UUID, ctx: AuthContext = Depends(read), db: AsyncSession = Depends(get_db)
):
    return await players.get_player(db, ctx, player_id)


@router.patch("/{player_id}", response_model=PlayerOut)
async def update_player(
    player_id: uuid.UUID,
    body: PlayerUpdate,
    ctx: AuthContext = Depends(write),
    db: AsyncSession = Depends(get_db),
):
    return await players.update_player(db, ctx, player_id, body)


@router.delete("/{player_id}", status_code=204)
async def archive_player(
    player_id: uuid.UUID, ctx: AuthContext = Depends(write), db: AsyncSession = Depends(get_db)
):
    await players.archive_player(db, ctx, player_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- career --------------------------------------------------------------------------
@router.get("/{player_id}/career", response_model=list[CareerOut])
async def list_career(
    player_id: uuid.UUID, ctx: AuthContext = Depends(read), db: AsyncSession = Depends(get_db)
):
    return await player_records.list_career(db, ctx, player_id)


@router.post("/{player_id}/career", response_model=CareerOut, status_code=201)
async def add_career(
    player_id: uuid.UUID,
    body: CareerCreate,
    ctx: AuthContext = Depends(write),
    db: AsyncSession = Depends(get_db),
):
    return await player_records.add_career(db, ctx, player_id, body)


@router.patch("/{player_id}/career/{entry_id}", response_model=CareerOut)
async def update_career(
    player_id: uuid.UUID,
    entry_id: uuid.UUID,
    body: CareerUpdate,
    ctx: AuthContext = Depends(write),
    db: AsyncSession = Depends(get_db),
):
    return await player_records.update_career(db, ctx, player_id, entry_id, body)


@router.delete("/{player_id}/career/{entry_id}", status_code=204)
async def delete_career(
    player_id: uuid.UUID,
    entry_id: uuid.UUID,
    ctx: AuthContext = Depends(write),
    db: AsyncSession = Depends(get_db),
):
    await player_records.delete_career(db, ctx, player_id, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- media ---------------------------------------------------------------------------
@router.get("/{player_id}/media", response_model=list[MediaOut])
async def list_media(
    player_id: uuid.UUID, ctx: AuthContext = Depends(read), db: AsyncSession = Depends(get_db)
):
    return await player_records.list_media(db, ctx, player_id)


@router.post("/{player_id}/media", response_model=MediaOut, status_code=201)
async def add_media(
    player_id: uuid.UUID,
    body: MediaCreate,
    ctx: AuthContext = Depends(write),
    db: AsyncSession = Depends(get_db),
):
    return await player_records.add_media(db, ctx, player_id, body)


@router.delete("/{player_id}/media/{media_id}", status_code=204)
async def delete_media(
    player_id: uuid.UUID,
    media_id: uuid.UUID,
    ctx: AuthContext = Depends(write),
    db: AsyncSession = Depends(get_db),
):
    await player_records.delete_media(db, ctx, player_id, media_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{player_id}/photo", response_model=PlayerOut)
async def upload_photo(
    player_id: uuid.UUID,
    file: UploadFile = File(...),
    crop_x: int | None = Form(default=None, ge=0),
    crop_y: int | None = Form(default=None, ge=0),
    crop_size: int | None = Form(default=None, ge=1),
    ctx: AuthContext = Depends(write),
    db: AsyncSession = Depends(get_db),
):
    """Multipart upload. Optional crop (pixels of the upright original) selects the square."""
    limit = media.get_settings().photo_max_bytes
    data = await file.read(limit + 1)
    crop = None
    if crop_x is not None and crop_y is not None and crop_size is not None:
        crop = media.Crop(crop_x, crop_y, crop_size)
    elif crop_x is not None or crop_y is not None or crop_size is not None:
        raise AppError(422, "invalid_crop", "Send crop_x, crop_y and crop_size together")
    return await players.set_photo(db, ctx, player_id, data, crop)


@router.delete("/{player_id}/photo", response_model=PlayerOut)
async def delete_photo(
    player_id: uuid.UUID,
    ctx: AuthContext = Depends(write),
    db: AsyncSession = Depends(get_db),
):
    return await players.remove_photo(db, ctx, player_id)
