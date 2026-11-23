"""player accounts: claims, offers and contact

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-24 10:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column("open_to_offers", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("players", sa.Column("contact_email", sa.String(length=254), nullable=True))
    op.create_table(
        "player_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("decided_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','cancelled')",
            name=op.f("ck_player_claims_status_valid"),
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_player_claims_player_id", "player_claims", ["player_id"])
    op.create_index("ix_player_claims_user_id", "player_claims", ["user_id"])
    op.create_index("ix_player_claims_organization_id", "player_claims", ["organization_id"])
    op.create_index(
        "uq_player_claim_pending",
        "player_claims",
        ["player_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_table("player_claims")
    op.drop_column("players", "contact_email")
    op.drop_column("players", "open_to_offers")
