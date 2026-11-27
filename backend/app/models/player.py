import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.football import (
    CLAIM_STATUSES,
    FEET,
    MEDIA_KINDS,
    POSITIONS,
    SPELL_TYPES,
    VISIBILITIES,
)


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({','.join(repr(v) for v in values)})"


class Player(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A global football identity. Moving clubs never creates a second Player row;
    club/team membership is a separate relationship (team_players, player_career_history)."""

    __tablename__ = "players"
    __table_args__ = (
        CheckConstraint("height_cm IS NULL OR height_cm BETWEEN 120 AND 230", name="height_range"),
        CheckConstraint("weight_kg IS NULL OR weight_kg BETWEEN 30 AND 160", name="weight_range"),
        CheckConstraint(
            f"preferred_foot IS NULL OR {_in('preferred_foot', FEET)}", name="foot_valid"
        ),
        CheckConstraint(
            f"primary_position IS NULL OR {_in('primary_position', POSITIONS)}",
            name="position_valid",
        ),
        CheckConstraint(_in("visibility", VISIBILITIES), name="visibility_valid"),
    )

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    nationality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    height_cm: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    weight_kg: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    preferred_foot: Mapped[str | None] = mapped_column(String(10), nullable=True)
    primary_position: Mapped[str | None] = mapped_column(String(5), nullable=True)
    biography: Mapped[str | None] = mapped_column(Text, nullable=True)
    # External image link (legacy, optional). An uploaded photo, when present, wins over it.
    profile_picture_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Storage key of the uploaded photo (processed, metadata stripped); see services/media.py.
    photo_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    photo_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # private: owner org (+ orgs with the player in a squad); network: every org; public: reserved
    visibility: Mapped[str] = mapped_column(String(10), nullable=False, default="private")
    # NULL when a player self-registers; otherwise the organization that created the record.
    owner_organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=True
    )
    claimed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )
    # Set by the player once the profile is claimed. Other organizations see the contact email
    # only while this is on (and never for a minor); the owning organization always does.
    open_to_offers: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    contact_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


Index("ix_players_name_trgm", func.lower(Player.full_name), postgresql_using="gin",
      postgresql_ops={"lower(full_name)": "gin_trgm_ops"})  # fmt: skip
Index("ix_players_dob", Player.date_of_birth)
Index("ix_players_owner_org", Player.owner_organization_id)
Index("ix_players_position", Player.primary_position)


class PlayerPosition(Base):
    """Secondary positions (the primary one lives on players.primary_position)."""

    __tablename__ = "player_positions"
    __table_args__ = (CheckConstraint(_in("position", POSITIONS), name="position_valid"),)

    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[str] = mapped_column(String(5), primary_key=True)


class PlayerCareer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One spell at a club. Objective history; kept (never overwritten) when a player moves."""

    __tablename__ = "player_career_history"
    __table_args__ = (
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="dates_ordered"),
        CheckConstraint(_in("spell_type", SPELL_TYPES), name="spell_type_valid"),
        CheckConstraint(
            "(appearances IS NULL OR appearances >= 0) AND (goals IS NULL OR goals >= 0)"
            " AND (assists IS NULL OR assists >= 0)",
            name="stats_non_negative",
        ),
    )

    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    club_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clubs.id", ondelete="RESTRICT"), index=True
    )
    team_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    spell_type: Mapped[str] = mapped_column(String(15), nullable=False, default="permanent")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    appearances: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    goals: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    assists: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    recorded_by_organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    # Set when the spell was opened automatically by adding the player to a squad.
    team_player_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class PlayerMedia(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Links to videos/images/documents. Always private to the organization that added it.
    (Actual file storage arrives with the document module; for now these are external URLs.)"""

    __tablename__ = "player_media"
    __table_args__ = (CheckConstraint(_in("kind", MEDIA_KINDS), name="kind_valid"),)

    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class PlayerClaim(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A player account asking to be linked to an existing player record. The organization
    that owns the record decides; only an approved claim sets `players.claimed_by_user_id`."""

    __tablename__ = "player_claims"
    __table_args__ = (
        CheckConstraint(_in("status", CLAIM_STATUSES), name="status_valid"),
        # one open request per person and profile
        Index(
            "uq_player_claim_pending",
            "player_id",
            "user_id",
            unique=True,
            postgresql_where="status = 'pending'",
        ),
        # one waiting request per account, whichever player it is for
        Index(
            "uq_player_claim_pending_per_user",
            "user_id",
            unique=True,
            postgresql_where="status = 'pending'",
        ),
    )

    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # The organization that owned the record when the claim was made: the one that reviews it.
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending")
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
