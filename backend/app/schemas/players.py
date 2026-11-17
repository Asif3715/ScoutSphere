import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    BaseModel,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from app.domain.football import POSITIONS, age_on

Position = Literal[
    "GK", "CB", "LB", "RB", "LWB", "RWB", "CDM", "CM", "CAM", "LM", "RM", "LW", "RW", "CF", "ST"
]
Foot = Literal["left", "right", "both"]
Visibility = Literal["private", "network", "public"]
SpellType = Literal["permanent", "loan", "youth", "trial"]
MediaKind = Literal["video", "image", "document"]

_url = TypeAdapter(AnyHttpUrl)


def _http_url(value: str) -> str:
    _url.validate_python(value)  # only http(s): blocks javascript:, data:, file: etc.
    return value


HttpUrl = Annotated[str, Field(max_length=1000), AfterValidator(_http_url)]


def _check_dob(v: date) -> date:
    if v >= date.today():
        raise ValueError("Date of birth must be in the past")
    if not 8 <= age_on(v) <= 60:
        raise ValueError("Age must be between 8 and 60")
    return v


class PlayerBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    date_of_birth: date
    nationality: str | None = Field(default=None, max_length=100)
    height_cm: int | None = Field(default=None, ge=120, le=230)
    weight_kg: int | None = Field(default=None, ge=30, le=160)
    preferred_foot: Foot | None = None
    primary_position: Position | None = None
    secondary_positions: list[Position] = Field(default_factory=list, max_length=4)
    biography: str | None = Field(default=None, max_length=5000)
    profile_picture_url: HttpUrl | None = None
    visibility: Visibility = "private"

    @field_validator("date_of_birth")
    @classmethod
    def _dob(cls, v: date) -> date:
        return _check_dob(v)

    @field_validator("secondary_positions")
    @classmethod
    def _dedupe(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))

    @model_validator(mode="after")
    def _primary_not_secondary(self):
        if self.primary_position and self.primary_position in self.secondary_positions:
            raise ValueError("Primary position cannot also be a secondary position")
        return self


class PlayerCreate(PlayerBase):
    # Set to true after the user has reviewed the possible-duplicate warning.
    allow_duplicate: bool = False


class PlayerUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    date_of_birth: date | None = None
    nationality: str | None = Field(default=None, max_length=100)
    height_cm: int | None = Field(default=None, ge=120, le=230)
    weight_kg: int | None = Field(default=None, ge=30, le=160)
    preferred_foot: Foot | None = None
    primary_position: Position | None = None
    secondary_positions: list[Position] | None = Field(default=None, max_length=4)
    biography: str | None = Field(default=None, max_length=5000)
    profile_picture_url: HttpUrl | None = None
    visibility: Visibility | None = None

    @field_validator("date_of_birth")
    @classmethod
    def _dob(cls, v: date | None) -> date | None:
        return None if v is None else _check_dob(v)


class CurrentClub(BaseModel):
    club_id: uuid.UUID
    club_name: str


class PlayerOut(BaseModel):
    id: uuid.UUID
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
    profile_picture_url: str | None
    visibility: str
    is_owner: bool  # created by the caller's organization
    current_club: CurrentClub | None
    created_at: datetime


class PlayerSummary(BaseModel):
    id: uuid.UUID
    full_name: str
    age: int
    is_minor: bool
    nationality: str | None
    primary_position: str | None
    current_club: CurrentClub | None
    is_owner: bool


class DuplicateCandidate(BaseModel):
    id: uuid.UUID
    full_name: str
    date_of_birth: date
    nationality: str | None
    similarity: float


# ---- career -------------------------------------------------------------------------
class CareerBase(BaseModel):
    club_id: uuid.UUID
    team_label: str | None = Field(default=None, max_length=100)
    spell_type: SpellType = "permanent"
    start_date: date
    end_date: date | None = None
    appearances: int | None = Field(default=None, ge=0, le=2000)
    goals: int | None = Field(default=None, ge=0, le=2000)
    assists: int | None = Field(default=None, ge=0, le=2000)


class CareerCreate(CareerBase):
    @model_validator(mode="after")
    def _dates(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date")
        return self


class CareerUpdate(BaseModel):
    team_label: str | None = Field(default=None, max_length=100)
    spell_type: SpellType | None = None
    start_date: date | None = None
    end_date: date | None = None
    appearances: int | None = Field(default=None, ge=0, le=2000)
    goals: int | None = Field(default=None, ge=0, le=2000)
    assists: int | None = Field(default=None, ge=0, le=2000)


class CareerOut(BaseModel):
    id: uuid.UUID
    club_id: uuid.UUID
    club_name: str
    team_label: str | None
    spell_type: str
    start_date: date
    end_date: date | None
    appearances: int | None
    goals: int | None
    assists: int | None
    editable: bool
    managed_by_squad: bool  # maintained by squad registration; cannot be deleted manually


# ---- media --------------------------------------------------------------------------
class MediaCreate(BaseModel):
    kind: MediaKind
    title: str = Field(min_length=1, max_length=200)
    url: HttpUrl


class MediaOut(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    url: str
    created_at: datetime


assert set(POSITIONS) == set(Position.__args__)  # schema stays in sync with the domain list
