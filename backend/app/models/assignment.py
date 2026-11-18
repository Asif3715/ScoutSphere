import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.scouting import ASSIGNMENT_STATUSES, ASSIGNMENT_TARGETS


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({','.join(repr(v) for v in values)})"


class Assignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Work given to a scout: observe a match, a competition or one player."""

    __tablename__ = "scout_assignments"
    __table_args__ = (
        CheckConstraint(_in("status", ASSIGNMENT_STATUSES), name="status_valid"),
        CheckConstraint(_in("target_type", ASSIGNMENT_TARGETS), name="target_type_valid"),
        # exactly one target, and it must match target_type
        CheckConstraint(
            "(target_type = 'match' AND match_id IS NOT NULL"
            " AND competition_id IS NULL AND player_id IS NULL)"
            " OR (target_type = 'competition' AND competition_id IS NOT NULL"
            " AND match_id IS NULL AND player_id IS NULL)"
            " OR (target_type = 'player' AND player_id IS NOT NULL"
            " AND match_id IS NULL AND competition_id IS NULL)",
            name="single_target",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    scout_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scout_profiles.id", ondelete="RESTRICT"), index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    target_type: Mapped[str] = mapped_column(String(12), nullable=False)
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id", ondelete="RESTRICT"), nullable=True
    )
    competition_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("competitions.id", ondelete="RESTRICT"), nullable=True
    )
    player_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="RESTRICT"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(15), nullable=False, default="draft", index=True)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AssignmentHistory(UUIDPrimaryKeyMixin, Base):
    """Append-only log of every status change."""

    __tablename__ = "assignment_history"

    # Database-generated, strictly increasing: rows written in one transaction share a
    # timestamp, so ordering must not depend on created_at.
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False, index=True)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scout_assignments.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE")
    )
    from_status: Mapped[str | None] = mapped_column(String(15), nullable=True)
    to_status: Mapped[str] = mapped_column(String(15), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
