import uuid
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domain.scouting import EDITABLE_REPORT_STATUSES, MIN_RATINGS_TO_SUBMIT
from app.models.assignment import Assignment
from app.models.club import Club
from app.models.competition import Match
from app.models.organization import OrganizationMember
from app.models.player import Player
from app.models.rbac import Role
from app.models.report import (
    ScoutingReport,
    ScoutingReportRating,
    ScoutingReportReview,
    ScoutingReportVersion,
)
from app.models.scout import ScoutProfile
from app.models.user import User
from app.permissions import catalog
from app.permissions.catalog import ROLES
from app.permissions.context import AuthContext
from app.repositories.players import PlayerRepository
from app.repositories.scoped import usable_club, visible
from app.schemas.common import Page, PageParams
from app.schemas.reports import (
    ReportCreate,
    ReportDetail,
    ReportSummary,
    ReportUpdate,
    ReviewBody,
    ReviewOut,
    VersionRef,
)
from app.services.assignments import _apply, my_scout_profile, return_to_scout_for_revision
from app.services.audit import record_audit
from app.services.notifications import notify

NOT_FOUND = AppError(404, "not_found", "Report not found")
TEXT_FIELDS = ["strengths", "weaknesses", "development_areas", "general_observations"]


# ---- visibility ----------------------------------------------------------------------
async def _any_profile(db: AsyncSession, ctx: AuthContext) -> ScoutProfile | None:
    return await db.scalar(
        select(ScoutProfile).where(
            ScoutProfile.organization_id == ctx.require_org(), ScoutProfile.user_id == ctx.user_id
        )
    )


async def _visibility(db: AsyncSession, ctx: AuthContext) -> ColumnElement[bool]:
    """Reviewers see everything; writers see their own reports; readers see approved ones."""
    base = ScoutingReport.organization_id == ctx.require_org()
    if ctx.has(catalog.REPORTS_REVIEW):
        return base
    conds: list[ColumnElement[bool]] = []
    if ctx.has(catalog.REPORTS_WRITE):
        profile = await _any_profile(db, ctx)
        if profile:
            conds.append(ScoutingReport.scout_profile_id == profile.id)
    if ctx.has(catalog.REPORTS_READ):
        conds.append(ScoutingReport.status == "approved")
    return base & or_(*conds) if conds else false()


async def _load(
    db: AsyncSession, ctx: AuthContext, report_id: uuid.UUID, *, lock: bool = False
) -> ScoutingReport:
    stmt = select(ScoutingReport).where(ScoutingReport.id == report_id, await _visibility(db, ctx))
    r = await db.scalar(stmt.with_for_update() if lock else stmt)
    if r is None:
        raise NOT_FOUND
    return r


# ---- serialization -------------------------------------------------------------------
async def _names(db: AsyncSession, rows: list[ScoutingReport]):
    ids = lambda f: {getattr(r, f) for r in rows if getattr(r, f)}  # noqa: E731
    players = dict(
        (
            await db.execute(
                select(Player.id, Player.full_name).where(Player.id.in_(ids("player_id")))
            )
        ).all()
    )
    scouts = dict(
        (
            await db.execute(
                select(ScoutProfile.id, User.full_name)
                .join(User, User.id == ScoutProfile.user_id)
                .where(ScoutProfile.id.in_(ids("scout_profile_id")))
            )
        ).all()
    )
    titles = dict(
        (
            await db.execute(
                select(Assignment.id, Assignment.title).where(
                    Assignment.id.in_(ids("assignment_id"))
                )
            )
        ).all()
    )
    matches: dict[uuid.UUID, str] = {}
    if ids("match_id"):
        from sqlalchemy.orm import aliased

        home, away = aliased(Club), aliased(Club)
        res = await db.execute(
            select(Match.id, home.name, away.name)
            .join(home, home.id == Match.home_club_id)
            .join(away, away.id == Match.away_club_id)
            .where(Match.id.in_(ids("match_id")))
        )
        matches = {mid: f"{h} v {a}" for mid, h, a in res}
    return players, scouts, titles, matches


def _summary(r: ScoutingReport, n) -> ReportSummary:
    players, scouts, titles, matches = n
    return ReportSummary(
        id=r.id, status=r.status, player_id=r.player_id, player_name=players.get(r.player_id, "?"),
        scout_id=r.scout_profile_id, scout_name=scouts.get(r.scout_profile_id, "?"),
        match_label=matches.get(r.match_id) if r.match_id else None, observed_on=r.observed_on,
        recommendation=r.recommendation, assignment_id=r.assignment_id,
        assignment_title=titles.get(r.assignment_id) if r.assignment_id else None,
        current_version=r.current_version, submitted_at=r.submitted_at,
    )  # fmt: skip


