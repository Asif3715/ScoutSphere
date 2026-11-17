import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

MatchStatus = Literal["scheduled", "live", "finished", "postponed", "cancelled"]
EventType = Literal["goal", "own_goal", "penalty", "yellow_card", "red_card", "substitution"]


class MatchCreate(BaseModel):
    season_id: uuid.UUID
    home_club_id: uuid.UUID
    away_club_id: uuid.UUID
    kickoff_at: AwareDatetime
    venue: str | None = Field(default=None, max_length=200)
    round_label: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def _differ(self):
        if self.home_club_id == self.away_club_id:
            raise ValueError("A club cannot play itself")
        return self


class MatchUpdate(BaseModel):
    kickoff_at: AwareDatetime | None = None
    venue: str | None = Field(default=None, max_length=200)
    round_label: str | None = Field(default=None, max_length=50)
    status: MatchStatus | None = None
    home_score: int | None = Field(default=None, ge=0, le=99)
    away_score: int | None = Field(default=None, ge=0, le=99)


class MatchOut(BaseModel):
    id: uuid.UUID
    competition_id: uuid.UUID
    competition_name: str
    season_id: uuid.UUID
    season_name: str
    home_club_id: uuid.UUID
    home_club_name: str
    away_club_id: uuid.UUID
    away_club_name: str
    kickoff_at: datetime
    venue: str | None
    round_label: str | None
    status: str
    home_score: int | None
    away_score: int | None
    is_global: bool
    editable: bool


class EventCreate(BaseModel):
    event_type: EventType
    minute: int = Field(ge=0, le=150)
    club_id: uuid.UUID
    player_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=300)


class EventOut(BaseModel):
    id: uuid.UUID
    event_type: str
    minute: int
    club_id: uuid.UUID
    club_name: str
    player_id: uuid.UUID | None
    player_name: str | None
    description: str | None


class StatsSide(BaseModel):
    possession_pct: int | None = Field(default=None, ge=0, le=100)
    shots: int | None = Field(default=None, ge=0, le=99)
    shots_on_target: int | None = Field(default=None, ge=0, le=99)
    corners: int | None = Field(default=None, ge=0, le=99)
    fouls: int | None = Field(default=None, ge=0, le=99)
    offsides: int | None = Field(default=None, ge=0, le=99)
    yellow_cards: int | None = Field(default=None, ge=0, le=22)
    red_cards: int | None = Field(default=None, ge=0, le=11)

    @model_validator(mode="after")
    def _on_target(self):
        if (
            self.shots is not None
            and self.shots_on_target is not None
            and self.shots_on_target > self.shots
        ):
            raise ValueError("Shots on target cannot exceed total shots")
        return self


class StatsBody(BaseModel):
    home: StatsSide | None = None
    away: StatsSide | None = None


class StatsOut(BaseModel):
    home: StatsSide | None
    away: StatsSide | None


class MatchDetail(MatchOut):
    events: list[EventOut]
    statistics: StatsOut


class MatchFilters(BaseModel):
    competition_id: uuid.UUID | None = None
    season_id: uuid.UUID | None = None
    club_id: uuid.UUID | None = None
    status: MatchStatus | None = None
    date_from: date | None = None
    date_to: date | None = None
    sort: Literal["kickoff_desc", "kickoff_asc"] = "kickoff_desc"
