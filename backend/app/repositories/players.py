import uuid
from dataclasses import dataclass, field

from sqlalchemy import ColumnElement, Select, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.football import POSITION_GROUPS, dob_bounds_for_age
from app.models.club import Club
from app.models.player import Player, PlayerCareer, PlayerPosition
from app.models.team import TeamPlayer
from app.permissions.context import AuthContext
from app.repositories.clubs import escape_like
from app.schemas.common import PageParams

SORTS = {"name", "age_asc", "age_desc", "newest"}


@dataclass
class PlayerFilters:
    q: str | None = None
    position: str | None = None  # a position code
    group: str | None = None  # goalkeeper | defender | midfielder | forward
    nationality: str | None = None
    foot: str | None = None
    min_age: int | None = None
    max_age: int | None = None
    min_height: int | None = None
    max_height: int | None = None
    club_id: uuid.UUID | None = None  # currently registered at this club
    team_id: uuid.UUID | None = None  # in this team of the caller's organization
    scope: str = "all"  # mine | network | all
    sort: str = "name"
    extra: dict = field(default_factory=dict)


class PlayerRepository:
    """The only place players are queried. Every method applies the visibility rule, so a
    player outside the caller's reach can never be returned (see PRD 0.1)."""

    def __init__(self, db: AsyncSession, ctx: AuthContext):
        self.db = db
        self.org_id = ctx.require_org()

    # ---- visibility ---------------------------------------------------------------
    def _in_my_squad(self) -> ColumnElement[bool]:
        return exists().where(
            TeamPlayer.player_id == Player.id,
            TeamPlayer.organization_id == self.org_id,
            TeamPlayer.status == "active",
        )

    def _mine(self) -> ColumnElement[bool]:
        return or_(Player.owner_organization_id == self.org_id, self._in_my_squad())

    def _visible(self) -> ColumnElement[bool]:
        return and_(
            Player.archived_at.is_(None),
            or_(self._mine(), Player.visibility.in_(["network", "public"])),
        )

    async def get_visible(self, player_id: uuid.UUID) -> Player | None:
        return await self.db.scalar(select(Player).where(Player.id == player_id, self._visible()))

    async def get_owned(self, player_id: uuid.UUID, *, for_update: bool = False) -> Player | None:
        stmt = select(Player).where(
            Player.id == player_id,
            Player.owner_organization_id == self.org_id,
            Player.archived_at.is_(None),
        )
        return await self.db.scalar(stmt.with_for_update() if for_update else stmt)

    # ---- search -------------------------------------------------------------------
    def _apply(self, stmt: Select, f: PlayerFilters) -> Select:
        stmt = stmt.where(self._visible())
        if f.scope == "mine":
            stmt = stmt.where(self._mine())
        elif f.scope == "network":
            stmt = stmt.where(~self._mine())
        if f.q:
            stmt = stmt.where(Player.full_name.ilike(f"%{escape_like(f.q)}%", escape="\\"))
        codes = None
        if f.position:
            codes = [f.position]
        elif f.group:
            codes = POSITION_GROUPS.get(f.group, [])
        if codes is not None:
            stmt = stmt.where(
                or_(
                    Player.primary_position.in_(codes),
                    exists().where(
                        PlayerPosition.player_id == Player.id, PlayerPosition.position.in_(codes)
                    ),
                )
            )
        if f.nationality:
            stmt = stmt.where(func.lower(Player.nationality) == f.nationality.lower())
        if f.foot:
            stmt = stmt.where(Player.preferred_foot == f.foot)
        earliest, latest = dob_bounds_for_age(f.min_age, f.max_age)
        if earliest:
            stmt = stmt.where(Player.date_of_birth >= earliest)
        if latest:
            stmt = stmt.where(Player.date_of_birth <= latest)
        if f.min_height is not None:
            stmt = stmt.where(Player.height_cm >= f.min_height)
        if f.max_height is not None:
            stmt = stmt.where(Player.height_cm <= f.max_height)
        if f.club_id:
            stmt = stmt.where(
                exists().where(
                    PlayerCareer.player_id == Player.id,
                    PlayerCareer.club_id == f.club_id,
                    PlayerCareer.end_date.is_(None),
                )
            )
        if f.team_id:
            stmt = stmt.where(
                exists().where(
                    TeamPlayer.player_id == Player.id,
                    TeamPlayer.team_id == f.team_id,
                    TeamPlayer.organization_id == self.org_id,
                    TeamPlayer.status == "active",
                )
            )
        return stmt

    async def search(
        self, f: PlayerFilters, page: PageParams, extra: tuple = ()
    ) -> tuple[list[Player], int]:
        stmt = self._apply(select(Player), f)
        if extra:  # additional conditions (e.g. scout-rating filters) from callers
            stmt = stmt.where(*extra)
        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        order = {
            "name": [func.lower(Player.full_name), Player.id],
            "age_asc": [Player.date_of_birth.desc(), Player.id],  # youngest first
            "age_desc": [Player.date_of_birth.asc(), Player.id],
            "newest": [Player.created_at.desc(), Player.id],
        }[f.sort if f.sort in SORTS else "name"]
        rows = await self.db.scalars(
            stmt.order_by(*order).offset(page.offset).limit(page.page_size)
        )
        return list(rows), total

    # ---- duplicates ---------------------------------------------------------------
    async def find_duplicates(
        self, full_name: str, dob, exclude_id: uuid.UUID | None = None
    ) -> list[tuple[Player, float]]:
        """Possible duplicates among players the caller may see. Players hidden from the
        caller are deliberately not considered, so this can never reveal their existence."""
        sim = func.similarity(func.lower(Player.full_name), full_name.lower())
        stmt = (
            select(Player, sim.label("sim"))
            .where(
                self._visible(),
                or_(
                    and_(Player.date_of_birth == dob, sim >= 0.4),
                    sim >= 0.9,
                ),
            )
            .order_by(sim.desc())
            .limit(5)
        )
        if exclude_id:
            stmt = stmt.where(Player.id != exclude_id)
        return [(p, float(s)) for p, s in (await self.db.execute(stmt)).all()]

    # ---- batch lookups for serialization ------------------------------------------
    async def current_clubs(self, ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[uuid.UUID, str]]:
        if not ids:
            return {}
        rows = await self.db.execute(
            select(PlayerCareer.player_id, Club.id, Club.name)
            .join(Club, Club.id == PlayerCareer.club_id)
            .where(PlayerCareer.player_id.in_(ids), PlayerCareer.end_date.is_(None))
            .order_by(PlayerCareer.start_date.asc())  # later rows overwrite: latest start wins
        )
        return {pid: (cid, name) for pid, cid, name in rows}

    async def secondary_positions(self, ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
        if not ids:
            return {}
        rows = await self.db.execute(
            select(PlayerPosition.player_id, PlayerPosition.position)
            .where(PlayerPosition.player_id.in_(ids))
            .order_by(PlayerPosition.position)
        )
        out: dict[uuid.UUID, list[str]] = {}
        for pid, pos in rows:
            out.setdefault(pid, []).append(pos)
        return out