async def list_reports(
    db: AsyncSession, ctx: AuthContext, page: PageParams, *, status=None, player_id=None,
    scout_id=None, match_id=None, assignment_id=None, recommendation=None, mine: bool = False,
) -> Page[ReportSummary]:  # fmt: skip
    if not ctx.has(catalog.REPORTS_WRITE):
        ctx.require(catalog.REPORTS_READ)
    stmt = select(ScoutingReport).where(await _visibility(db, ctx))
    for column, value in (
        (ScoutingReport.status, status), (ScoutingReport.player_id, player_id),
        (ScoutingReport.scout_profile_id, scout_id), (ScoutingReport.match_id, match_id),
        (ScoutingReport.assignment_id, assignment_id),
        (ScoutingReport.recommendation, recommendation),
    ):  # fmt: skip
        if value:
            stmt = stmt.where(column == value)
    if mine:
        profile = await _any_profile(db, ctx)
        stmt = stmt.where(ScoutingReport.scout_profile_id == (profile.id if profile else None))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        (
            await db.scalars(
                stmt.order_by(ScoutingReport.observed_on.desc(), ScoutingReport.created_at.desc())
                .offset(page.offset)
                .limit(page.page_size)
            )
        ).all()
    )
    n = await _names(db, rows)
    return Page(
        items=[_summary(r, n) for r in rows], total=total, page=page.page, page_size=page.page_size
    )


async def _ratings(db: AsyncSession, report_id: uuid.UUID) -> dict[str, int]:
    rows = await db.execute(
        select(ScoutingReportRating.attribute, ScoutingReportRating.rating).where(
            ScoutingReportRating.report_id == report_id
        )
    )
    return {a: v for a, v in rows}


async def _detail(db: AsyncSession, ctx: AuthContext, r: ScoutingReport) -> ReportDetail:
    n = await _names(db, [r])
    base = _summary(r, n)
    profile = await _any_profile(db, ctx)
    mine = bool(profile and profile.id == r.scout_profile_id)
    versions = (
        await db.scalars(
            select(ScoutingReportVersion)
            .where(ScoutingReportVersion.report_id == r.id)
            .order_by(ScoutingReportVersion.version)
        )
    ).all()
    reviews = (
        await db.execute(
            select(ScoutingReportReview, User.full_name)
            .outerjoin(User, User.id == ScoutingReportReview.reviewer_user_id)
            .where(ScoutingReportReview.report_id == r.id)
            .order_by(ScoutingReportReview.version, ScoutingReportReview.created_at)
        )
    ).all()
    club_name = (
        await db.scalar(select(Club.name).where(Club.id == r.club_id)) if r.club_id else None
    )
    return ReportDetail(
        **base.model_dump(), match_id=r.match_id, club_id=r.club_id, club_name=club_name,
        position_observed=r.position_observed, strengths=r.strengths, weaknesses=r.weaknesses,
        development_areas=r.development_areas, general_observations=r.general_observations,
        ratings=await _ratings(db, r.id),
        versions=[VersionRef(version=v.version, created_at=v.created_at) for v in versions],
        reviews=[
            ReviewOut(
                version=rv.version, decision=rv.decision, comment=rv.comment,
                reviewer_name=name, created_at=rv.created_at,
            )
            for rv, name in reviews
        ],
        is_mine=mine,
        can_edit=mine and ctx.has(catalog.REPORTS_WRITE) and r.status in EDITABLE_REPORT_STATUSES,
        can_review=ctx.has(catalog.REPORTS_REVIEW) and not mine and r.status == "submitted",
        created_at=r.created_at,
    )  # fmt: skip


async def get_report(db: AsyncSession, ctx: AuthContext, report_id: uuid.UUID) -> ReportDetail:
    return await _detail(db, ctx, await _load(db, ctx, report_id))


async def get_version(
    db: AsyncSession, ctx: AuthContext, report_id: uuid.UUID, version: int
) -> dict:
    r = await _load(db, ctx, report_id)
    v = await db.scalar(
        select(ScoutingReportVersion).where(
            ScoutingReportVersion.report_id == r.id, ScoutingReportVersion.version == version
        )
    )
    if v is None:
        raise AppError(404, "not_found", "Version not found")
    return {"version": v.version, "created_at": v.created_at.isoformat(), **v.snapshot}


