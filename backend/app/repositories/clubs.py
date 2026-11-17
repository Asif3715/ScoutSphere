import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.club import Club
from app.permissions.context import AuthContext
from app.schemas.common import PageParams


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class ClubRepository:
    """All club queries go through here. Managed clubs are *always* filtered by the caller's
    organization; there is no method that can return another tenant's managed club."""

    def __init__(self, db: AsyncSession, ctx: AuthContext):
        self.db = db
        self.org_id = ctx.require_org()

    def _filters(self, stmt: Select, q: str | None, country: str | None) -> Select:
        stmt = stmt.where(Club.archived_at.is_(None))
        if q:
            stmt = stmt.where(Club.name.ilike(f"%{escape_like(q)}%", escape="\\"))
        if country:
            stmt = stmt.where(func.lower(Club.country) == country.lower())
        return stmt

    async def _page(self, stmt: Select, page: PageParams) -> tuple[list[Club], int]:
        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = await self.db.scalars(
            stmt.order_by(func.lower(Club.name)).offset(page.offset).limit(page.page_size)
        )
        return list(rows), total

    async def list_managed(self, page: PageParams, q=None, country=None):
        stmt = self._filters(select(Club).where(Club.organization_id == self.org_id), q, country)
        return await self._page(stmt, page)

    async def list_reference(self, page: PageParams, q=None, country=None):
        stmt = self._filters(select(Club).where(Club.organization_id.is_(None)), q, country)
        return await self._page(stmt, page)

    async def get_visible(self, club_id: uuid.UUID) -> Club | None:
        """Own managed club or a global reference club."""
        return await self.db.scalar(
            select(Club).where(
                Club.id == club_id,
                Club.archived_at.is_(None),
                (Club.organization_id == self.org_id) | Club.organization_id.is_(None),
            )
        )

    async def get_managed(self, club_id: uuid.UUID) -> Club | None:
        return await self.db.scalar(
            select(Club).where(
                Club.id == club_id,
                Club.organization_id == self.org_id,
                Club.archived_at.is_(None),
            )
        )
