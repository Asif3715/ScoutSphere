import uuid
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

from app.schemas.base import RequestModel

AssignmentStatus = Literal[
    "draft", "assigned", "accepted", "in_progress", "submitted",
    "under_review", "approved", "rejected", "cancelled",
]  # fmt: skip
TargetType = Literal["match", "competition", "player"]


class AssignmentCreate(RequestModel):
    scout_id: uuid.UUID  # scout *profile* id
    target_type: TargetType
    target_id: uuid.UUID
    title: str = Field(min_length=3, max_length=200)
    instructions: str | None = Field(default=None, max_length=5000)
    criteria: str | None = Field(default=None, max_length=3000)
    deadline: AwareDatetime | None = None
    assign_now: bool = False  # create and send in one step


class AssignmentUpdate(RequestModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    instructions: str | None = Field(default=None, max_length=5000)
    criteria: str | None = Field(default=None, max_length=3000)
    deadline: AwareDatetime | None = None
    scout_id: uuid.UUID | None = None  # only while draft or assigned


class TransitionBody(RequestModel):
    to: AssignmentStatus
    note: str | None = Field(default=None, max_length=500)


class AssignmentOut(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    target_type: str
    target_id: uuid.UUID
    target_label: str
    scout_id: uuid.UUID
    scout_name: str
    deadline: datetime | None
    is_overdue: bool
    instructions: str | None
    criteria: str | None
    report_count: int
    created_at: datetime


class HistoryEntry(BaseModel):
    from_status: str | None
    to_status: str
    actor_name: str | None
    note: str | None
    created_at: datetime


class AssignmentReportRef(BaseModel):
    id: uuid.UUID
    player_name: str
    status: str
    recommendation: str | None


class AssignmentDetail(AssignmentOut):
    history: list[HistoryEntry]
    reports: list[AssignmentReportRef]
    allowed_transitions: list[str]  # what *you* may do next
    is_mine: bool  # you are the assigned scout


class AssignmentSummary(BaseModel):
    counts: dict[str, int]
    overdue: int
    due_soon: int  # open assignments due within 48 hours
