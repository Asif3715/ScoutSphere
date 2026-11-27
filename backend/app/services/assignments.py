import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domain.scouting import (
    MANAGER_TRANSITIONS,
    OPEN_ASSIGNMENT_STATUSES,
    SCOUT_TRANSITIONS,
)
from app.models.assignment import Assignment, AssignmentHistory
from app.models.club import Club
from app.models.competition import Competition, Match
from app.models.organization import OrganizationMember
from app.models.player import Player
from app.models.report import ScoutingReport
from app.models.scout import ScoutProfile
from app.models.user import User
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.repositories.players import PlayerRepository
from app.repositories.scoped import visible
from app.schemas.assignments import (
    AssignmentCreate,
    AssignmentDetail,
    AssignmentOut,
    AssignmentReportRef,
    AssignmentSummary,
    AssignmentUpdate,
    HistoryEntry,
)
from app.schemas.common import Page, PageParams
from app.services.audit import record_audit
from app.services.competitions import get_visible_competition
from app.services.notifications import notify

NOT_FOUND = AppError(404, "not_found", "Assignment not found")
EDITABLE = {"draft", "assigned", "accepted", "in_progress"}


def _now() -> datetime:
    return datetime.now(UTC)


# ---- helpers -------------------------------------------------------------------------
async def my_scout_profile(db: AsyncSession, ctx: AuthContext) -> ScoutProfile | None:
    return await db.scalar(
        select(ScoutProfile).where(
            ScoutProfile.organization_id == ctx.require_org(),
            ScoutProfile.user_id == ctx.user_id,
            ScoutProfile.is_active.is_(True),
        )
    )


def _visibility(ctx: AuthContext, my_profile_id: uuid.UUID | None) -> ColumnElement[bool]:
    """Managers see every assignment of the organization. Everyone else sees only the
    non-draft assignments given to them."""
    base = Assignment.organization_id == ctx.organization_id
    if ctx.has(catalog.ASSIGNMENTS_MANAGE):
        return base
    if my_profile_id is None:
        return base & (Assignment.id.is_(None))  # matches nothing
    return base & (Assignment.scout_profile_id == my_profile_id) & (Assignment.status != "draft")


def _overdue(a: Assignment) -> bool:
    return a.deadline is not None and a.deadline < _now() and a.status in OPEN_ASSIGNMENT_STATUSES


async def _labels(
    db: AsyncSession, rows: list[Assignment]
) -> dict[uuid.UUID, tuple[uuid.UUID, str]]:
    out: dict[uuid.UUID, tuple[uuid.UUID, str]] = {}
    match_ids = [a.match_id for a in rows if a.match_id]
    if match_ids:
        home, away = Club.__table__.alias("h"), Club.__table__.alias("a")
        res = await db.execute(
            select(Match.id, home.c.name, away.c.name)
            .join(home, home.c.id == Match.home_club_id)
            .join(away, away.c.id == Match.away_club_id)
            .where(Match.id.in_(match_ids))
        )
        names = {mid: f"{h} v {a}" for mid, h, a in res}
        for a in rows:
            if a.match_id:
                out[a.id] = (a.match_id, names.get(a.match_id, "Match"))
    comp_ids = [a.competition_id for a in rows if a.competition_id]
    if comp_ids:
        names = dict(
            (
                await db.execute(
                    select(Competition.id, Competition.name).where(Competition.id.in_(comp_ids))
                )
            ).all()
        )
        for a in rows:
            if a.competition_id:
                out[a.id] = (a.competition_id, names.get(a.competition_id, "Competition"))
    player_ids = [a.player_id for a in rows if a.player_id]
    if player_ids:
        names = dict(
            (
                await db.execute(
                    select(Player.id, Player.full_name).where(Player.id.in_(player_ids))
                )
            ).all()
        )
        for a in rows:
            if a.player_id:
                out[a.id] = (a.player_id, names.get(a.player_id, "Player"))
    return out


