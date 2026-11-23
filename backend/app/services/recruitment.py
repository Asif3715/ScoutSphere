"""Recruitment requirements, candidate discovery and the candidate pipeline."""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domain.football import age_on
from app.domain.recruitment import (
    DEFAULT_STAGE,
    REQUIREMENT_TRANSITIONS,
    STAGE_ORDER,
    STAGES,
    can_move,
)
from app.models.assignment import Assignment
from app.models.player import Player, PlayerCareer, PlayerPosition
from app.models.recruitment import (
    RecruitmentCandidate,
    RecruitmentRequirement,
    RecruitmentStageHistory,
    RequirementAttribute,
)
from app.models.report import ScoutingReport, ScoutingReportRating
from app.models.user import User
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.repositories.players import PlayerFilters, PlayerRepository
from app.schemas.assignments import AssignmentCreate
from app.schemas.common import Page, PageParams
from app.schemas.recruitment import (
    AssignScoutBody,
    BulkAddResult,
    CandidateDetail,
    CandidateMatch,
    CandidateOut,
    CriterionResult,
    RequirementCreate,
    RequirementOut,
    RequirementSummary,
    RequirementUpdate,
    StageHistoryEntry,
)
from app.services import assignments as assignment_service
from app.services.audit import record_audit
from app.services.notifications import notify
from app.services.players import build_summary, photo_thumb

NOT_FOUND = AppError(404, "not_found", "Requirement not found")
CANDIDATE_NOT_FOUND = AppError(404, "not_found", "Candidate not found")


# ======================================================================================
# discovery engine (shared by requirements, ad hoc search and comparison)
# ======================================================================================
@dataclass
class Criteria:
    q: str | None = None
    position: str | None = None
    min_age: int | None = None
    max_age: int | None = None
    nationality: str | None = None
    foot: str | None = None
    min_appearances: int | None = None
    ratings: dict[str, int] = field(default_factory=dict)  # attribute -> minimum average
    exclude_requirement_id: uuid.UUID | None = None


@dataclass
class Facts:
    """Everything needed to judge a player against criteria and to display them."""

    player: Player
    positions: list[str]
    appearances: int | None
    goals: int | None
    assists: int | None
    ratings: dict[str, float]
    report_count: int


def _avg_rating(org_id: uuid.UUID, attribute: str):
    return (
        select(func.avg(ScoutingReportRating.rating))
        .join(ScoutingReport, ScoutingReport.id == ScoutingReportRating.report_id)
        .where(
            ScoutingReport.player_id == Player.id,
            ScoutingReport.organization_id == org_id,
            ScoutingReport.status == "approved",
            ScoutingReportRating.attribute == attribute,
        )
        .correlate(Player)
        .scalar_subquery()
    )


def _total_appearances():
    return (
        select(func.coalesce(func.sum(PlayerCareer.appearances), 0))
        .where(PlayerCareer.player_id == Player.id)
        .correlate(Player)
        .scalar_subquery()
    )


def _extra_conditions(org_id: uuid.UUID, c: Criteria) -> tuple:
    conds = []
    for attribute, minimum in c.ratings.items():
        conds.append(_avg_rating(org_id, attribute) >= minimum)  # NULL (no data) never matches
    if c.min_appearances:
        conds.append(_total_appearances() >= c.min_appearances)
    if c.exclude_requirement_id:
        conds.append(
            ~exists().where(
                RecruitmentCandidate.requirement_id == c.exclude_requirement_id,
                RecruitmentCandidate.player_id == Player.id,
            )
        )
    return tuple(conds)


