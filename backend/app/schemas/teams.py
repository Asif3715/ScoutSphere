import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.players import Position

TeamType = Literal["senior", "u23", "u21", "u19", "u18", "u17", "u16", "academy", "womens", "other"]


class TeamCreate(BaseModel):
    club_id: uuid.UUID
    name: str = Field(min_length=1, max_length=150)
    team_type: TeamType = "senior"


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    team_type: TeamType | None = None


class TeamOut(BaseModel):
    id: uuid.UUID
    club_id: uuid.UUID
    club_name: str
    name: str
    team_type: str
    active_players: int
    created_at: datetime


class SquadAdd(BaseModel):
    player_id: uuid.UUID
    squad_number: int | None = Field(default=None, ge=1, le=99)
    position: Position | None = None
    registered_on: date | None = None


class SquadUpdate(BaseModel):
    squad_number: int | None = Field(default=None, ge=1, le=99)
    position: Position | None = None


class SquadPlayerOut(BaseModel):
    membership_id: uuid.UUID
    player_id: uuid.UUID
    full_name: str
    age: int
    is_minor: bool
    nationality: str | None
    primary_position: str | None
    position: str | None
    position_group: str | None
    squad_number: int | None
    registered_on: date
    left_on: date | None
    status: str


class SquadOut(BaseModel):
    team: TeamOut
    players: list[SquadPlayerOut]
    counts_by_group: dict[str, int]