async def _outs(db: AsyncSession, rows: list[Assignment]) -> list[AssignmentOut]:
    if not rows:
        return []
    labels = await _labels(db, rows)
    scouts = dict(
        (
            await db.execute(
                select(ScoutProfile.id, User.full_name)
                .join(User, User.id == ScoutProfile.user_id)
                .where(ScoutProfile.id.in_({a.scout_profile_id for a in rows}))
            )
        ).all()
    )
    counts = dict(
        (
            await db.execute(
                select(ScoutingReport.assignment_id, func.count(ScoutingReport.id))
                .where(ScoutingReport.assignment_id.in_([a.id for a in rows]))
                .group_by(ScoutingReport.assignment_id)
            )
        ).all()
    )
    return [
        AssignmentOut(
            id=a.id, title=a.title, status=a.status, target_type=a.target_type,
            target_id=labels[a.id][0], target_label=labels[a.id][1], scout_id=a.scout_profile_id,
            scout_name=scouts.get(a.scout_profile_id, "Unknown"), deadline=a.deadline,
            is_overdue=_overdue(a), instructions=a.instructions, criteria=a.criteria,
            report_count=counts.get(a.id, 0), created_at=a.created_at,
        )
        for a in rows
    ]  # fmt: skip


async def _load(
    db: AsyncSession, ctx: AuthContext, assignment_id: uuid.UUID, *, lock: bool = False
) -> Assignment:
    ctx.require(catalog.ASSIGNMENTS_READ)
    profile = await my_scout_profile(db, ctx)
    stmt = select(Assignment).where(
        Assignment.id == assignment_id, _visibility(ctx, profile.id if profile else None)
    )
    a = await db.scalar(stmt.with_for_update() if lock else stmt)
    if a is None:
        raise NOT_FOUND
    return a


async def _record(
    db: AsyncSession, ctx_user: uuid.UUID | None, a: Assignment, from_status: str | None,
    to_status: str, note: str | None = None,
) -> None:  # fmt: skip
    db.add(
        AssignmentHistory(
            assignment_id=a.id,
            organization_id=a.organization_id,
            from_status=from_status,
            to_status=to_status,
            actor_user_id=ctx_user,
            note=note,
        )
    )


async def _scout_user(db: AsyncSession, a: Assignment) -> uuid.UUID | None:
    return await db.scalar(
        select(ScoutProfile.user_id).where(ScoutProfile.id == a.scout_profile_id)
    )


# ---- queries -------------------------------------------------------------------------
async def list_assignments(
    db: AsyncSession, ctx: AuthContext, page: PageParams, *, status=None, scout_id=None,
    target_type=None, overdue: bool = False, mine: bool = False,
) -> Page[AssignmentOut]:  # fmt: skip
    ctx.require(catalog.ASSIGNMENTS_READ)
    profile = await my_scout_profile(db, ctx)
    stmt = select(Assignment).where(_visibility(ctx, profile.id if profile else None))
    if status:
        stmt = stmt.where(Assignment.status == status)
    if scout_id:
        stmt = stmt.where(Assignment.scout_profile_id == scout_id)
    if target_type:
        stmt = stmt.where(Assignment.target_type == target_type)
    if mine:
        stmt = stmt.where(Assignment.scout_profile_id == (profile.id if profile else None))
    if overdue:
        stmt = stmt.where(
            Assignment.deadline < _now(), Assignment.status.in_(OPEN_ASSIGNMENT_STATUSES)
        )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        await db.scalars(
            stmt.order_by(Assignment.deadline.asc().nulls_last(), Assignment.created_at.desc())
            .offset(page.offset)
            .limit(page.page_size)
        )
    ).all()
    return Page(
        items=await _outs(db, list(rows)), total=total, page=page.page, page_size=page.page_size
    )


async def _allowed_for(db: AsyncSession, ctx: AuthContext, a: Assignment) -> list[str]:
    profile = await my_scout_profile(db, ctx)
    allowed: set[str] = set()
    if ctx.has(catalog.ASSIGNMENTS_MANAGE):
        allowed |= MANAGER_TRANSITIONS.get(a.status, set())
    if profile and profile.id == a.scout_profile_id:
        allowed |= SCOUT_TRANSITIONS.get(a.status, set())
    return sorted(allowed)