async def gather_facts(
    db: AsyncSession, org_id: uuid.UUID, players: list[Player]
) -> dict[uuid.UUID, Facts]:
    ids = [p.id for p in players]
    if not ids:
        return {}
    secondaries: dict[uuid.UUID, list[str]] = {}
    for pid, pos in await db.execute(
        select(PlayerPosition.player_id, PlayerPosition.position).where(
            PlayerPosition.player_id.in_(ids)
        )
    ):
        secondaries.setdefault(pid, []).append(pos)

    totals: dict[uuid.UUID, list[int | None]] = {pid: [None, None, None] for pid in ids}
    for pid, app, goals, assists in await db.execute(
        select(
            PlayerCareer.player_id,
            PlayerCareer.appearances,
            PlayerCareer.goals,
            PlayerCareer.assists,
        ).where(PlayerCareer.player_id.in_(ids))
    ):
        for i, value in enumerate((app, goals, assists)):
            if value is not None:
                totals[pid][i] = (totals[pid][i] or 0) + value

    ratings: dict[uuid.UUID, dict[str, float]] = {pid: {} for pid in ids}
    for pid, attr, avg in await db.execute(
        select(
            ScoutingReport.player_id,
            ScoutingReportRating.attribute,
            func.avg(ScoutingReportRating.rating),
        )
        .join(ScoutingReportRating, ScoutingReportRating.report_id == ScoutingReport.id)
        .where(
            ScoutingReport.player_id.in_(ids),
            ScoutingReport.organization_id == org_id,
            ScoutingReport.status == "approved",
        )
        .group_by(ScoutingReport.player_id, ScoutingReportRating.attribute)
    ):
        ratings[pid][attr] = round(float(avg), 2)
    counts = dict(
        (
            await db.execute(
                select(ScoutingReport.player_id, func.count(ScoutingReport.id))
                .where(
                    ScoutingReport.player_id.in_(ids),
                    ScoutingReport.organization_id == org_id,
                    ScoutingReport.status == "approved",
                )
                .group_by(ScoutingReport.player_id)
            )
        ).all()
    )
    return {
        p.id: Facts(
            player=p,
            positions=(
                ([p.primary_position] if p.primary_position else [])
                + sorted(secondaries.get(p.id, []))
            ),
            appearances=totals[p.id][0], goals=totals[p.id][1], assists=totals[p.id][2],
            ratings=ratings[p.id], report_count=counts.get(p.id, 0),
        )
        for p in players
    }  # fmt: skip


def evaluate(f: Facts, c: Criteria) -> list[CriterionResult]:
    """Judges one player against every criterion. Transparent by design: each line shows what
    was required, what the player actually has, and whether it was met. There is no hidden
    composite score."""
    out: list[CriterionResult] = []
    p = f.player
    if c.position:
        out.append(
            CriterionResult(
                name="Position",
                required=c.position,
                actual=", ".join(f.positions) or None,
                met=c.position in f.positions,
            )
        )
    if c.min_age is not None or c.max_age is not None:
        age = age_on(p.date_of_birth)
        lo, hi = c.min_age, c.max_age
        met = (lo is None or age >= lo) and (hi is None or age <= hi)
        out.append(
            CriterionResult(
                name="Age", required=f"{lo or '…'}–{hi or '…'}", actual=str(age), met=met
            )
        )
    if c.nationality:
        out.append(
            CriterionResult(
                name="Nationality",
                required=c.nationality,
                actual=p.nationality,
                met=(p.nationality or "").lower() == c.nationality.lower(),
            )
        )
    if c.foot:
        out.append(
            CriterionResult(
                name="Preferred foot",
                required=c.foot,
                actual=p.preferred_foot,
                met=p.preferred_foot == c.foot,
            )
        )
    if c.min_appearances:
        out.append(
            CriterionResult(
                name="Career appearances",
                required=f"≥ {c.min_appearances}",
                actual=None if f.appearances is None else str(f.appearances),
                met=(f.appearances or 0) >= c.min_appearances,
            )
        )
    for attr, minimum in c.ratings.items():
        actual = f.ratings.get(attr)
        out.append(
            CriterionResult(
                name=f"{attr.replace('_', ' ').title()} rating",
                required=f"≥ {minimum}",
                actual=None if actual is None else f"{actual:.1f}",
                met=actual is not None and actual >= minimum,
            )
        )
    return out  # fmt: skip


async def find_candidates(
    db: AsyncSession, ctx: AuthContext, criteria: Criteria, page: PageParams
) -> Page[CandidateMatch]:
    ctx.require(catalog.RECRUITMENT_READ)
    ctx.require(catalog.PLAYERS_READ)
    org_id = ctx.require_org()
    repo = PlayerRepository(db, ctx)
    filters = PlayerFilters(
        q=criteria.q, position=criteria.position, nationality=criteria.nationality,
        foot=criteria.foot, min_age=criteria.min_age, max_age=criteria.max_age,
    )  # fmt: skip
    players, total = await repo.search(filters, page, _extra_conditions(org_id, criteria))
    facts = await gather_facts(db, org_id, players)
    clubs = await repo.current_clubs([p.id for p in players])
    pipeline_ids: set[uuid.UUID] = set()
    if criteria.exclude_requirement_id is None and players:
        pipeline_ids = set(
            await db.scalars(
                select(RecruitmentCandidate.player_id).where(
                    RecruitmentCandidate.organization_id == org_id,
                    RecruitmentCandidate.player_id.in_([p.id for p in players]),
                )
            )
        )
    items = [
        CandidateMatch(
            player=build_summary(p, ctx, clubs), criteria=evaluate(facts[p.id], criteria),
            report_count=facts[p.id].report_count, in_pipeline=p.id in pipeline_ids,
        )
        for p in players
    ]  # fmt: skip
    return Page(items=items, total=total, page=page.page, page_size=page.page_size)


