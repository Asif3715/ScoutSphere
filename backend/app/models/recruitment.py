import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.football import FEET, POSITIONS
from app.domain.recruitment import PRIORITIES, REQUIREMENT_STATUSES, STAGES
from app.domain.scouting import RATING_ATTRIBUTES, RATING_MAX, RATING_MIN


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({','.join(repr(v) for v in values)})"


class RecruitmentRequirement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """What a club is looking for. Organization-private."""

    __tablename__ = "recruitment_requirements"
    __table_args__ = (
        CheckConstraint(_in("status", REQUIREMENT_STATUSES), name="status_valid"),
        CheckConstraint(_in("priority", PRIORITIES), name="priority_valid"),
        CheckConstraint(_in("position", POSITIONS), name="position_valid"),
        CheckConstraint(
            f"preferred_foot IS NULL OR {_in('preferred_foot', FEET)}", name="foot_valid"
        ),
        CheckConstraint(
            "min_age IS NULL OR max_age IS NULL OR min_age <= max_age", name="age_range_ordered"
        ),
        CheckConstraint(
            "budget_min IS NULL OR budget_max IS NULL OR budget_min <= budget_max",
            name="budget_ordered",
        ),
        CheckConstraint(
            "min_appearances IS NULL OR min_appearances >= 0", name="appearances_nonneg"
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[str] = mapped_column(String(5), nullable=False)
    min_age: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    max_age: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_foot: Mapped[str | None] = mapped_column(String(10), nullable=True)
    min_appearances: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Budget is recorded for the team's reference. Market value and fees are not tracked until
    # the contracts phase, so it is not used for matching yet.
    budget_min: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    budget_max: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    contract_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="draft", index=True)


class RequirementAttribute(Base):
    """A minimum *average* scout rating (from approved reports) the player must have."""

    __tablename__ = "recruitment_requirement_attributes"
    __table_args__ = (
        CheckConstraint(_in("attribute", RATING_ATTRIBUTES), name="attribute_valid"),
        CheckConstraint(f"min_rating BETWEEN {RATING_MIN} AND {RATING_MAX}", name="rating_range"),
    )

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recruitment_requirements.id", ondelete="CASCADE"),
        primary_key=True,
    )
    attribute: Mapped[str] = mapped_column(String(30), primary_key=True)
    min_rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class RecruitmentCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A player being pursued for a requirement."""

    __tablename__ = "recruitment_candidates"
    __table_args__ = (
        UniqueConstraint("requirement_id", "player_id", name="uq_candidate_requirement_player"),
        CheckConstraint(_in("stage", STAGES), name="stage_valid"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recruitment_requirements.id", ondelete="RESTRICT"),
        index=True,
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="RESTRICT"), index=True
    )
    stage: Mapped[str] = mapped_column(String(20), nullable=False, default="discovered", index=True)
    added_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scout_assignments.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class RecruitmentStageHistory(UUIDPrimaryKeyMixin, Base):
    """Append-only: every stage change, in a database-generated order."""

    __tablename__ = "recruitment_stage_history"

    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False, index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recruitment_candidates.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE")
    )
    from_stage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_stage: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Shortlist(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Private to its creator until explicitly shared with colleagues."""

    __tablename__ = "shortlists"
    __table_args__ = (CheckConstraint(_in("priority", PRIORITIES), name="priority_valid"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recruitment_requirements.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")


class ShortlistPlayer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shortlist_players"
    __table_args__ = (
        UniqueConstraint("shortlist_id", "player_id", name="uq_shortlist_player"),
        CheckConstraint(_in("priority", PRIORITIES), name="priority_valid"),
    )

    shortlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shortlists.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="RESTRICT"), index=True
    )
    added_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # internal, never shown outside
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")


class ShortlistShare(Base):
    __tablename__ = "shortlist_shares"

    shortlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shortlists.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