# ---- commands ------------------------------------------------------------------------
async def create_report(db: AsyncSession, ctx: AuthContext, data: ReportCreate) -> ReportDetail:
    ctx.require(catalog.REPORTS_WRITE)
    profile = await my_scout_profile(db, ctx)
    if profile is None:
        raise AppError(
            422, "scout_profile_required", "Create your scout profile before writing reports"
        )
    if await PlayerRepository(db, ctx).get_visible(data.player_id) is None:
        raise AppError(422, "invalid_player", "Player not found")

    match_id, club_id = data.match_id, data.club_id
    assignment: Assignment | None = None
    if data.assignment_id:
        assignment = await db.scalar(
            select(Assignment)
            .where(
                Assignment.id == data.assignment_id,
                Assignment.organization_id == ctx.organization_id,
                Assignment.scout_profile_id == profile.id,
            )
            .with_for_update()
        )
        if assignment is None:
            raise AppError(422, "invalid_assignment", "Assignment not found")
        if assignment.status not in ("accepted", "in_progress"):
            raise AppError(
                409, "assignment_not_open", "Accept the assignment before reporting on it"
            )
        if assignment.target_type == "player" and assignment.player_id != data.player_id:
            raise AppError(
                422, "assignment_mismatch", "This assignment is about a different player"
            )
        if assignment.target_type == "match":
            if match_id not in (None, assignment.match_id):
                raise AppError(
                    422, "assignment_mismatch", "This assignment is about a different match"
                )
            match_id = assignment.match_id

    if match_id:
        match = await db.scalar(
            select(Match).where(
                Match.id == match_id, visible(Match.organization_id, ctx.organization_id)
            )
        )
        if match is None:
            raise AppError(422, "invalid_match", "Match not found")
        if (
            assignment
            and assignment.target_type == "competition"
            and match.competition_id != assignment.competition_id
        ):
            raise AppError(
                422, "assignment_mismatch", "The match is not in the assigned competition"
            )
        if club_id and club_id not in (match.home_club_id, match.away_club_id):
            raise AppError(422, "invalid_club", "The club is not playing in this match")
    if club_id and await usable_club(db, ctx.organization_id, club_id) is None:
        raise AppError(422, "invalid_club", "Club not found")

    report = ScoutingReport(
        organization_id=ctx.require_org(), scout_profile_id=profile.id,
        assignment_id=assignment.id if assignment else None, player_id=data.player_id,
        match_id=match_id, club_id=club_id, observed_on=data.observed_on,
        position_observed=data.position_observed, recommendation=data.recommendation,
        **{f: getattr(data, f) for f in TEXT_FIELDS},
    )  # fmt: skip
    db.add(report)
    await db.flush()
    db.add_all(
        ScoutingReportRating(report_id=report.id, attribute=a, rating=v)
        for a, v in data.ratings.items()
    )
    if assignment and assignment.status == "accepted":  # starting work moves the assignment on
        await _apply(db, ctx, assignment, "in_progress", "Started a report")
    await record_audit(
        db, action="report.create", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="report", target_id=str(report.id),
    )  # fmt: skip
    await db.commit()
    return await _detail(db, ctx, report)


async def _own_editable(
    db: AsyncSession, ctx: AuthContext, report_id: uuid.UUID, *, lock: bool = True
) -> ScoutingReport:
    ctx.require(catalog.REPORTS_WRITE)
    r = await _load(db, ctx, report_id, lock=lock)
    profile = await _any_profile(db, ctx)
    if profile is None or profile.id != r.scout_profile_id:
        raise AppError(403, "forbidden", "You can only change your own reports")
    if r.status not in EDITABLE_REPORT_STATUSES:
        raise AppError(409, "not_editable", f"A {r.status} report cannot be edited")
    return r


async def update_report(
    db: AsyncSession, ctx: AuthContext, report_id: uuid.UUID, data: ReportUpdate
) -> ReportDetail:
    r = await _own_editable(db, ctx, report_id)
    changes = data.model_dump(exclude_unset=True)
    ratings = changes.pop("ratings", None)
    if changes.get("observed_on", "x") is None:
        raise AppError(422, "validation_error", "observed_on cannot be empty")
    if changes.get("club_id"):
        if await usable_club(db, ctx.organization_id, changes["club_id"]) is None:
            raise AppError(422, "invalid_club", "Club not found")
        if r.match_id:
            m = await db.get(Match, r.match_id)
            if m and changes["club_id"] not in (m.home_club_id, m.away_club_id):
                raise AppError(422, "invalid_club", "The club is not playing in this match")
    for field, value in changes.items():
        setattr(r, field, value)
    for attr, value in (ratings or {}).items():
        existing = await db.get(ScoutingReportRating, (r.id, attr))
        if value is None:
            if existing is not None:
                await db.delete(existing)
        elif existing is None:
            db.add(ScoutingReportRating(report_id=r.id, attribute=attr, rating=value))
        else:
            existing.rating = value
    await record_audit(
        db, action="report.update", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="report", target_id=str(r.id),
    )  # fmt: skip
    await db.commit()
    return await _detail(db, ctx, r)


async def delete_report(db: AsyncSession, ctx: AuthContext, report_id: uuid.UUID) -> None:
    r = await _own_editable(db, ctx, report_id)
    if r.current_version > 0:
        raise AppError(409, "has_history", "A report that was already submitted cannot be deleted")
    await db.delete(r)
    await record_audit(
        db, action="report.delete", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="report", target_id=str(report_id),
    )  # fmt: skip
    await db.commit()