# ======================================================================================
# requirements
# ======================================================================================
async def _load_requirement(
    db: AsyncSession, ctx: AuthContext, requirement_id: uuid.UUID, *, lock: bool = False
) -> RecruitmentRequirement:
    stmt = select(RecruitmentRequirement).where(
        RecruitmentRequirement.id == requirement_id,
        RecruitmentRequirement.organization_id == ctx.require_org(),
    )
    req = await db.scalar(stmt.with_for_update() if lock else stmt)
    if req is None:
        raise NOT_FOUND
    return req


async def _attributes(db: AsyncSession, requirement_id: uuid.UUID) -> dict[str, int]:
    rows = await db.execute(
        select(RequirementAttribute.attribute, RequirementAttribute.min_rating).where(
            RequirementAttribute.requirement_id == requirement_id
        )
    )
    return {a: m for a, m in rows}


def criteria_for(req: RecruitmentRequirement, attributes: dict[str, int]) -> Criteria:
    return Criteria(
        position=req.position, min_age=req.min_age, max_age=req.max_age,
        nationality=req.nationality, foot=req.preferred_foot,
        min_appearances=req.min_appearances, ratings=dict(attributes),
    )  # fmt: skip


async def _counts(db: AsyncSession, requirement_id: uuid.UUID) -> dict[str, int]:
    rows = await db.execute(
        select(RecruitmentCandidate.stage, func.count(RecruitmentCandidate.id))
        .where(RecruitmentCandidate.requirement_id == requirement_id)
        .group_by(RecruitmentCandidate.stage)
    )
    return dict(rows.all())


def _summary(req: RecruitmentRequirement, count: int) -> RequirementSummary:
    return RequirementSummary(
        id=req.id, title=req.title, position=req.position, priority=req.priority,
        status=req.status, candidate_count=count, created_at=req.created_at,
    )  # fmt: skip


async def _out(db: AsyncSession, req: RecruitmentRequirement) -> RequirementOut:
    counts = await _counts(db, req.id)
    author = (
        await db.scalar(select(User.full_name).where(User.id == req.created_by_user_id))
        if req.created_by_user_id
        else None
    )
    return RequirementOut(
        **_summary(req, sum(counts.values())).model_dump(),
        min_age=req.min_age, max_age=req.max_age, nationality=req.nationality,
        preferred_foot=req.preferred_foot, min_appearances=req.min_appearances,
        budget_min=req.budget_min, budget_max=req.budget_max, currency=req.currency,
        contract_notes=req.contract_notes, instructions=req.instructions,
        attributes=await _attributes(db, req.id), pipeline_counts=counts,
        created_by_name=author, allowed_statuses=sorted(REQUIREMENT_TRANSITIONS[req.status]),
    )  # fmt: skip


async def create_requirement(
    db: AsyncSession, ctx: AuthContext, data: RequirementCreate
) -> RequirementOut:
    ctx.require(catalog.RECRUITMENT_MANAGE)
    fields = data.model_dump(exclude={"attributes"})
    req = RecruitmentRequirement(
        organization_id=ctx.require_org(), created_by_user_id=ctx.user_id, **fields
    )
    db.add(req)
    await db.flush()
    db.add_all(
        RequirementAttribute(requirement_id=req.id, attribute=a, min_rating=m)
        for a, m in data.attributes.items()
    )
    await record_audit(
        db, action="requirement.create", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="requirement", target_id=str(req.id),
    )  # fmt: skip
    await db.commit()
    return await _out(db, req)


