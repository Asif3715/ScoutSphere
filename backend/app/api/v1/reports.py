import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_auth_context
from app.db.session import get_db
from app.permissions.context import AuthContext
from app.schemas.common import Page, PageParams
from app.schemas.reports import (
    Recommendation,
    ReportCreate,
    ReportDetail,
    ReportStatus,
    ReportSummary,
    ReportUpdate,
    ReviewBody,
)
from app.services import reports

router = APIRouter(prefix="/scouting-reports", tags=["scouting-reports"])
# Permissions live in the service layer so the AI agent gets identical checks.


@router.get("", response_model=Page[ReportSummary])
async def list_reports(
    status: ReportStatus | None = None,
    player_id: uuid.UUID | None = None,
    scout_id: uuid.UUID | None = None,
    match_id: uuid.UUID | None = None,
    assignment_id: uuid.UUID | None = None,
    recommendation: Recommendation | None = None,
    mine: bool = False,
    page: PageParams = Depends(),
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    return await reports.list_reports(
        db, ctx, page, status=status, player_id=player_id, scout_id=scout_id,
        match_id=match_id, assignment_id=assignment_id, recommendation=recommendation, mine=mine,
    )  # fmt: skip


@router.post("", response_model=ReportDetail, status_code=201)
async def create_report(
    body: ReportCreate,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    return await reports.create_report(db, ctx, body)


@router.get("/{report_id}", response_model=ReportDetail)
async def get_report(
    report_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    return await reports.get_report(db, ctx, report_id)


@router.patch("/{report_id}", response_model=ReportDetail)
async def update_report(
    report_id: uuid.UUID,
    body: ReportUpdate,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    return await reports.update_report(db, ctx, report_id, body)


@router.delete("/{report_id}", status_code=204)
async def delete_report(
    report_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    await reports.delete_report(db, ctx, report_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{report_id}/submit", response_model=ReportDetail)
async def submit_report(
    report_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    return await reports.submit_report(db, ctx, report_id)


@router.post("/{report_id}/review", response_model=ReportDetail)
async def review_report(
    report_id: uuid.UUID,
    body: ReviewBody,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    return await reports.review_report(db, ctx, report_id, body)


@router.get("/{report_id}/versions/{version}")
async def get_version(
    report_id: uuid.UUID,
    version: int,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    return await reports.get_version(db, ctx, report_id, version)
