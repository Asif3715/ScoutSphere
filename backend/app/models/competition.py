import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.football import COMPETITION_TYPES, EVENT_TYPES, MATCH_STATUSES


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({','.join(repr(v) for v in values)})"


class Competition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """organization_id NULL = global (platform-maintained, read-only for tenants);
    otherwise private to that organization. Same model as clubs (PRD 0.1)."""

    __tablename__ = "competitions"
    __table_args__ = (
        CheckConstraint(_in("competition_type", COMPETITION_TYPES), name="type_valid"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    competition_type: Mapped[str] = mapped_column(String(15), nullable=False, default="league")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


Index(
    "uq_competitions_scope_name",
    func.coalesce(
        Competition.organization_id, text("'00000000-0000-0000-0000-000000000000'::uuid")
    ),
    func.lower(Competition.name),
    unique=True,
    postgresql_where=text("archived_at IS NULL"),
)


class CompetitionSeason(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "competition_seasons"
    __table_args__ = (
        UniqueConstraint("competition_id", "name", name="uq_season_name"),
        CheckConstraint("end_date >= start_date", name="dates_ordered"),
    )

    competition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("competitions.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "2025/26"
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)


class CompetitionParticipant(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "competition_participants"
    __table_args__ = (UniqueConstraint("season_id", "club_id", name="uq_participant"),)

    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("competition_seasons.id", ondelete="CASCADE"), index=True
    )
    club_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clubs.id", ondelete="RESTRICT"), index=True
    )


class Match(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint("home_club_id <> away_club_id", name="clubs_differ"),
        CheckConstraint(_in("status", MATCH_STATUSES), name="status_valid"),
        CheckConstraint("(home_score IS NULL) = (away_score IS NULL)", name="scores_paired"),
        CheckConstraint(
            "(home_score IS NULL OR home_score >= 0) AND (away_score IS NULL OR away_score >= 0)",
            name="scores_non_negative",
        ),
        CheckConstraint(
            "status <> 'finished' OR home_score IS NOT NULL", name="finished_has_score"
        ),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    competition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("competitions.id", ondelete="RESTRICT"), index=True
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("competition_seasons.id", ondelete="RESTRICT"), index=True
    )
    home_club_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clubs.id", ondelete="RESTRICT"), index=True
    )
    away_club_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clubs.id", ondelete="RESTRICT"), index=True
    )
    kickoff_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    venue: Mapped[str | None] = mapped_column(String(200), nullable=True)
    round_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="scheduled")
    home_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    away_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)


class MatchEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "match_events"
    __table_args__ = (
        CheckConstraint(_in("event_type", EVENT_TYPES), name="type_valid"),
        CheckConstraint("minute BETWEEN 0 AND 150", name="minute_range"),
    )

    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), index=True
    )
    club_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clubs.id", ondelete="RESTRICT")
    )
    event_type: Mapped[str] = mapped_column(String(15), nullable=False)
    minute: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    player_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)


class MatchStatistics(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Objective team statistics for one side of a match (kept apart from scout opinions)."""

    __tablename__ = "match_statistics"
    __table_args__ = (
        UniqueConstraint("match_id", "club_id", name="uq_match_stats_side"),
        CheckConstraint(
            "possession_pct IS NULL OR possession_pct BETWEEN 0 AND 100", name="possession_range"
        ),
        CheckConstraint(
            "shots_on_target IS NULL OR shots IS NULL OR shots_on_target <= shots",
            name="on_target_le_shots",
        ),
    )

    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), index=True
    )
    club_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clubs.id", ondelete="RESTRICT")
    )
    possession_pct: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    shots: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    shots_on_target: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    corners: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    fouls: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    offsides: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    yellow_cards: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    red_cards: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