async def list_requirements(
    db: AsyncSession, ctx: AuthContext, page: PageParams, *, status=None, priority=None, q=None
) -> Page[RequirementSummary]:  # fmt: skip
    ctx.require(catalog.RECRUITMENT_READ)
    stmt = select(RecruitmentRequirement).where(
        RecruitmentRequirement.organization_id == ctx.require_org()
    )
    if status:
        stmt = stmt.where(RecruitmentRequirement.status == status)
    if priority:
        stmt = stmt.where(RecruitmentRequirement.priority == priority)
    if q:
        from app.repositories.clubs import escape_like

        stmt = stmt.where(RecruitmentRequirement.title.ilike(f"%{escape_like(q)}%", escape="\\"))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        await db.scalars(
            stmt.order_by(RecruitmentRequirement.created_at.desc())
            .offset(page.offset)
            .limit(page.page_size)
        )
    ).all()
    counts = (
        dict(
            (
                await db.execute(
                    select(RecruitmentCandidate.requirement_id, func.count(RecruitmentCandidate.id))
                    .where(RecruitmentCandidate.requirement_id.in_([r.id for r in rows]))
                    .group_by(RecruitmentCandidate.requirement_id)
                )
            ).all()
        )
        if rows
        else {}
    )
    return Page(
        items=[_summary(r, counts.get(r.id, 0)) for r in rows],
        total=total, page=page.page, page_size=page.page_size,
    )  # fmt: skip


async def get_requirement(
    db: AsyncSession, ctx: AuthContext, requirement_id: uuid.UUID
) -> RequirementOut:
    ctx.require(catalog.RECRUITMENT_READ)
    return await _out(db, await _load_requirement(db, ctx, requirement_id))


async def update_requirement(
    db: AsyncSession, ctx: AuthContext, requirement_id: uuid.UUID, data: RequirementUpdate
) -> RequirementOut:
    ctx.require(catalog.RECRUITMENT_MANAGE)
    req = await _load_requirement(db, ctx, requirement_id, lock=True)
    changes = data.model_dump(exclude_unset=True)
    attributes = changes.pop("attributes", None)
    new_status = changes.pop("status", None)
    if None in (
        changes.get("title", "x"),
        changes.get("position", "x"),
        changes.get("priority", "x"),
    ):
        raise AppError(422, "validation_error", "title, position and priority cannot be empty")

    if new_status is not None and new_status != req.status:
        if new_status not in REQUIREMENT_TRANSITIONS[req.status]:
            raise AppError(
                409, "invalid_transition", f"A {req.status} requirement cannot become {new_status}"
            )
    if req.status in ("fulfilled", "cancelled") and (changes or attributes is not None):
        raise AppError(409, "not_editable", f"A {req.status} requirement can no longer be edited")

    for field_name, value in changes.items():
        setattr(req, field_name, value)
    if req.min_age and req.max_age and req.min_age > req.max_age:
        raise AppError(422, "validation_error", "Minimum age cannot exceed maximum age")
    if (
        req.budget_min is not None
        and req.budget_max is not None
        and req.budget_min > req.budget_max
    ):
        raise AppError(422, "validation_error", "Minimum budget cannot exceed maximum budget")
    if (req.budget_min is not None or req.budget_max is not None) and not req.currency:
        raise AppError(422, "validation_error", "A currency is required with a budget")
    if new_status is not None:
        req.status = new_status
    if attributes is not None:
        for row in (
            await db.scalars(
                select(RequirementAttribute).where(RequirementAttribute.requirement_id == req.id)
            )
        ).all():
            await db.delete(row)
        await db.flush()
        db.add_all(
            RequirementAttribute(requirement_id=req.id, attribute=a, min_rating=m)
            for a, m in attributes.items()
        )
    await record_audit(
        db, action="requirement.update", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="requirement", target_id=str(req.id),
        metadata={"fields": sorted(data.model_dump(exclude_unset=True)), "status": req.status},
    )  # fmt: skip
    await db.commit()
    return await _out(db, req)


async def requirement_matches(
    db: AsyncSession, ctx: AuthContext, requirement_id: uuid.UUID, page: PageParams,
    exclude_pipeline: bool = True,
) -> Page[CandidateMatch]:  # fmt: skip
    ctx.require(catalog.RECRUITMENT_READ)
    req = await _load_requirement(db, ctx, requirement_id)
    criteria = criteria_for(req, await _attributes(db, req.id))
    if exclude_pipeline:
        criteria.exclude_requirement_id = req.id
    return await find_candidates(db, ctx, criteria, page)


