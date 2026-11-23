import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_permission
from app.core.errors import AppError
from app.db.session import get_db
from app.models.user import User
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.schemas.player_accounts import (
    ClaimableOut,
    ClaimCreate,
    ClaimDecision,
    MyClaimOut,
    OrgClaimOut,
    SelfProfile,
    SelfUpdate,
)
from app.services import media, player_accounts

# The player's own side: needs a signed-in player account, no organization.
me = APIRouter(prefix="/me/player", tags=["player account"])

# The organization's side: reviewing claims on the players it owns.
claims = APIRouter(prefix="/player-claims", tags=["player account"])
write = require_permission(catalog.PLAYERS_WRITE)


@me.get("", response_model=SelfProfile)
async def my_profile(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await player_accounts.get_self(db, user)


@me.patch("", response_model=SelfProfile)
async def update_my_profile(
    body: SelfUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await player_accounts.update_self(db, user, body)


@me.put("/photo", response_model=SelfProfile)
async def upload_my_photo(
    file: UploadFile = File(...),
    crop_x: int | None = Form(default=None, ge=0),
    crop_y: int | None = Form(default=None, ge=0),
    crop_size: int | None = Form(default=None, ge=1),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await file.read(media.get_settings().photo_max_bytes + 1)
    crop = None
    if crop_x is not None or crop_y is not None or crop_size is not None:
        if None in (crop_x, crop_y, crop_size):
            raise AppError(422, "invalid_crop", "Send crop_x, crop_y and crop_size together")
        crop = media.Crop(crop_x, crop_y, crop_size)
    return await player_accounts.set_self_photo(db, user, data, crop)


@me.delete("/photo", response_model=SelfProfile)
async def delete_my_photo(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await player_accounts.remove_self_photo(db, user)


@me.get("/search", response_model=list[ClaimableOut])
async def find_my_profile(
    name: str = Query(min_length=2, max_length=100),
    date_of_birth: date = Query(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await player_accounts.search_claimable(db, user, name.strip(), date_of_birth)


@me.get("/claims", response_model=list[MyClaimOut])
async def my_claims(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await player_accounts.list_my_claims(db, user)


@me.post("/claims", response_model=MyClaimOut, status_code=201)
async def claim_profile(
    body: ClaimCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await player_accounts.create_claim(db, user, body)


@me.delete("/claims/{claim_id}", response_model=MyClaimOut)
async def cancel_my_claim(
    claim_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await player_accounts.cancel_claim(db, user, claim_id)


@claims.get("", response_model=list[OrgClaimOut])
async def list_claims(
    status: Literal["pending", "approved", "rejected", "cancelled"] | None = "pending",
    ctx: AuthContext = Depends(write),
    db: AsyncSession = Depends(get_db),
):
    return await player_accounts.list_org_claims(db, ctx, status)


@claims.post("/{claim_id}/decision", response_model=OrgClaimOut)
async def decide_claim(
    claim_id: uuid.UUID,
    body: ClaimDecision,
    ctx: AuthContext = Depends(write),
    db: AsyncSession = Depends(get_db),
):
    return await player_accounts.decide_claim(db, ctx, claim_id, body)
