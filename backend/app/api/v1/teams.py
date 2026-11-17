import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.db.session import get_db
from app.domain.football import POSITION_GROUPS
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.schemas.teams import (
    SquadAdd,
    SquadOut,
    SquadUpdate,
    TeamCreate,
    TeamOut,
    TeamUpdate,
)
from app.services import teams

router = APIRouter(prefix="/teams", tags=["teams"])
read = require_permission(catalog.CLUBS_READ)
manage = require_permission(catalog.CLUBS_MANAGE)


class TransferBody(BaseModel):
    to_team_id: uuid.UUID
    squad_number: int | None = Field(default=None, ge=1, le=99)


@router.get("", response_model=list[TeamOut])
async def list_teams(
    club_id: uuid.UUID | None = None,
    ctx: AuthContext = Depends(read),
    db: AsyncSession = Depends(get_db),
):
    return await teams.list_teams(db, ctx, club_id)


@router.post("", response_model=TeamOut, status_code=201)
async def create_team(
    body: TeamCreate, ctx: AuthContext = Depends(manage), db: AsyncSession = Depends(get_db)
):
    return await teams.create_team(db, ctx, body)


@router.get("/{team_id}", response_model=TeamOut)
async def get_team(
    team_id: uuid.UUID, ctx: AuthContext = Depends(read), db: AsyncSession = Depends(get_db)
):
    return await teams.get_team(db, ctx, team_id)


@router.patch("/{team_id}", response_model=TeamOut)
async def update_team(
    team_id: uuid.UUID,
    body: TeamUpdate,
    ctx: AuthContext = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await teams.update_team(db, ctx, team_id, body)


@router.delete("/{team_id}", status_code=204)
async def archive_team(
    team_id: uuid.UUID, ctx: AuthContext = Depends(manage), db: AsyncSession = Depends(get_db)
):
    await teams.archive_team(db, ctx, team_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{team_id}/squad", response_model=SquadOut)
async def squad(
    team_id: uuid.UUID,
    include_left: bool = False,
    group: Literal[tuple(POSITION_GROUPS)] | None = None,  # type: ignore[valid-type]
    ctx: AuthContext = Depends(read),
    db: AsyncSession = Depends(get_db),
):
    return await teams.squad(db, ctx, team_id, include_left, group)


@router.post("/{team_id}/players", response_model=SquadOut, status_code=201)
async def add_player(
    team_id: uuid.UUID,
    body: SquadAdd,
    ctx: AuthContext = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await teams.add_to_squad(db, ctx, team_id, body)


@router.patch("/{team_id}/players/{membership_id}", response_model=SquadOut)
async def update_member(
    team_id: uuid.UUID,
    membership_id: uuid.UUID,
    body: SquadUpdate,
    ctx: AuthContext = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await teams.update_squad_member(db, ctx, team_id, membership_id, body)


@router.delete("/{team_id}/players/{membership_id}", response_model=SquadOut)
async def release_player(
    team_id: uuid.UUID,
    membership_id: uuid.UUID,
    ctx: AuthContext = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await teams.release_from_squad(db, ctx, team_id, membership_id)


@router.post("/{team_id}/players/{membership_id}/transfer", response_model=SquadOut)
async def transfer_player(
    team_id: uuid.UUID,
    membership_id: uuid.UUID,
    body: TransferBody,
    ctx: AuthContext = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await teams.transfer_squad_member(
        db, ctx, team_id, membership_id, body.to_team_id, body.squad_number
    )