# ======================================================================================
# pipeline
# ======================================================================================
async def _candidate_out(
    db: AsyncSession, ctx: AuthContext, rows: list[RecruitmentCandidate]
) -> list[CandidateOut]:
    if not rows:
        return []
    players = {
        p.id: p
        for p in (
            await db.scalars(select(Player).where(Player.id.in_({c.player_id for c in rows})))
        ).all()
    }
    titles = dict(
        (
            await db.execute(
                select(RecruitmentRequirement.id, RecruitmentRequirement.title).where(
                    RecruitmentRequirement.id.in_({c.requirement_id for c in rows})
                )
            )
        ).all()
    )
    assignment_ids = {c.assignment_id for c in rows if c.assignment_id}
    statuses = (
        dict(
            (
                await db.execute(
                    select(Assignment.id, Assignment.status).where(
                        Assignment.id.in_(assignment_ids)
                    )
                )
            ).all()
        )
        if assignment_ids
        else {}
    )
    return [
        CandidateOut(
            id=c.id, requirement_id=c.requirement_id, requirement_title=titles[c.requirement_id],
            player_id=c.player_id, player_name=players[c.player_id].full_name,
            age=age_on(players[c.player_id].date_of_birth),
            primary_position=players[c.player_id].primary_position, stage=c.stage, notes=c.notes,
            assignment_id=c.assignment_id, assignment_status=statuses.get(c.assignment_id),
            created_at=c.created_at, updated_at=c.updated_at,
            photo_thumb_url=photo_thumb(players[c.player_id], ctx),
        )
        for c in rows
    ]  # fmt: skip


async def _history(
    db: AsyncSession, candidate_id: uuid.UUID, from_stage: str | None, to_stage: str,
    actor: uuid.UUID | None, org_id: uuid.UUID, note: str | None,
) -> None:  # fmt: skip
    db.add(
        RecruitmentStageHistory(
            candidate_id=candidate_id,
            organization_id=org_id,
            from_stage=from_stage,
            to_stage=to_stage,
            actor_user_id=actor,
            note=note,
        )
    )


async def _add_one(
    db: AsyncSession, ctx: AuthContext, req: RecruitmentRequirement, player_id: uuid.UUID,
    notes: str | None,
) -> RecruitmentCandidate | None:  # fmt: skip
    """Adds a player to the pipeline; returns None when already present."""
    if await PlayerRepository(db, ctx).get_visible(player_id) is None:
        raise AppError(422, "invalid_player", "Player not found")
    candidate = RecruitmentCandidate(
        organization_id=req.organization_id, requirement_id=req.id, player_id=player_id,
        stage=DEFAULT_STAGE, added_by_user_id=ctx.user_id, notes=notes,
    )  # fmt: skip
    try:
        async with db.begin_nested():
            db.add(candidate)
            await db.flush()
    except IntegrityError:
        return None
    await _history(
        db,
        candidate.id,
        None,
        DEFAULT_STAGE,
        ctx.user_id,
        req.organization_id,
        "Added to the pipeline",
    )
    return candidate


def _open_requirement(req: RecruitmentRequirement) -> None:
    if req.status in ("fulfilled", "cancelled"):
        raise AppError(409, "requirement_closed", f"This requirement is {req.status}")


async def add_candidate(
    db: AsyncSession, ctx: AuthContext, requirement_id: uuid.UUID, player_id: uuid.UUID,
    notes: str | None,
) -> CandidateOut:  # fmt: skip
    ctx.require(catalog.RECRUITMENT_MANAGE)
    req = await _load_requirement(db, ctx, requirement_id)
    _open_requirement(req)
    candidate = await _add_one(db, ctx, req, player_id, notes)
    if candidate is None:
        raise AppError(409, "already_candidate", "This player is already in the pipeline")
    await record_audit(
        db, action="candidate.add", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="candidate", target_id=str(candidate.id),
    )  # fmt: skip
    await db.commit()
    return (await _candidate_out(db, ctx, [candidate]))[0]


async def add_candidates(
    db: AsyncSession, ctx: AuthContext, requirement_id: uuid.UUID, player_ids: list[uuid.UUID]
) -> BulkAddResult:
    ctx.require(catalog.RECRUITMENT_MANAGE)
    req = await _load_requirement(db, ctx, requirement_id)
    _open_requirement(req)
    added: list[RecruitmentCandidate] = []
    skipped = 0
    for pid in dict.fromkeys(player_ids):
        candidate = await _add_one(db, ctx, req, pid, None)
        if candidate is None:
            skipped += 1
        else:
            added.append(candidate)
    await record_audit(
        db, action="candidate.bulk_add", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="requirement", target_id=str(req.id),
        metadata={"added": len(added), "skipped": skipped},
    )  # fmt: skip
    await db.commit()
    return BulkAddResult(
        added=len(added), skipped=skipped, candidates=await _candidate_out(db, ctx, added)
    )


