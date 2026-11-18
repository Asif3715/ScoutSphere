import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.base import RequestModel

CompetitionType = Literal["league", "cup", "friendly", "youth_league", "international", "other"]


class CompetitionCreate(RequestModel):
    name: str = Field(min_length=2, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    competition_type: CompetitionType = "league"


class CompetitionUpdate(RequestModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    competition_type: CompetitionType | None = None


class SeasonCreate(RequestModel):
    name: str = Field(min_length=1, max_length=50)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _dates(self):
        if self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date")
        return self


class SeasonUpdate(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    start_date: date | None = None
    end_date: date | None = None


class ParticipantAdd(RequestModel):
    club_id: uuid.UUID


class SeasonOut(BaseModel):
    id: uuid.UUID
    competition_id: uuid.UUID
    name: str
    start_date: date
    end_date: date
    participant_count: int
    match_count: int


class ParticipantOut(BaseModel):
    club_id: uuid.UUID
    club_name: str
    is_reference: bool


class SeasonDetail(SeasonOut):
    competition_name: str
    participants: list[ParticipantOut]
    editable: bool


class CompetitionOut(BaseModel):
    id: uuid.UUID
    name: str
    country: str | None
    competition_type: str
    is_global: bool
    editable: bool
    season_count: int
    created_at: datetime


class CompetitionDetail(CompetitionOut):
    seasons: list[SeasonOut]
