import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_org_permission
from app.db.session import get_db
from app.models.user import User
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.schemas.organizations import (
    DashboardOut,
    InvitationAccept,
    InvitationCreate,
    InvitationOut,
    InvitationPreview,
    MemberOut,
    MemberUpdate,
    OrganizationCreate,
    OrganizationOut,
    OrganizationUpdate,
)
from app.services import invitations, members, organizations

router = APIRouter(tags=["organizations"])


@router.post("/organizations", response_model=OrganizationOut, status_code=201)
async def create_organization(
    body: OrganizationCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    return await organizations.create_organization(db, user, body, ip)


@router.get("/organizations/{org_id}", response_model=OrganizationOut)
async def get_organization(
    org_id: uuid.UUID,
    ctx: AuthContext = Depends(require_org_permission(catalog.ORG_READ)),
    db: AsyncSession = Depends(get_db),
):
    return await organizations.get_organization(db, ctx)


@router.patch("/organizations/{org_id}", response_model=OrganizationOut)
async def update_organization(
    org_id: uuid.UUID,
    body: OrganizationUpdate,
    ctx: AuthContext = Depends(require_org_permission(catalog.ORG_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    return await organizations.update_organization(db, ctx, body)


@router.get("/organizations/{org_id}/dashboard", response_model=DashboardOut)
async def dashboard(
    org_id: uuid.UUID,
    ctx: AuthContext = Depends(require_org_permission(catalog.ORG_READ)),
    db: AsyncSession = Depends(get_db),
):
    return await organizations.dashboard_counts(db, ctx)


# ---- members -------------------------------------------------------------------------
@router.get("/organizations/{org_id}/members", response_model=list[MemberOut])
async def list_members(
    org_id: uuid.UUID,
    ctx: AuthContext = Depends(require_org_permission(catalog.MEMBERS_READ)),
    db: AsyncSession = Depends(get_db),
):
    return await members.list_members(db, ctx)


@router.patch("/organizations/{org_id}/members/{member_id}", status_code=204)
async def change_member_role(
    org_id: uuid.UUID,
    member_id: uuid.UUID,
    body: MemberUpdate,
    ctx: AuthContext = Depends(require_org_permission(catalog.MEMBERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    await members.change_role(db, ctx, member_id, body.role)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/organizations/{org_id}/members/{member_id}", status_code=204)
async def remove_member(
    org_id: uuid.UUID,
    member_id: uuid.UUID,
    ctx: AuthContext = Depends(require_org_permission(catalog.MEMBERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    await members.remove_member(db, ctx, member_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- invitations ---------------------------------------------------------------------
@router.post("/organizations/{org_id}/invitations", response_model=InvitationOut, status_code=201)
async def create_invitation(
    org_id: uuid.UUID,
    body: InvitationCreate,
    ctx: AuthContext = Depends(require_org_permission(catalog.MEMBERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    return await invitations.create_invitation(db, ctx, body.email, body.role)


@router.get("/organizations/{org_id}/invitations", response_model=list[InvitationOut])
async def list_invitations(
    org_id: uuid.UUID,
    ctx: AuthContext = Depends(require_org_permission(catalog.MEMBERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    return await invitations.list_invitations(db, ctx)


@router.delete("/organizations/{org_id}/invitations/{invitation_id}", status_code=204)
async def revoke_invitation(
    org_id: uuid.UUID,
    invitation_id: uuid.UUID,
    ctx: AuthContext = Depends(require_org_permission(catalog.MEMBERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    await invitations.revoke_invitation(db, ctx, invitation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Token-based routes (the token is the credential, so no organization context is needed).
@router.post("/invitations/preview", response_model=InvitationPreview)
async def preview_invitation(body: InvitationAccept, db: AsyncSession = Depends(get_db)):
    return await invitations.preview_invitation(db, body.token)


@router.post("/invitations/accept", response_model=OrganizationOut)
async def accept_invitation(
    body: InvitationAccept,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await invitations.accept_invitation(db, user, body.token)
