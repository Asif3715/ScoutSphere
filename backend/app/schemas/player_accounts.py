import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.base import RequestModel
from app.schemas.players import CurrentClub, Foot, Position


class ClaimCreate(RequestModel):
    player_id: uuid.UUID
    # Proof that you know the person: must match the record. Wrong answers look like "not found".
    date_of_birth: date
    message: str | None = Field(default=None, max_length=500)


class ClaimDecision(RequestModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=500)


class SelfUpdate(RequestModel):
    """What a player may change about their own profile. Name and date of birth stay with the
    club (they are how identity is checked); contract, medical and scouting data are not here."""

    nationality: str | None = Field(default=None, max_length=100)
    height_cm: int | None = Field(default=None, ge=120, le=230)
    weight_kg: int | None = Field(default=None, ge=30, le=160)
    preferred_foot: Foot | None = None
    primary_position: Position | None = None
    secondary_positions: list[Position] | None = Field(default=None, max_length=4)
    biography: str | None = Field(default=None, max_length=5000)
    visibility: Literal["private", "network"] | None = None
    open_to_offers: bool | None = None
    contact_email: EmailStr | None = None

    @field_validator("secondary_positions")
    @classmethod
    def _dedupe(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else list(dict.fromkeys(v))


class ClaimableOut(BaseModel):
    player_id: uuid.UUID
    full_name: str
    age: int
    nationality: str | None
    primary_position: str | None
    current_club: CurrentClub | None
    reviewed_by: str  # the organization that will review the request


class MyClaimOut(BaseModel):
    id: uuid.UUID
    status: str
    player_id: uuid.UUID
    player_name: str
    reviewed_by: str
    message: str | None
    decision_note: str | None
    created_at: datetime
    decided_at: datetime | None


class OrgClaimOut(BaseModel):
    id: uuid.UUID
    status: str
    created_at: datetime
    message: str | None
    requester_name: str
    requester_email: str
    player_id: uuid.UUID
    player_name: str
    player_age: int
    player_position: str | None
    decision_note: str | None
    decided_at: datetime | None
    decided_by_name: str | None


class CareerSpell(BaseModel):
    club_name: str
    team_label: str | None
    spell_type: str
    start_date: date
    end_date: date | None
    appearances: int | None
    goals: int | None
    assists: int | None


class SelfProfile(BaseModel):
    player_id: uuid.UUID
    full_name: str
    date_of_birth: date
    age: int
    is_minor: bool
    nationality: str | None
    height_cm: int | None
    weight_kg: int | None
    preferred_foot: str | None
    primary_position: str | None
    secondary_positions: list[str]
    biography: str | None
    photo_url: str | None
    photo_thumb_url: str | None
    has_uploaded_photo: bool
    visibility: str
    open_to_offers: bool
    contact_email: str | None
    current_club: CurrentClub | None
    managed_by: str | None  # the organization that keeps the club-side record
    career: list[CareerSpell]
