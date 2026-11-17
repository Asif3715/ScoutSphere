import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_auth_context
from app.db.session import get_db
from app.permissions.context import AuthContext
from app.schemas.common import Page, PageParams
from app.schemas.players import Position
from app.schemas.scouts import AgeGroup, ScoutCreate, ScoutOut, ScoutUpdate
from app.services import scouts

router = APIRouter(prefix="/scouts", tags=["scouts"])
# Permission checks live in the service (so the AI agent gets the same ones); the context
# dependency still verifies organization membership.


@router.get("", response_model=Page[ScoutOut])
async def list_scouts(
    q: str | None = Query(default=None, max_length=100),
    position: Position | None = None,
    age_group: AgeGroup | None = None,
    region: str | None = Query(default=None, max_length=100),
    min_experience: int | None = Query(default=None, ge=0, le=60),
    status: Literal["active", "inactive", "all"] = "active",
    page: PageParams = Depends(),
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    active = {"active": True, "inactive": False, "all": None}[status]
    return await scouts.list_scouts(
        db, ctx, page, q=q, position=position, age_group=age_group, region=region,
        min_experience=min_experience, active=active,
    )  # fmt: skip


@router.post("", response_model=ScoutOut, status_code=201)
async def create_scout(
    body: ScoutCreate,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    return await scouts.create_scout(db, ctx, body)


@router.get("/{scout_id}", response_model=ScoutOut)
async def get_scout(
    scout_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    return await scouts.get_scout(db, ctx, scout_id)


@router.patch("/{scout_id}", response_model=ScoutOut)
async def update_scout(
    scout_id: uuid.UUID,
    body: ScoutUpdate,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    return await scouts.update_scout(db, ctx, scout_id, body)