async def get_assignment(
    db: AsyncSession, ctx: AuthContext, assignment_id: uuid.UUID
) -> AssignmentDetail:
    a = await _load(db, ctx, assignment_id)
    out = (await _outs(db, [a]))[0]
    history = (
        await db.execute(
            select(AssignmentHistory, User.full_name)
            .outerjoin(User, User.id == AssignmentHistory.actor_user_id)
            .where(AssignmentHistory.assignment_id == a.id)
            .order_by(AssignmentHistory.seq)
        )
    ).all()
    reports = (
        await db.execute(
            select(ScoutingReport, Player.full_name)
            .join(Player, Player.id == ScoutingReport.player_id)
            .where(ScoutingReport.assignment_id == a.id)
            .order_by(ScoutingReport.created_at)
        )
    ).all()
    profile = await my_scout_profile(db, ctx)
    return AssignmentDetail(
        **out.model_dump(),
        history=[
            HistoryEntry(
                from_status=h.from_status, to_status=h.to_status, actor_name=name,
                note=h.note, created_at=h.created_at,
            )
            for h, name in history
        ],
        reports=[
            AssignmentReportRef(
                id=r.id, player_name=pname, status=r.status, recommendation=r.recommendation
            )
            for r, pname in reports
        ],
        allowed_transitions=await _allowed_for(db, ctx, a),
        is_mine=bool(profile and profile.id == a.scout_profile_id),
    )  # fmt: skip


async def summary(db: AsyncSession, ctx: AuthContext) -> AssignmentSummary:
    ctx.require(catalog.ASSIGNMENTS_READ)
    profile = await my_scout_profile(db, ctx)
    vis = _visibility(ctx, profile.id if profile else None)
    counts = dict(
        (
            await db.execute(
                select(Assignment.status, func.count(Assignment.id))
                .where(vis)
                .group_by(Assignment.status)
            )
        ).all()
    )
    now = _now()
    open_ = Assignment.status.in_(OPEN_ASSIGNMENT_STATUSES)
    overdue = await db.scalar(
        select(func.count(Assignment.id)).where(vis, open_, Assignment.deadline < now)
    )
    soon = await db.scalar(
        select(func.count(Assignment.id)).where(
            vis, open_, Assignment.deadline >= now, Assignment.deadline < now + timedelta(hours=48)
        )
    )
    return AssignmentSummary(counts=counts, overdue=overdue or 0, due_soon=soon or 0)


# ---- commands ------------------------------------------------------------------------
async def _assignable_scout(
    db: AsyncSession, ctx: AuthContext, scout_id: uuid.UUID
) -> ScoutProfile:
    profile = await db.scalar(
        select(ScoutProfile).where(
            ScoutProfile.id == scout_id,
            ScoutProfile.organization_id == ctx.require_org(),
            ScoutProfile.is_active.is_(True),
            exists().where(
                OrganizationMember.organization_id == ScoutProfile.organization_id,
                OrganizationMember.user_id == ScoutProfile.user_id,
                OrganizationMember.status == "active",
            ),
        )
    )
    if profile is None:
        raise AppError(422, "invalid_scout", "Scout not found or not active")
    return profile


async def _check_target(
    db: AsyncSession, ctx: AuthContext, target_type: str, target_id: uuid.UUID
) -> dict:
    ok: bool
    if target_type == "match":
        ok = (
            await db.scalar(
                select(Match.id).where(
                    Match.id == target_id, visible(Match.organization_id, ctx.organization_id)
                )
            )
        ) is not None
        key = "match_id"
    elif target_type == "competition":
        try:
            await get_visible_competition(db, ctx, target_id)
            ok = True
        except AppError:
            ok = False
        key = "competition_id"
    else:
        ok = (await PlayerRepository(db, ctx).get_visible(target_id)) is not None
        key = "player_id"
    if not ok:
        raise AppError(422, "invalid_target", "The selected target was not found")
    return {key: target_id}


def _check_deadline(deadline: datetime | None) -> None:
    if deadline is not None and deadline <= _now():
        raise AppError(422, "deadline_in_past", "The deadline must be in the future")


async def create_assignment(
    db: AsyncSession, ctx: AuthContext, data: AssignmentCreate
) -> AssignmentDetail:
    ctx.require(catalog.ASSIGNMENTS_MANAGE)
    org_id = ctx.require_org()
    scout = await _assignable_scout(db, ctx, data.scout_id)
    target = await _check_target(db, ctx, data.target_type, data.target_id)
    _check_deadline(data.deadline)

    a = Assignment(
        organization_id=org_id, scout_profile_id=scout.id, created_by_user_id=ctx.user_id,
        target_type=data.target_type, title=data.title.strip(), instructions=data.instructions,
        criteria=data.criteria, deadline=data.deadline, status="draft", **target,
    )  # fmt: skip
    db.add(a)
    await db.flush()
    await _record(db, ctx.user_id, a, None, "draft")
    await record_audit(
        db, action="assignment.create", outcome="success", actor_user_id=ctx.user_id,
        organization_id=org_id, target_type="assignment", target_id=str(a.id),
    )  # fmt: skip
    if data.assign_now:
        await _apply(db, ctx, a, "assigned", None)
    await db.commit()
    return await get_assignment(db, ctx, a.id)