def _snapshot(r: ScoutingReport, ratings: dict[str, int]) -> dict:
    return {
        "player_id": str(r.player_id), "match_id": str(r.match_id) if r.match_id else None,
        "club_id": str(r.club_id) if r.club_id else None, "observed_on": r.observed_on.isoformat(),
        "position_observed": r.position_observed, "recommendation": r.recommendation,
        **{f: getattr(r, f) for f in TEXT_FIELDS}, "ratings": ratings,
    }  # fmt: skip


async def _reviewers(db: AsyncSession, org_id: uuid.UUID, exclude: uuid.UUID) -> list[uuid.UUID]:
    keys = [k for k, (_, _, perms) in ROLES.items() if catalog.REPORTS_REVIEW in perms]
    rows = await db.scalars(
        select(OrganizationMember.user_id)
        .join(Role, Role.id == OrganizationMember.role_id)
        .where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.status == "active",
            Role.key.in_(keys),
            OrganizationMember.user_id != exclude,
        )
    )
    return list(rows)


async def submit_report(db: AsyncSession, ctx: AuthContext, report_id: uuid.UUID) -> ReportDetail:
    r = await _own_editable(db, ctx, report_id)
    ratings = await _ratings(db, r.id)
    missing = []
    if len(ratings) < MIN_RATINGS_TO_SUBMIT:
        missing.append(f"at least {MIN_RATINGS_TO_SUBMIT} ratings")
    if not r.recommendation:
        missing.append("a recommendation")
    if not (r.general_observations or "").strip():
        missing.append("general observations")
    if missing:
        raise AppError(
            422,
            "incomplete_report",
            "The report is not complete: add " + ", ".join(missing),
            missing,
        )

    r.current_version += 1
    r.status, r.submitted_at = "submitted", datetime.now(UTC)
    db.add(
        ScoutingReportVersion(
            report_id=r.id,
            version=r.current_version,
            snapshot=_snapshot(r, ratings),
            created_by_user_id=ctx.user_id,
        )
    )
    player_name = await db.scalar(select(Player.full_name).where(Player.id == r.player_id))
    for user_id in await _reviewers(db, r.organization_id, ctx.user_id):
        await notify(
            db, user_id=user_id, type="report_submitted",
            title=f"Report submitted: {player_name}",
            body=f"Version {r.current_version} is ready for review.",
            link_path=f"/reports/{r.id}", organization_id=r.organization_id,
        )  # fmt: skip
    await record_audit(
        db, action="report.submit", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="report", target_id=str(r.id),
        metadata={"version": r.current_version},
    )  # fmt: skip
    await db.commit()
    return await _detail(db, ctx, r)


async def review_report(
    db: AsyncSession, ctx: AuthContext, report_id: uuid.UUID, data: ReviewBody
) -> ReportDetail:
    ctx.require(catalog.REPORTS_REVIEW)
    r = await _load(db, ctx, report_id, lock=True)
    profile = await _any_profile(db, ctx)
    if profile and profile.id == r.scout_profile_id:
        raise AppError(403, "cannot_review_own", "You cannot review your own report")
    if r.status != "submitted":
        raise AppError(409, "not_submitted", "Only submitted reports can be reviewed")
    comment = data.comment.strip() if data.comment else None
    if data.decision != "approved" and not comment:
        raise AppError(422, "comment_required", "Explain your decision to the scout")

    r.status = data.decision
    db.add(
        ScoutingReportReview(
            report_id=r.id,
            version=r.current_version,
            reviewer_user_id=ctx.user_id,
            decision=data.decision,
            comment=comment,
        )
    )
    scout_user = await db.scalar(
        select(ScoutProfile.user_id).where(ScoutProfile.id == r.scout_profile_id)
    )
    player_name = await db.scalar(select(Player.full_name).where(Player.id == r.player_id))
    ntype = {
        "approved": "report_approved",
        "rejected": "report_rejected",
        "revision_requested": "report_revision_requested",
    }[data.decision]
    if scout_user:
        await notify(
            db, user_id=scout_user, type=ntype,
            title=f"Report {data.decision.replace('_', ' ')}: {player_name}", body=comment,
            link_path=f"/reports/{r.id}", organization_id=r.organization_id,
        )  # fmt: skip
    if data.decision == "revision_requested" and r.assignment_id:
        await return_to_scout_for_revision(
            db, ctx, r.assignment_id, f"Revision requested on a report: {comment}"
        )
    await record_audit(
        db, action="report.review", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="report", target_id=str(r.id),
        metadata={"decision": data.decision, "version": r.current_version},
    )  # fmt: skip
    await db.commit()
    return await _detail(db, ctx, r)
