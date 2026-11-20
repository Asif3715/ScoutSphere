import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_auth_context
from app.core.errors import AppError
from app.db.session import get_db
from app.domain.scouting import RATING_ATTRIBUTES, RATING_MAX, RATING_MIN
from app.permissions.context import AuthContext
from app.schemas.common import Page, PageParams
from app.schemas.players import Foot, Position
from app.schemas.recruitment import (
    AssignScoutBody,
    BulkAddResult,
    CandidateAdd,
    CandidateBulkAdd,
    CandidateDetail,
    CandidateMatch,
    CandidateOut,
    CompareBody,
    CompareOut,
    Priority,
    RequirementCreate,
    RequirementOut,
    RequirementStatus,
    RequirementSummary,
    RequirementUpdate,
    Stage,
    StageMove,
)
from app.services import comparison, recruitment

router = APIRouter(prefix="/recruitment", tags=["recruitment"])
# Permissions are enforced in the services (shared with the AI agent); the context dependency
# verifies organization membership.
Ctx = Depends(get_auth_context)
Db = Depends(get_db)


# ---- requirements -------------------------------------------------------------------------
@router.get("/requirements", response_model=Page[RequirementSummary])
async def list_requirements(
    status: RequirementStatus | None = None,
    priority: Priority | None = None,
    q: str | None = Query(default=None, max_length=100),
    page: PageParams = Depends(),
    ctx: AuthContext = Ctx,
    db: AsyncSession = Db,
):
    return await recruitment.list_requirements(db, ctx, page, status=status, priority=priority, q=q)


@router.post("/requirements", response_model=RequirementOut, status_code=201)
async def create_requirement(
    body: RequirementCreate, ctx: AuthContext = Ctx, db: AsyncSession = Db
):
    return await recruitment.create_requirement(db, ctx, body)


@router.get("/requirements/{requirement_id}", response_model=RequirementOut)
async def get_requirement(requirement_id: uuid.UUID, ctx: AuthContext = Ctx, db: AsyncSession = Db):
    return await recruitment.get_requirement(db, ctx, requirement_id)


@router.patch("/requirements/{requirement_id}", response_model=RequirementOut)
async def update_requirement(
    requirement_id: uuid.UUID,
    body: RequirementUpdate,
    ctx: AuthContext = Ctx,
    db: AsyncSession = Db,
):
    return await recruitment.update_requirement(db, ctx, requirement_id, body)


@router.get("/requirements/{requirement_id}/matches", response_model=Page[CandidateMatch])
async def requirement_matches(
    requirement_id: uuid.UUID,
    exclude_pipeline: bool = True,
    page: PageParams = Depends(),
    ctx: AuthContext = Ctx,
    db: AsyncSession = Db,
):
    return await recruitment.requirement_matches(db, ctx, requirement_id, page, exclude_pipeline)


# ---- pipeline -------------------------------------------------------------------------------
@router.get("/requirements/{requirement_id}/candidates", response_model=Page[CandidateOut])
async def list_candidates(
    requirement_id: uuid.UUID,
    stage: Stage | None = None,
    page: PageParams = Depends(),
    ctx: AuthContext = Ctx,
    db: AsyncSession = Db,
):
    return await recruitment.list_candidates(db, ctx, requirement_id, stage, page)


@router.post(
    "/requirements/{requirement_id}/candidates", response_model=CandidateOut, status_code=201
)
async def add_candidate(
    requirement_id: uuid.UUID, body: CandidateAdd, ctx: AuthContext = Ctx, db: AsyncSession = Db
):
    return await recruitment.add_candidate(db, ctx, requirement_id, body.player_id, body.notes)


@router.post(
    "/requirements/{requirement_id}/candidates/bulk", response_model=BulkAddResult, status_code=201
)
async def add_candidates(
    requirement_id: uuid.UUID, body: CandidateBulkAdd, ctx: AuthContext = Ctx, db: AsyncSession = Db
):
    return await recruitment.add_candidates(db, ctx, requirement_id, body.player_ids)


@router.get("/candidates/{candidate_id}", response_model=CandidateDetail)
async def get_candidate(candidate_id: uuid.UUID, ctx: AuthContext = Ctx, db: AsyncSession = Db):
    return await recruitment.get_candidate(db, ctx, candidate_id)


@router.post("/candidates/{candidate_id}/stage", response_model=CandidateDetail)
async def move_stage(
    candidate_id: uuid.UUID, body: StageMove, ctx: AuthContext = Ctx, db: AsyncSession = Db
):
    return await recruitment.move_stage(db, ctx, candidate_id, body.to, body.note)


@router.post("/candidates/{candidate_id}/assign-scout", response_model=CandidateDetail)
async def assign_scout(
    candidate_id: uuid.UUID, body: AssignScoutBody, ctx: AuthContext = Ctx, db: AsyncSession = Db
):
    return await recruitment.assign_scout(db, ctx, candidate_id, body)


# ---- ad hoc search and comparison ------------------------------------------------------------
@router.get("/search", response_model=Page[CandidateMatch])
async def search_players(
    q: str | None = Query(default=None, max_length=100),
    position: Position | None = None,
    min_age: int | None = Query(default=None, ge=8, le=60),
    max_age: int | None = Query(default=None, ge=8, le=60),
    nationality: str | None = Query(default=None, max_length=100),
    foot: Foot | None = None,
    min_appearances: int | None = Query(default=None, ge=0, le=5000),
    min_rating: list[str] = Query(
        default_factory=list, description="attribute:minimum, e.g. passing:7"
    ),
    page: PageParams = Depends(),
    ctx: AuthContext = Ctx,
    db: AsyncSession = Db,
):
    """Discover players by structured filters and by *scout-rating* filters (average over the
    organization's approved reports)."""
    ratings: dict[str, int] = {}
    for item in min_rating:
        attr, _, value = item.partition(":")
        if (
            attr not in RATING_ATTRIBUTES
            or not value.isdigit()
            or not RATING_MIN <= int(value) <= RATING_MAX
        ):
            raise AppError(
                422, "validation_error", f"Invalid min_rating '{item}' (use attribute:1-10)"
            )
        ratings[attr] = int(value)
    criteria = recruitment.Criteria(
        q=q, position=position, min_age=min_age, max_age=max_age, nationality=nationality,
        foot=foot, min_appearances=min_appearances, ratings=ratings,
    )  # fmt: skip
    if min_age and max_age and min_age > max_age:
        raise AppError(422, "validation_error", "min_age cannot exceed max_age")
    return await recruitment.find_candidates(db, ctx, criteria, page)


@router.post("/compare", response_model=CompareOut)
async def compare(body: CompareBody, ctx: AuthContext = Ctx, db: AsyncSession = Db):
    return await comparison.compare_players(db, ctx, body.player_ids, body.requirement_id)
