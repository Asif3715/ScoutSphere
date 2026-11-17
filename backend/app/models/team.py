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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.football import POSITIONS, TEAM_TYPES


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({','.join(repr(v) for v in values)})"


class Team(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A squad within one of the organization's managed clubs (Senior, U19, Women's...)."""

    __tablename__ = "teams"
    __table_args__ = (CheckConstraint(_in("team_type", TEAM_TYPES), name="team_type_valid"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    club_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clubs.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    team_type: Mapped[str] = mapped_column(String(10), nullable=False, default="senior")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


Index(
    "uq_teams_club_name_active",
    Team.club_id,
    func.lower(Team.name),
    unique=True,
    postgresql_where=text("archived_at IS NULL"),
)


class TeamPlayer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A player's membership of a team. Organization-private. Rows are never deleted:
    leaving sets `status='left'` and `left_on`, so squad history is preserved."""

    __tablename__ = "team_players"
    __table_args__ = (
        CheckConstraint("status IN ('active','left')", name="status_valid"),
        CheckConstraint(
            "squad_number IS NULL OR squad_number BETWEEN 1 AND 99", name="number_range"
        ),
        CheckConstraint("left_on IS NULL OR left_on >= registered_on", name="dates_ordered"),
        CheckConstraint(f"position IS NULL OR {_in('position', POSITIONS)}", name="position_valid"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="RESTRICT"), index=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="RESTRICT"), index=True
    )
    squad_number: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    position: Mapped[str | None] = mapped_column(String(5), nullable=True)
    registered_on: Mapped[date] = mapped_column(Date, nullable=False)
    left_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")


# One active membership per (team, player); one active holder per squad number in a team.
Index(
    "uq_team_players_active_player",
    TeamPlayer.team_id,
    TeamPlayer.player_id,
    unique=True,
    postgresql_where=text("status = 'active'"),
)
Index(
    "uq_team_players_active_number",
    TeamPlayer.team_id,
    TeamPlayer.squad_number,
    unique=True,
    postgresql_where=text("status = 'active' AND squad_number IS NOT NULL"),
)
