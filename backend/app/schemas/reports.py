import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.domain.scouting import RATING_ATTRIBUTES, RATING_MAX, RATING_MIN
from app.schemas.base import RequestModel
from app.schemas.players import Position

Recommendation = Literal["strongly_recommend", "recommend", "monitor", "not_recommended"]
ReportStatus = Literal["draft", "submitted", "revision_requested", "approved", "rejected"]
Decision = Literal["approved", "revision_requested", "rejected"]

Text = Field(default=None, max_length=5000)


def _check_attributes(v: dict) -> dict:
    unknown = set(v) - set(RATING_ATTRIBUTES)
    if unknown:
        raise ValueError(f"Unknown rating attributes: {sorted(unknown)}")
    return v


class ReportCreate(RequestModel):
    player_id: uuid.UUID
    observed_on: date
    match_id: uuid.UUID | None = None
    club_id: uuid.UUID | None = None
    assignment_id: uuid.UUID | None = None
    position_observed: Position | None = None
    recommendation: Recommendation | None = None
    strengths: str | None = Text
    weaknesses: str | None = Text
    development_areas: str | None = Text
    general_observations: str | None = Text
    ratings: dict[str, int] = Field(default_factory=dict)

    @field_validator("observed_on")
    @classmethod
    def _not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Observation date cannot be in the future")
        return v

    @field_validator("ratings")
    @classmethod
    def _ratings(cls, v: dict[str, int]) -> dict[str, int]:
        _check_attributes(v)
        for attr, rating in v.items():
            if not RATING_MIN <= rating <= RATING_MAX:
                raise ValueError(f"{attr} must be between {RATING_MIN} and {RATING_MAX}")
        return v


class ReportUpdate(RequestModel):
    observed_on: date | None = None
    club_id: uuid.UUID | None = None
    position_observed: Position | None = None
    recommendation: Recommendation | None = None
    strengths: str | None = Text
    weaknesses: str | None = Text
    development_areas: str | None = Text
    general_observations: str | None = Text
    # merged into the stored ratings; a null value removes that rating
    ratings: dict[str, int | None] | None = None

    @field_validator("observed_on")
    @classmethod
    def _not_future(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("Observation date cannot be in the future")
        return v

    @field_validator("ratings")
    @classmethod
    def _ratings(cls, v: dict[str, int | None] | None) -> dict[str, int | None] | None:
        if v is None:
            return v
        _check_attributes(v)
        for attr, rating in v.items():
            if rating is not None and not RATING_MIN <= rating <= RATING_MAX:
                raise ValueError(f"{attr} must be between {RATING_MIN} and {RATING_MAX}")
        return v


class ReviewBody(RequestModel):
    decision: Decision
    comment: str | None = Field(default=None, max_length=3000)


class ReportSummary(BaseModel):
    id: uuid.UUID
    status: str
    player_id: uuid.UUID
    player_name: str
    scout_id: uuid.UUID
    scout_name: str
    match_label: str | None
    observed_on: date
    recommendation: str | None
    assignment_id: uuid.UUID | None
    assignment_title: str | None
    current_version: int
    submitted_at: datetime | None


class VersionRef(BaseModel):
    version: int
    created_at: datetime


class ReviewOut(BaseModel):
    version: int
    decision: str
    comment: str | None
    reviewer_name: str | None
    created_at: datetime


class ReportDetail(ReportSummary):
    match_id: uuid.UUID | None
    club_id: uuid.UUID | None
    club_name: str | None
    position_observed: str | None
    strengths: str | None
    weaknesses: str | None
    development_areas: str | None
    general_observations: str | None
    ratings: dict[str, int]
    versions: list[VersionRef]
    reviews: list[ReviewOut]
    is_mine: bool
    can_edit: bool
    can_review: bool
    created_at: datetime