async def list_candidates(
    db: AsyncSession, ctx: AuthContext, requirement_id: uuid.UUID, stage: str | None,
    page: PageParams,
) -> Page[CandidateOut]:  # fmt: skip
    ctx.require(catalog.RECRUITMENT_READ)
    req = await _load_requirement(db, ctx, requirement_id)
    stmt = select(RecruitmentCandidate).where(RecruitmentCandidate.requirement_id == req.id)
    if stage:
        stmt = stmt.where(RecruitmentCandidate.stage == stage)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        (
            await db.scalars(
                stmt.order_by(RecruitmentCandidate.updated_at.desc(), RecruitmentCandidate.id)
                .offset(page.offset)
                .limit(page.page_size)
            )
        ).all()
    )
    return Page(
        items=await _candidate_out(db, ctx, rows),
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


async def _load_candidate(
    db: AsyncSession, ctx: AuthContext, candidate_id: uuid.UUID, *, lock: bool = False
) -> RecruitmentCandidate:
    stmt = select(RecruitmentCandidate).where(
        RecruitmentCandidate.id == candidate_id,
        RecruitmentCandidate.organization_id == ctx.require_org(),
    )
    c = await db.scalar(stmt.with_for_update() if lock else stmt)
    if c is None:
        raise CANDIDATE_NOT_FOUND
    return c


def _allowed(stage: str) -> list[str]:
    return [s for s in STAGES if can_move(stage, s)]


async def get_candidate(
    db: AsyncSession, ctx: AuthContext, candidate_id: uuid.UUID
) -> CandidateDetail:
    ctx.require(catalog.RECRUITMENT_READ)
    c = await _load_candidate(db, ctx, candidate_id)
    out = (await _candidate_out(db, ctx, [c]))[0]
    history = (
        await db.execute(
            select(RecruitmentStageHistory, User.full_name)
            .outerjoin(User, User.id == RecruitmentStageHistory.actor_user_id)
            .where(RecruitmentStageHistory.candidate_id == c.id)
            .order_by(RecruitmentStageHistory.seq)
        )
    ).all()
    return CandidateDetail(
        **out.model_dump(),
        history=[
            StageHistoryEntry(
                from_stage=h.from_stage, to_stage=h.to_stage, actor_name=name,
                note=h.note, created_at=h.created_at,
            )
            for h, name in history
        ],
        allowed_stages=_allowed(c.stage),
    )  # fmt: skip


async def _apply_stage(
    db: AsyncSession, ctx: AuthContext, c: RecruitmentCandidate, to: str, note: str | None
) -> None:
    previous, c.stage = c.stage, to
    await _history(db, c.id, previous, to, ctx.user_id, c.organization_id, note)
    await record_audit(
        db, action="candidate.stage", outcome="success", actor_user_id=ctx.user_id,
        organization_id=c.organization_id, target_type="candidate", target_id=str(c.id),
        metadata={"from": previous, "to": to},
    )  # fmt: skip
    req = await db.get(RecruitmentRequirement, c.requirement_id)
    player = await db.get(Player, c.player_id)
    if req and req.created_by_user_id and req.created_by_user_id != ctx.user_id:
        await notify(
            db, user_id=req.created_by_user_id, type="recruitment_status_updated",
            title=(
                f"{player.full_name if player else 'Candidate'}: "
                f"{previous.replace('_', ' ')} → {to.replace('_', ' ')}"
            ),
            body=f"Requirement: {req.title}", link_path=f"/recruitment/{req.id}",
            organization_id=c.organization_id,
        )  # fmt: skip


async def move_stage(
    db: AsyncSession, ctx: AuthContext, candidate_id: uuid.UUID, to: str, note: str | None
) -> CandidateDetail:
    ctx.require(catalog.RECRUITMENT_MANAGE)
    c = await _load_candidate(db, ctx, candidate_id, lock=True)
    if c.stage == to:
        raise AppError(409, "same_stage", "The candidate is already at this stage")
    if not can_move(c.stage, to):
        raise AppError(
            409, "invalid_transition", f"A candidate at '{c.stage}' cannot move to '{to}'"
        )
    req = await db.get(RecruitmentRequirement, c.requirement_id)
    if (
        req is not None
        and req.status in ("fulfilled", "cancelled")
        and to not in ("archived", "rejected")
    ):
        raise AppError(409, "requirement_closed", f"This requirement is {req.status}")
    await _apply_stage(db, ctx, c, to, note.strip() if note else None)
    await db.commit()
    return await get_candidate(db, ctx, candidate_id)


async def assign_scout(
    db: AsyncSession, ctx: AuthContext, candidate_id: uuid.UUID, data: AssignScoutBody
) -> CandidateDetail:
    """Creates a scouting assignment about this player and moves the candidate on."""
    ctx.require(catalog.RECRUITMENT_MANAGE)
    ctx.require(catalog.ASSIGNMENTS_MANAGE)
    c = await _load_candidate(db, ctx, candidate_id, lock=True)
    req = await db.get(RecruitmentRequirement, c.requirement_id)
    _open_requirement(req)
    if c.stage in ("rejected", "archived", "signed"):
        raise AppError(
            409, "invalid_transition", f"A candidate at '{c.stage}' cannot be assigned a scout"
        )
    player = await db.get(Player, c.player_id)
    created = await assignment_service.create_assignment(
        db, ctx,
        AssignmentCreate(
            scout_id=data.scout_id, target_type="player", target_id=c.player_id,
            title=f"Evaluate {player.full_name} for {req.title}"[:200],
            instructions=data.instructions, deadline=data.deadline, assign_now=True,
        ),
    )  # fmt: skip
    c = await _load_candidate(db, ctx, candidate_id, lock=True)  # create_assignment committed
    c.assignment_id = created.id
    if c.stage in ("discovered", "under_evaluation", "shortlisted") and can_move(
        c.stage, "scout_assigned"
    ):
        await _apply_stage(db, ctx, c, "scout_assigned", f"Scout assigned: {created.scout_name}")
    await db.commit()
    return await get_candidate(db, ctx, candidate_id)


# What a report event does to a candidate's stage. Forward moves never pull a candidate back
# (someone further along, say in negotiation, is left alone); the one step back is a report
# sent for revision, because the scout is working on it again.
_REPORT_EVENT_TARGET = {"submitted": "report_submitted", "approved": "under_review"}
_REPORT_EVENT_NOTE = {
    "submitted": "Automatic: a scouting report was submitted",
    "approved": "Automatic: the scouting report was approved",
    "revision_requested": "Automatic: the report was sent back to the scout for changes",
}


async def sync_with_report(
    db: AsyncSession, ctx: AuthContext, report: ScoutingReport, event: str
) -> int:
    """Moves this organization's open candidates for the report's player along the pipeline
    when the report is submitted, approved or sent back. The caller commits. Returns how many
    candidates moved. A rejected report changes nothing: the manager decides what is next."""
    if event not in _REPORT_EVENT_NOTE:
        return 0
    query = (
        select(RecruitmentCandidate)
        .join(
            RecruitmentRequirement,
            RecruitmentRequirement.id == RecruitmentCandidate.requirement_id,
        )
        .where(
            RecruitmentCandidate.organization_id == report.organization_id,
            RecruitmentCandidate.player_id == report.player_id,
            RecruitmentCandidate.stage.in_(STAGE_ORDER[:-1]),  # active: not signed/out
            RecruitmentRequirement.status.in_(("draft", "open", "on_hold")),
        )
    )
    # A candidate already tied to a different assignment is waiting on that scout's work.
    if report.assignment_id is not None:
        query = query.where(
            or_(
                RecruitmentCandidate.assignment_id.is_(None),
                RecruitmentCandidate.assignment_id == report.assignment_id,
            )
        )
    else:
        query = query.where(RecruitmentCandidate.assignment_id.is_(None))

    moved = 0
    for c in (await db.scalars(query.with_for_update(of=RecruitmentCandidate))).all():
        target = _REPORT_EVENT_TARGET.get(event)
        if target is None:  # revision requested: step back only from the report stages
            if c.stage not in ("report_submitted", "under_review"):
                continue
            target = "scout_assigned"
        elif STAGE_ORDER.index(c.stage) >= STAGE_ORDER.index(target):
            continue
        await _apply_stage(db, ctx, c, target, _REPORT_EVENT_NOTE[event])
        moved += 1
    return moved
