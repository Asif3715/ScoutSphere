import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_auth_context
from app.core.errors import AppError
from app.db.session import get_db
from app.permissions.context import AuthContext
from app.schemas.common import Page, PageParams
from app.schemas.recruitment import (
    CompareOut,
    SharesBody,
    ShortlistCreate,
    ShortlistDetail,
    ShortlistPlayerAdd,
    ShortlistPlayerUpdate,
    ShortlistSummary,
    ShortlistUpdate,
)
from app.services import comparison, shortlists

router = APIRouter(prefix="/recruitment/shortlists", tags=["shortlists"])
Ctx = Depends(get_auth_context)
Db = Depends(get_db)


@router.get("", response_model=Page[ShortlistSummary])
async def list_shortlists(
    scope: Literal["all", "mine", "shared"] = "all",
    q: str | None = Query(default=None, max_length=100),
    page: PageParams = Depends(),
    ctx: AuthContext = Ctx,
    db: AsyncSession = Db,
):
    return await shortlists.list_shortlists(db, ctx, page, scope, q)


@router.post("", response_model=ShortlistDetail, status_code=201)
async def create_shortlist(body: ShortlistCreate, ctx: AuthContext = Ctx, db: AsyncSession = Db):
    return await shortlists.create_shortlist(db, ctx, body)


@router.get("/{shortlist_id}", response_model=ShortlistDetail)
async def get_shortlist(shortlist_id: uuid.UUID, ctx: AuthContext = Ctx, db: AsyncSession = Db):
    return await shortlists.get_shortlist(db, ctx, shortlist_id)


@router.patch("/{shortlist_id}", response_model=ShortlistDetail)
async def update_shortlist(
    shortlist_id: uuid.UUID, body: ShortlistUpdate, ctx: AuthContext = Ctx, db: AsyncSession = Db
):
    return await shortlists.update_shortlist(db, ctx, shortlist_id, body)


@router.delete("/{shortlist_id}", status_code=204)
async def delete_shortlist(shortlist_id: uuid.UUID, ctx: AuthContext = Ctx, db: AsyncSession = Db):
    await shortlists.delete_shortlist(db, ctx, shortlist_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{shortlist_id}/players", response_model=ShortlistDetail, status_code=201)
async def add_player(
    shortlist_id: uuid.UUID, body: ShortlistPlayerAdd, ctx: AuthContext = Ctx, db: AsyncSession = Db
):
    return await shortlists.add_player(db, ctx, shortlist_id, body)


@router.patch("/{shortlist_id}/players/{player_id}", response_model=ShortlistDetail)
async def update_player(
    shortlist_id: uuid.UUID,
    player_id: uuid.UUID,
    body: ShortlistPlayerUpdate,
    ctx: AuthContext = Ctx,
    db: AsyncSession = Db,
):
    return await shortlists.update_player(db, ctx, shortlist_id, player_id, body)


@router.delete("/{shortlist_id}/players/{player_id}", response_model=ShortlistDetail)
async def remove_player(
    shortlist_id: uuid.UUID, player_id: uuid.UUID, ctx: AuthContext = Ctx, db: AsyncSession = Db
):
    return await shortlists.remove_player(db, ctx, shortlist_id, player_id)


@router.put("/{shortlist_id}/shares", response_model=ShortlistDetail)
async def set_shares(
    shortlist_id: uuid.UUID, body: SharesBody, ctx: AuthContext = Ctx, db: AsyncSession = Db
):
    return await shortlists.set_shares(db, ctx, shortlist_id, body.user_ids)


@router.get("/{shortlist_id}/compare", response_model=CompareOut)
async def compare_shortlist(
    shortlist_id: uuid.UUID,
    requirement_id: uuid.UUID | None = None,
    ctx: AuthContext = Ctx,
    db: AsyncSession = Db,
):
    """Compares everyone on the shortlist (2 to 5 players)."""
    detail = await shortlists.get_shortlist(db, ctx, shortlist_id)
    ids = [p.player.id for p in detail.players]
    if not 2 <= len(ids) <= 5:
        raise AppError(
            422, "invalid_selection", "A shortlist can be compared when it has 2 to 5 players"
        )
    return await comparison.compare_players(db, ctx, ids, requirement_id)