async def update_assignment(
    db: AsyncSession, ctx: AuthContext, assignment_id: uuid.UUID, data: AssignmentUpdate
) -> AssignmentDetail:
    ctx.require(catalog.ASSIGNMENTS_MANAGE)
    a = await _load(db, ctx, assignment_id, lock=True)
    if a.status not in EDITABLE:
        raise AppError(409, "not_editable", f"A {a.status} assignment can no longer be edited")
    changes = data.model_dump(exclude_unset=True)
    if None in (changes.get("title", "x"),):
        raise AppError(422, "validation_error", "Title cannot be empty")
    if "scout_id" in changes:
        if changes["scout_id"] is None:
            raise AppError(422, "validation_error", "scout_id cannot be empty")
        if a.status not in ("draft", "assigned"):
            raise AppError(409, "scout_locked", "The scout cannot change once work has started")
        scout = await _assignable_scout(db, ctx, changes.pop("scout_id"))
        if scout.id != a.scout_profile_id:
            a.scout_profile_id = scout.id
            if a.status == "assigned":  # tell the new scout
                await _notify_assigned(db, ctx, a)
    if "deadline" in changes:
        _check_deadline(changes["deadline"])
        a.reminder_sent_at = None  # a new deadline gets a fresh reminder
    for field, value in changes.items():
        setattr(a, field, value.strip() if field == "title" and value else value)
    await _record(
        db,
        ctx.user_id,
        a,
        a.status,
        a.status,
        f"Edited: {', '.join(sorted(data.model_dump(exclude_unset=True)))}",
    )
    await record_audit(
        db, action="assignment.update", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="assignment", target_id=str(a.id),
        metadata={"fields": sorted(data.model_dump(exclude_unset=True))},
    )  # fmt: skip
    await db.commit()
    return await get_assignment(db, ctx, a.id)


async def _notify_assigned(db: AsyncSession, ctx: AuthContext, a: Assignment) -> None:
    user_id = await _scout_user(db, a)
    if user_id:
        due = f" Due {a.deadline:%Y-%m-%d %H:%M} UTC." if a.deadline else ""
        await notify(
            db, user_id=user_id, type="assignment_assigned", title=f"New assignment: {a.title}",
            body=f"You have been assigned a scouting task.{due}",
            link_path=f"/assignments/{a.id}", organization_id=a.organization_id,
        )  # fmt: skip


async def _apply(
    db: AsyncSession, ctx: AuthContext, a: Assignment, to: str, note: str | None
) -> None:
    """Changes status, writes history, and sends the notification for that step."""
    previous, a.status = a.status, to
    await _record(db, ctx.user_id, a, previous, to, note)
    await record_audit(
        db, action="assignment.transition", outcome="success", actor_user_id=ctx.user_id,
        organization_id=a.organization_id, target_type="assignment", target_id=str(a.id),
        metadata={"from": previous, "to": to},
    )  # fmt: skip
    link = f"/assignments/{a.id}"
    scout_user = await _scout_user(db, a)
    if to == "assigned":
        await _notify_assigned(db, ctx, a)
    elif to == "cancelled" and previous != "draft" and scout_user:
        await notify(
            db, user_id=scout_user, type="assignment_cancelled",
            title=f"Assignment cancelled: {a.title}", body=note, link_path=link,
            organization_id=a.organization_id,
        )  # fmt: skip
    elif to == "accepted" and a.created_by_user_id and a.created_by_user_id != ctx.user_id:
        await notify(
            db, user_id=a.created_by_user_id, type="assignment_accepted",
            title=f"Assignment accepted: {a.title}", link_path=link,
            organization_id=a.organization_id,
        )  # fmt: skip
    elif to == "submitted" and a.created_by_user_id and a.created_by_user_id != ctx.user_id:
        await notify(
            db, user_id=a.created_by_user_id, type="assignment_submitted",
            title=f"Assignment submitted for review: {a.title}", link_path=link,
            organization_id=a.organization_id,
        )  # fmt: skip
    elif to in ("approved", "rejected") and scout_user:
        await notify(
            db, user_id=scout_user, type=f"assignment_{to}", title=f"Assignment {to}: {a.title}",
            body=note, link_path=link, organization_id=a.organization_id,
        )  # fmt: skip
    elif to == "in_progress" and previous in ("submitted", "under_review") and scout_user:
        await notify(
            db, user_id=scout_user, type="assignment_returned",
            title=f"Assignment returned for changes: {a.title}", body=note, link_path=link,
            organization_id=a.organization_id,
        )  # fmt: skip


