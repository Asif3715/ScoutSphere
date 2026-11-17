import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Club(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A football club.

    `organization_id` set  -> *managed* club: private to that organization.
    `organization_id` NULL -> *reference* club: global, read-only for tenants (opponents,
    past clubs in a player's career). See PRD section 0.1.
    """

    __tablename__ = "clubs"
    __table_args__ = (
        CheckConstraint(
            "founded_year IS NULL OR founded_year BETWEEN 1800 AND 2100",
            name="founded_year_range",
        ),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    founded_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    website: Mapped[str | None] = mapped_column(String(300), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# A managed club name is unique within its organization (case-insensitive, ignoring archived).
Index(
    "uq_clubs_org_name_active",
    Club.organization_id,
    func.lower(Club.name),
    unique=True,
    postgresql_where=text("archived_at IS NULL AND organization_id IS NOT NULL"),
)
# Fast name search / duplicate checks on global reference clubs.
Index(
    "ix_clubs_name_trgm", Club.name, postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}
)
