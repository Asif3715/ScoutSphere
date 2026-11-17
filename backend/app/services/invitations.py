import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.invitation import Invitation
from app.models.organization import Organization, OrganizationMember
from app.models.rbac import Role
from app.models.user import User
from app.permissions import catalog
from app.permissions.context import AuthContext
from app.schemas.organizations import InvitationOut, InvitationPreview
from app.services.audit import record_audit
from app.services.members import assert_can_assign
from app.services.organizations import get_role

log = structlog.get_logger()
# One generic error for every unusable-token case: do not reveal which condition failed.
INVALID_INVITATION = AppError(
    400, "invalid_invitation", "This invitation is invalid or has expired"
)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _accept_url(token: str) -> str:
    return f"{get_settings().frontend_url}/invitations/accept?token={token}"


def _out(inv: Invitation, role_key: str, token: str | None = None) -> InvitationOut:
    status = inv.status
    if status == "pending" and inv.expires_at <= _now():
        status = "expired"
    return InvitationOut(
        id=inv.id, email=inv.email, role=role_key, status=status,
        expires_at=inv.expires_at, created_at=inv.created_at,
        accept_url=_accept_url(token) if token else None,
    )  # fmt: skip


async def create_invitation(
    db: AsyncSession, ctx: AuthContext, email: str, role_key: str
) -> InvitationOut:
    ctx.require(catalog.MEMBERS_MANAGE)
    org_id = ctx.require_org()
    assert_can_assign(ctx, role_key)
    email = email.strip()

    existing_member = await db.scalar(
        select(OrganizationMember.id)
        .join(User, User.id == OrganizationMember.user_id)
        .where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.status == "active",
            User.email == email,
        )
    )
    if existing_member:
        raise AppError(409, "already_member", "This person is already a member")

    pending = await db.scalar(
        select(Invitation).where(
            Invitation.organization_id == org_id,
            Invitation.email == email,
            Invitation.status == "pending",
        )
    )
    if pending is not None:
        if pending.expires_at > _now():
            raise AppError(409, "invitation_exists", "A pending invitation already exists")
        pending.status = "revoked"  # lapsed: replace it
        await db.flush()

    token = secrets.token_urlsafe(32)
    role = await get_role(db, role_key)
    inv = Invitation(
        organization_id=org_id,
        email=email,
        role_id=role.id,
        token_hash=_hash(token),
        invited_by_user_id=ctx.user_id,
        expires_at=_now() + timedelta(days=get_settings().invitation_days),
    )
    db.add(inv)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise AppError(409, "invitation_exists", "A pending invitation already exists") from None
    await record_audit(
        db, action="invitation.create", outcome="success", actor_user_id=ctx.user_id,
        organization_id=org_id, target_type="invitation", target_id=str(inv.id),
        metadata={"role": role_key},
    )  # fmt: skip
    await db.commit()

    # Email delivery is stubbed until a provider is chosen (PRD 0.3). The link is only
    # exposed to the API caller outside production-like environments.
    log.info("invitation.email_stub", invitation_id=str(inv.id), to_domain=email.split("@")[-1])
    expose = get_settings().environment in {"local", "test"}
    return _out(inv, role_key, token if expose else None)


async def list_invitations(db: AsyncSession, ctx: AuthContext) -> list[InvitationOut]:
    ctx.require(catalog.MEMBERS_MANAGE)
    rows = await db.execute(
        select(Invitation, Role.key)
        .join(Role, Role.id == Invitation.role_id)
        .where(Invitation.organization_id == ctx.require_org(), Invitation.status == "pending")
        .order_by(Invitation.created_at.desc())
    )
    return [_out(inv, key) for inv, key in rows]


async def revoke_invitation(db: AsyncSession, ctx: AuthContext, invitation_id: uuid.UUID) -> None:
    ctx.require(catalog.MEMBERS_MANAGE)
    inv = await db.scalar(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.organization_id == ctx.require_org(),
            Invitation.status == "pending",
        )
    )
    if inv is None:
        raise AppError(404, "not_found", "Invitation not found")
    inv.status = "revoked"
    await record_audit(
        db, action="invitation.revoke", outcome="success", actor_user_id=ctx.user_id,
        organization_id=ctx.organization_id, target_type="invitation", target_id=str(inv.id),
    )  # fmt: skip
    await db.commit()


async def _find_usable(db: AsyncSession, token: str) -> Invitation:
    inv = await db.scalar(select(Invitation).where(Invitation.token_hash == _hash(token)))
    if inv is None or inv.status != "pending" or inv.expires_at <= _now():
        raise INVALID_INVITATION
    return inv


async def preview_invitation(db: AsyncSession, token: str) -> InvitationPreview:
    inv = await _find_usable(db, token)
    org = await db.get(Organization, inv.organization_id)
    role = await db.get(Role, inv.role_id)
    if org is None or org.status != "active" or role is None:
        raise INVALID_INVITATION
    return InvitationPreview(organization_name=org.name, email=inv.email, role=role.key)


async def accept_invitation(db: AsyncSession, user: User, token: str) -> Organization:
    inv = await _find_usable(db, token)
    if user.email.lower() != inv.email.lower():
        raise AppError(
            403, "email_mismatch", "This invitation was sent to a different email address"
        )
    org = await db.get(Organization, inv.organization_id)
    if org is None or org.status != "active":
        raise INVALID_INVITATION

    membership = await db.scalar(
        select(OrganizationMember)
        .where(
            OrganizationMember.organization_id == inv.organization_id,
            OrganizationMember.user_id == user.id,
        )
        .with_for_update()
    )
    if membership is not None and membership.status == "active":
        raise AppError(409, "already_member", "You are already a member of this organization")
    if membership is None:
        db.add(
            OrganizationMember(
                organization_id=inv.organization_id, user_id=user.id, role_id=inv.role_id
            )
        )
    else:  # previously removed or suspended: reactivate with the invited role
        membership.status, membership.role_id = "active", inv.role_id

    inv.status, inv.accepted_at, inv.accepted_by_user_id = "accepted", _now(), user.id
    await record_audit(
        db, action="invitation.accept", outcome="success", actor_user_id=user.id,
        organization_id=inv.organization_id, target_type="invitation", target_id=str(inv.id),
    )  # fmt: skip
    await db.commit()
    return org
