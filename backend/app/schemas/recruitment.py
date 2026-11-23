import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.domain.scouting import RATING_ATTRIBUTES, RATING_MAX, RATING_MIN
from app.schemas.base import RequestModel
from app.schemas.players import Foot, PlayerSummary, Position

Priority = Literal["low", "medium", "high", "urgent"]
RequirementStatus = Literal["draft", "open", "on_hold", "fulfilled", "cancelled"]
Stage = Literal[
    "discovered", "under_evaluation", "shortlisted", "scout_assigned", "report_submitted",
    "under_review", "trial_proposed", "negotiation", "signed", "rejected", "archived",
]  # fmt: skip
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{3}$", to_upper=True)]


def _check_ratings(v: dict[str, int]) -> dict[str, int]:
    unknown = set(v) - set(RATING_ATTRIBUTES)
    if unknown:
        raise ValueError(f"Unknown rating attributes: {sorted(unknown)}")
    for attr, rating in v.items():
        if not RATING_MIN <= rating <= RATING_MAX:
            raise ValueError(f"{attr} must be between {RATING_MIN} and {RATING_MAX}")
    return v


class RequirementBase(RequestModel):
    title: str = Field(min_length=3, max_length=200)
    position: Position
    min_age: int | None = Field(default=None, ge=8, le=60)
    max_age: int | None = Field(default=None, ge=8, le=60)
    nationality: str | None = Field(default=None, max_length=100)
    preferred_foot: Foot | None = None
    min_appearances: int | None = Field(default=None, ge=0, le=5000)
    budget_min: int | None = Field(default=None, ge=0)
    budget_max: int | None = Field(default=None, ge=0)
    currency: Currency | None = None
    contract_notes: str | None = Field(default=None, max_length=3000)
    instructions: str | None = Field(default=None, max_length=5000)
    priority: Priority = "medium"
    # attribute -> minimum average scout rating (from approved reports)
    attributes: dict[str, int] = Field(default_factory=dict)

    @field_validator("attributes")
    @classmethod
    def _attrs(cls, v: dict[str, int]) -> dict[str, int]:
        return _check_ratings(v)

    @model_validator(mode="after")
    def _ranges(self):
        if self.min_age and self.max_age and self.min_age > self.max_age:
            raise ValueError("Minimum age cannot exceed maximum age")
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_min > self.budget_max
        ):
            raise ValueError("Minimum budget cannot exceed maximum budget")
        if (self.budget_min is not None or self.budget_max is not None) and not self.currency:
            raise ValueError("A currency is required with a budget")
        return self


class RequirementCreate(RequirementBase):
    pass


class RequirementUpdate(RequestModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    position: Position | None = None
    min_age: int | None = Field(default=None, ge=8, le=60)
    max_age: int | None = Field(default=None, ge=8, le=60)
    nationality: str | None = Field(default=None, max_length=100)
    preferred_foot: Foot | None = None
    min_appearances: int | None = Field(default=None, ge=0, le=5000)
    budget_min: int | None = Field(default=None, ge=0)
    budget_max: int | None = Field(default=None, ge=0)
    currency: Currency | None = None
    contract_notes: str | None = Field(default=None, max_length=3000)
    instructions: str | None = Field(default=None, max_length=5000)
    priority: Priority | None = None
    status: RequirementStatus | None = None
    attributes: dict[str, int] | None = None  # replaces the whole set when sent

    @field_validator("attributes")
    @classmethod
    def _attrs(cls, v: dict[str, int] | None) -> dict[str, int] | None:
        return None if v is None else _check_ratings(v)


class RequirementSummary(BaseModel):
    id: uuid.UUID
    title: str
    position: str
    priority: str
    status: str
    candidate_count: int
    created_at: datetime


class RequirementOut(RequirementSummary):
    min_age: int | None
    max_age: int | None
    nationality: str | None
    preferred_foot: str | None
    min_appearances: int | None
    budget_min: int | None
    budget_max: int | None
    currency: str | None
    contract_notes: str | None
    instructions: str | None
    attributes: dict[str, int]
    pipeline_counts: dict[str, int]
    created_by_name: str | None
    allowed_statuses: list[str]


class CriterionResult(BaseModel):
    name: str
    required: str
    actual: str | None
    met: bool


class CandidateMatch(BaseModel):
    player: PlayerSummary
    criteria: list[CriterionResult]
    report_count: int  # approved reports the ratings are based on
    in_pipeline: bool


# ---- pipeline ----------------------------------------------------------------------------
class CandidateAdd(RequestModel):
    player_id: uuid.UUID
    notes: str | None = Field(default=None, max_length=2000)


class CandidateBulkAdd(RequestModel):
    player_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)


