import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.db.session import get_db
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.schemas.clubs import ClubCreate, ClubOut
from app.schemas.common import Page, PageParams
from app.schemas.organizations import OrganizationOut, OrganizationStatusUpdate
from app.services import clubs, organizations

router = APIRouter(prefix="/platform", tags=["platform"])
_admin = require_permission(catalog.PLATFORM_ORGS_MANAGE)


@router.get("/organizations", response_model=Page[OrganizationOut])
async def list_organizations(
    q: str | None = Query(default=None, max_length=100),
    page: PageParams = Depends(),
    ctx: AuthContext = Depends(_admin),
    db: AsyncSession = Depends(get_db),
):
    items, total = await organizations.list_all_organizations(db, ctx, page, q)
    return Page(
        items=[OrganizationOut.model_validate(o) for o in items],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.patch("/organizations/{org_id}/status", response_model=OrganizationOut)
async def set_status(
    org_id: uuid.UUID,
    body: OrganizationStatusUpdate,
    ctx: AuthContext = Depends(_admin),
    db: AsyncSession = Depends(get_db),
):
    return await organizations.set_organization_status(db, ctx, org_id, body.status)


@router.post("/clubs", response_model=ClubOut, status_code=201)
async def create_reference_club(
    body: ClubCreate,
    ctx: AuthContext = Depends(_admin),
    db: AsyncSession = Depends(get_db),
):
    return await clubs.create_reference_club(db, ctx, body)
