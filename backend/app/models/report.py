import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.football import POSITIONS
from app.domain.scouting import (
    RATING_ATTRIBUTES,
    RATING_MAX,
    RATING_MIN,
    RECOMMENDATIONS,
    REPORT_STATUSES,
    REVIEW_DECISIONS,
)


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({','.join(repr(v) for v in values)})"


class ScoutingReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A scout's *subjective* evaluation. Never mixed with objective match/player statistics."""

    __tablename__ = "scouting_reports"
    __table_args__ = (
        CheckConstraint(_in("status", REPORT_STATUSES), name="status_valid"),
        CheckConstraint(
            f"recommendation IS NULL OR {_in('recommendation', RECOMMENDATIONS)}",
            name="recommendation_valid",
        ),
        CheckConstraint(
            f"position_observed IS NULL OR {_in('position_observed', POSITIONS)}",
            name="position_valid",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    scout_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scout_profiles.id", ondelete="RESTRICT"), index=True
    )
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scout_assignments.id", ondelete="RESTRICT"), index=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="RESTRICT"), index=True
    )
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id", ondelete="RESTRICT"), index=True
    )
    club_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clubs.id", ondelete="RESTRICT"), nullable=True
    )
    observed_on: Mapped[date] = mapped_column(Date, nullable=False)
    position_observed: Mapped[str | None] = mapped_column(String(5), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    current_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    recommendation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)
    weaknesses: Mapped[str | None] = mapped_column(Text, nullable=True)
    development_areas: Mapped[str | None] = mapped_column(Text, nullable=True)
    general_observations: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ScoutingReportRating(Base):
    __tablename__ = "scouting_report_ratings"
    __table_args__ = (
        CheckConstraint(_in("attribute", RATING_ATTRIBUTES), name="attribute_valid"),
        CheckConstraint(f"rating BETWEEN {RATING_MIN} AND {RATING_MAX}", name="rating_range"),
    )

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scouting_reports.id", ondelete="CASCADE"), primary_key=True
    )
    attribute: Mapped[str] = mapped_column(String(30), primary_key=True)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class ScoutingReportVersion(UUIDPrimaryKeyMixin, Base):
    """Immutable snapshot taken at every submission (JSONB is appropriate: it is a frozen copy)."""

    __tablename__ = "scouting_report_versions"
    __table_args__ = (UniqueConstraint("report_id", "version", name="uq_report_version"),)

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scouting_reports.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScoutingReportReview(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "scouting_report_reviews"
    __table_args__ = (CheckConstraint(_in("decision", REVIEW_DECISIONS), name="decision_valid"),)

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scouting_reports.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