class StageMove(RequestModel):
    to: Stage
    note: str | None = Field(default=None, max_length=500)


class AssignScoutBody(RequestModel):
    scout_id: uuid.UUID
    deadline: AwareDatetime | None = None
    instructions: str | None = Field(default=None, max_length=5000)


class StageHistoryEntry(BaseModel):
    from_stage: str | None
    to_stage: str
    actor_name: str | None
    note: str | None
    created_at: datetime


class CandidateOut(BaseModel):
    id: uuid.UUID
    requirement_id: uuid.UUID
    requirement_title: str
    player_id: uuid.UUID
    player_name: str
    age: int
    primary_position: str | None
    stage: str
    notes: str | None
    assignment_id: uuid.UUID | None
    assignment_status: str | None
    created_at: datetime
    updated_at: datetime
    photo_thumb_url: str | None = None
    # The team of the caller's organization the player is currently registered with, if any.
    squad_team_id: uuid.UUID | None = None
    squad_team_name: str | None = None


class CandidateDetail(CandidateOut):
    history: list[StageHistoryEntry]
    allowed_stages: list[str]


class BulkAddResult(BaseModel):
    added: int
    skipped: int  # already in the pipeline
    candidates: list[CandidateOut]


# ---- shortlists --------------------------------------------------------------------------
class ShortlistCreate(RequestModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    priority: Priority = "medium"
    requirement_id: uuid.UUID | None = None


class ShortlistUpdate(RequestModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    priority: Priority | None = None
    requirement_id: uuid.UUID | None = None


class ShortlistPlayerAdd(RequestModel):
    player_id: uuid.UUID
    notes: str | None = Field(default=None, max_length=3000)
    priority: Priority = "medium"


class ShortlistPlayerUpdate(RequestModel):
    notes: str | None = Field(default=None, max_length=3000)
    priority: Priority | None = None


class SharesBody(RequestModel):
    user_ids: list[uuid.UUID] = Field(max_length=50)


class PipelineRef(BaseModel):
    requirement_id: uuid.UUID
    requirement_title: str
    stage: str


class ShortlistPlayerOut(BaseModel):
    player: PlayerSummary
    notes: str | None
    priority: str
    added_at: datetime
    pipeline: list[PipelineRef]  # where this player stands in the recruitment pipeline


class ShortlistSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    priority: str
    requirement_id: uuid.UUID | None
    requirement_title: str | None
    player_count: int
    is_owner: bool
    owner_name: str | None
    created_at: datetime


class SharedWith(BaseModel):
    user_id: uuid.UUID
    full_name: str


class ShortlistDetail(ShortlistSummary):
    players: list[ShortlistPlayerOut]
    shared_with: list[SharedWith]  # only populated for the owner


# ---- comparison --------------------------------------------------------------------------
class CompareBody(RequestModel):
    player_ids: list[uuid.UUID] = Field(min_length=2, max_length=5)
    requirement_id: uuid.UUID | None = None

    @field_validator("player_ids")
    @classmethod
    def _unique(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(v)) != len(v):
            raise ValueError("Each player can appear only once")
        return v


class ObjectiveStats(BaseModel):
    """Objective facts only: nothing here comes from a scout's opinion."""

    appearances: int | None
    goals: int | None
    assists: int | None
    recent_club: str | None
    recent_appearances: int | None
    recent_goals: int | None
    recent_assists: int | None
    contract_status: str | None  # contracts are not tracked until a later phase


class ScoutingSummary(BaseModel):
    """Subjective evaluations: averages over approved reports, never mixed with the above."""

    approved_reports: int
    ratings: dict[str, float]
    recommendations: dict[str, int]
    latest_recommendation: str | None


class ComparePlayer(BaseModel):
    player: PlayerSummary
    date_of_birth: str
    secondary_positions: list[str]
    height_cm: int | None
    weight_kg: int | None
    preferred_foot: str | None
    objective: ObjectiveStats
    scouting: ScoutingSummary
    suitability: list[CriterionResult] | None  # only when a requirement was given


class CompareOut(BaseModel):
    players: list[ComparePlayer]
    attributes: list[str]  # rating attributes at least one player has data for
    leaders: dict[str, list[uuid.UUID]]  # per attribute, who has the highest average
    requirement_title: str | None
