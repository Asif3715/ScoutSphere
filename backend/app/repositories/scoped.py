"""Helpers for data that is either organization-private or global (organization_id NULL).

`org_id` is the caller's active organization, or None for a platform admin acting on
global data. Tenants can read global rows but only ever write their own.
"""

import uuid

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.club import Club


def visible(column, org_id: uuid.UUID | None) -> ColumnElement[bool]:
    if org_id is None:
        return column.is_(None)
    return or_(column.is_(None), column == org_id)


def owned(column, org_id: uuid.UUID | None) -> ColumnElement[bool]:
    return column.is_(None) if org_id is None else column == org_id


async def usable_club(
    db: AsyncSession, org_id: uuid.UUID | None, club_id: uuid.UUID
) -> Club | None:
    """A club the caller may reference: a global reference club, or (for tenants) their own."""
    return await db.scalar(
        select(Club).where(
            Club.id == club_id, Club.archived_at.is_(None), visible(Club.organization_id, org_id)
        )
    )
