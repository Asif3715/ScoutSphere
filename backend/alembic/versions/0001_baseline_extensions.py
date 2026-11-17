"""baseline: postgres extensions

Revision ID: 0001
Revises:
Create Date: 2026-11-17
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')  # gen_random_uuid()
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')  # fuzzy search / duplicate detection
    op.execute('CREATE EXTENSION IF NOT EXISTS "citext"')  # case-insensitive emails


def downgrade() -> None:
    op.execute('DROP EXTENSION IF EXISTS "citext"')
    op.execute('DROP EXTENSION IF EXISTS "pg_trgm"')
    op.execute('DROP EXTENSION IF EXISTS "pgcrypto"')
