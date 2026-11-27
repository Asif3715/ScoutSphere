"""Side-by-side player comparison.

Objective facts and scout opinions are kept in separate sections, and nothing is collapsed into
a single score: every number can be traced to a stored value or report.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domain.recruitment import MAX_COMPARE, MIN_COMPARE
from app.domain.scouting import RATING_ATTRIBUTES
from app.models.club import Club
from app.models.player import Player, PlayerCareer
from app.models.recruitment import RecruitmentRequirement
from app.models.report import ScoutingReport
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.repositories.players import PlayerRepository
from app.schemas.recruitment import (
    CompareOut,
    ComparePlayer,
    ObjectiveStats,
    ScoutingSummary,
)
from app.services.players import build_summary
from app.services.recruitment import _attributes, criteria_for, evaluate, gather_facts


async def compare_players(
    db: AsyncSession, ctx: AuthContext, player_ids: list[uuid.UUID],
    requirement_id: uuid.UUID | None = None,
) -> CompareOut:  # fmt: skip
    ctx.require(catalog.RECRUITMENT_READ)
    ctx.require(catalog.PLAYERS_READ)
    org_id = ctx.require_org()
    if not MIN_COMPARE <= len(player_ids) <= MAX_COMPARE or len(set(player_ids)) != len(player_ids):
        raise AppError(
            422, "invalid_selection", f"Choose {MIN_COMPARE} to {MAX_COMPARE} different players"
        )

    repo = PlayerRepository(db, ctx)
    players: list[Player] = []
    for pid in player_ids:  # keep the caller's order
        p = await repo.get_visible(pid)
        if p is None:
            raise AppError(422, "invalid_player", "One of the players was not found")
        players.append(p)

    criteria = None
    requirement_title = None
    if requirement_id:
        req = await db.scalar(
            select(RecruitmentRequirement).where(
                RecruitmentRequirement.id == requirement_id,
                RecruitmentRequirement.organization_id == org_id,
            )
        )
        if req is None:
            raise AppError(422, "invalid_requirement", "Requirement not found")
        criteria = criteria_for(req, await _attributes(db, req.id))
        requirement_title = req.title

    facts = await gather_facts(db, org_id, players)
    clubs = await repo.current_clubs(player_ids)

    # most recent club spell per player (objective "recent performance")
    recent: dict[uuid.UUID, tuple[str, PlayerCareer]] = {}
    for career, career_club in await db.execute(
        select(PlayerCareer, Club.name)
        .join(Club, Club.id == PlayerCareer.club_id)
        .where(PlayerCareer.player_id.in_(player_ids))
        .order_by(PlayerCareer.start_date)
    ):
        recent[career.player_id] = (career_club, career)

    recs: dict[uuid.UUID, dict[str, int]] = {pid: {} for pid in player_ids}
    latest: dict[uuid.UUID, str | None] = {pid: None for pid in player_ids}
    for pid, rec in await db.execute(
        select(ScoutingReport.player_id, ScoutingReport.recommendation)
        .where(
            ScoutingReport.player_id.in_(player_ids),
            ScoutingReport.organization_id == org_id,
            ScoutingReport.status == "approved",
            ScoutingReport.recommendation.is_not(None),
        )
        .order_by(ScoutingReport.submitted_at)
    ):
        if rec is None:  # filtered out by the query; keeps the type checker honest
            continue
        recs[pid][rec] = recs[pid].get(rec, 0) + 1
        latest[pid] = rec

    out: list[ComparePlayer] = []
    for p in players:
        f = facts[p.id]
        club_name: str | None = None
        spell: PlayerCareer | None = None
        if p.id in recent:
            club_name, spell = recent[p.id]
        out.append(
            ComparePlayer(
                player=build_summary(p, ctx, clubs), date_of_birth=p.date_of_birth.isoformat(),
                secondary_positions=[x for x in f.positions if x != p.primary_position],
                height_cm=p.height_cm, weight_kg=p.weight_kg, preferred_foot=p.preferred_foot,
                objective=ObjectiveStats(
                    appearances=f.appearances, goals=f.goals, assists=f.assists,
                    recent_club=club_name,
                    recent_appearances=spell.appearances if spell else None,
                    recent_goals=spell.goals if spell else None,
                    recent_assists=spell.assists if spell else None,
                    contract_status=None,
                ),
                scouting=ScoutingSummary(
                    approved_reports=f.report_count, ratings=f.ratings,
                    recommendations=recs[p.id], latest_recommendation=latest[p.id],
                ),
                suitability=evaluate(f, criteria) if criteria else None,
            )
        )  # fmt: skip

    attributes = [a for a in RATING_ATTRIBUTES if any(a in c.scouting.ratings for c in out)]
    leaders: dict[str, list[uuid.UUID]] = {}
    for a in attributes:
        best = max(c.scouting.ratings[a] for c in out if a in c.scouting.ratings)
        leaders[a] = [c.player.id for c in out if c.scouting.ratings.get(a) == best]
    return CompareOut(
        players=out, attributes=attributes, leaders=leaders, requirement_title=requirement_title
    )
