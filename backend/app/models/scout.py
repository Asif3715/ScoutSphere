import uuid

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.football import SPECIALIZATION_KINDS


class ScoutProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Scouting profile of an organization member. Private to the organization."""

    __tablename__ = "scout_profiles"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_scout_org_user"),
        CheckConstraint(
            "experience_years IS NULL OR experience_years BETWEEN 0 AND 60", name="experience_range"
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience_years: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class ScoutSpecialization(Base):
    """A position, age group or region the scout covers."""

    __tablename__ = "scout_specializations"
    __table_args__ = (
        CheckConstraint(
            "kind IN (" + ",".join(repr(k) for k in SPECIALIZATION_KINDS) + ")", name="kind_valid"
        ),
    )

    scout_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scout_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(10), primary_key=True)
    value: Mapped[str] = mapped_column(String(100), primary_key=True)
