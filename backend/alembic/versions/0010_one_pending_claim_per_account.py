"""one pending player claim per account

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-27 10:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The app already allows one waiting request per account; this makes it true under
    # concurrency too. Keep the newest pending request if duplicates slipped in.
    op.execute(
        """
        UPDATE player_claims c SET status = 'cancelled'
        WHERE status = 'pending' AND EXISTS (
            SELECT 1 FROM player_claims n
            WHERE n.user_id = c.user_id AND n.status = 'pending'
              AND (n.created_at, n.id) > (c.created_at, c.id)
        )
        """
    )
    op.create_index(
        "uq_player_claim_pending_per_user",
        "player_claims",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_player_claim_pending_per_user", table_name="player_claims")