async def transition(
    db: AsyncSession, ctx: AuthContext, assignment_id: uuid.UUID, to: str, note: str | None
) -> AssignmentDetail:
    a = await _load(db, ctx, assignment_id, lock=True)
    allowed = set(await _allowed_for(db, ctx, a))
    if to not in allowed:
        either = to in MANAGER_TRANSITIONS.get(a.status, set()) | SCOUT_TRANSITIONS.get(
            a.status, set()
        )
        if either:  # a legal step, but not yours to take
            raise AppError(403, "forbidden", "You are not allowed to make this change")
        raise AppError(409, "invalid_transition", f"A {a.status} assignment cannot become {to}")
    note = note.strip() if note else None

    if to == "assigned":
        await _assignable_scout(db, ctx, a.scout_profile_id)
        if a.deadline is not None:
            _check_deadline(a.deadline)
    if to in ("rejected", "in_progress") and a.status in ("submitted", "under_review") and not note:
        raise AppError(422, "note_required", "Explain what needs to change")
    if to == "submitted":
        statuses = list(
            await db.scalars(
                select(ScoutingReport.status).where(ScoutingReport.assignment_id == a.id)
            )
        )
        if not statuses:
            raise AppError(409, "no_reports", "Write and submit at least one report first")
        if any(s in ("draft", "revision_requested") for s in statuses):
            raise AppError(
                409,
                "reports_incomplete",
                "Submit all your reports before submitting the assignment",
            )
    if to == "approved":
        statuses = list(
            await db.scalars(
                select(ScoutingReport.status).where(ScoutingReport.assignment_id == a.id)
            )
        )
        if "approved" not in statuses or any(s not in ("approved", "rejected") for s in statuses):
            raise AppError(
                409, "reports_not_reviewed", "Review every report before approving the assignment"
            )
    await _apply(db, ctx, a, to, note)
    await db.commit()
    return await get_assignment(db, ctx, a.id)


async def return_to_scout_for_revision(
    db: AsyncSession, ctx: AuthContext, assignment_id: uuid.UUID, note: str
) -> None:
    """Used by report review: a revision request re-opens a submitted assignment."""
    a = await db.scalar(select(Assignment).where(Assignment.id == assignment_id).with_for_update())
    if a is not None and a.status in ("submitted", "under_review"):
        await _apply(db, ctx, a, "in_progress", note)


# ---- background job ------------------------------------------------------------------
async def send_deadline_reminders(
    db: AsyncSession, *, within_hours: int = 24, now: datetime | None = None
) -> int:
    """Notifies scouts of open assignments due soon. Idempotent: each deadline is reminded
    once. Meant to run on a schedule (cron / worker); no request context involved."""
    now = now or _now()
    rows = (
        await db.scalars(
            select(Assignment).where(
                Assignment.status.in_(OPEN_ASSIGNMENT_STATUSES),
                Assignment.deadline.is_not(None),
                Assignment.deadline > now,
                Assignment.deadline <= now + timedelta(hours=within_hours),
                Assignment.reminder_sent_at.is_(None),
            )
        )
    ).all()
    sent = 0
    for a in rows:
        user_id = await _scout_user(db, a)
        if user_id:
            await notify(
                db, user_id=user_id, type="assignment_deadline",
                title=f"Deadline approaching: {a.title}",
                body=f"Due {a.deadline:%Y-%m-%d %H:%M} UTC.",
                link_path=f"/assignments/{a.id}", organization_id=a.organization_id,
            )  # fmt: skip
            sent += 1
        a.reminder_sent_at = now
    await db.commit()
    return sent
