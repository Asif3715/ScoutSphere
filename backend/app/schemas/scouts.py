import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.players import Position

AgeGroup = Literal["u15", "u16", "u17", "u18", "u19", "u21", "u23", "senior"]


def _dedupe(v: list) -> list:
    return list(dict.fromkeys(v))


class ScoutBase(BaseModel):
    bio: str | None = Field(default=None, max_length=3000)
    experience_years: int | None = Field(default=None, ge=0, le=60)
    positions: list[Position] = Field(default_factory=list, max_length=15)
    age_groups: list[AgeGroup] = Field(default_factory=list, max_length=8)
    regions: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("regions")
    @classmethod
    def _regions(cls, v: list[str]) -> list[str]:
        cleaned = [r.strip() for r in v]
        if any(not r or len(r) > 100 for r in cleaned):
            raise ValueError("Regions must be 1-100 characters")
        return list(dict.fromkeys(cleaned))

    @field_validator("positions", "age_groups")
    @classmethod
    def _unique(cls, v: list) -> list:
        return _dedupe(v)


class ScoutCreate(ScoutBase):
    user_id: uuid.UUID | None = None  # default: yourself


class ScoutUpdate(BaseModel):
    bio: str | None = Field(default=None, max_length=3000)
    experience_years: int | None = Field(default=None, ge=0, le=60)
    positions: list[Position] | None = Field(default=None, max_length=15)
    age_groups: list[AgeGroup] | None = Field(default=None, max_length=8)
    regions: list[str] | None = Field(default=None, max_length=10)
    is_active: bool | None = None  # managers only

    @field_validator("regions")
    @classmethod
    def _regions(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        cleaned = [r.strip() for r in v]
        if any(not r or len(r) > 100 for r in cleaned):
            raise ValueError("Regions must be 1-100 characters")
        return list(dict.fromkeys(cleaned))


class ScoutOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    org_role: str
    bio: str | None
    experience_years: int | None
    positions: list[str]
    age_groups: list[str]
    regions: list[str]
    is_active: bool
    can_edit: bool
    created_at: datetime
