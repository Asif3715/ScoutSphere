import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_auth_context
from app.db.session import get_db
from app.permissions.context import AuthContext
from app.schemas.assignments import (
    AssignmentCreate,
    AssignmentDetail,
    AssignmentOut,
    AssignmentStatus,
    AssignmentSummary,
    AssignmentUpdate,
    TargetType,
    TransitionBody,
)
from app.schemas.common import Page, PageParams
from app.services import assignments

router = APIRouter(prefix="/assignments", tags=["assignments"])
# Permissions are enforced inside the service (shared with the AI agent); the context
# dependency verifies organization membership.


@router.get("", response_model=Page[AssignmentOut])
async def list_assignments(
    status: AssignmentStatus | None = None,
    scout_id: uuid.UUID | None = None,
    target_type: TargetType | None = None,
    overdue: bool = False,
    mine: bool = False,
    page: PageParams = Depends(),
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    return await assignments.list_assignments(
        db, ctx, page, status=status, scout_id=scout_id, target_type=target_type,
        overdue=overdue, mine=mine,
    )  # fmt: skip


@router.get("/summary", response_model=AssignmentSummary)
async def summary(ctx: AuthContext = Depends(get_auth_context), db: AsyncSession = Depends(get_db)):
    return await assignments.summary(db, ctx)


@router.post("", response_model=AssignmentDetail, status_code=201)
async def create_assignment(
    body: AssignmentCreate,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    return await assignments.create_assignment(db, ctx, body)


@router.get("/{assignment_id}", response_model=AssignmentDetail)
async def get_assignment(
    assignment_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    return await assignments.get_assignment(db, ctx, assignment_id)


@router.patch("/{assignment_id}", response_model=AssignmentDetail)
async def update_assignment(
    assignment_id: uuid.UUID,
    body: AssignmentUpdate,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    return await assignments.update_assignment(db, ctx, assignment_id, body)


@router.post("/{assignment_id}/transition", response_model=AssignmentDetail)
async def transition(
    assignment_id: uuid.UUID,
    body: TransitionBody,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    return await assignments.transition(db, ctx, assignment_id, body.to, body.note)
