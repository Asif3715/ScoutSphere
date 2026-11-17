from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models.organization import Organization, OrganizationMember
from app.models.rbac import Role
from app.models.user import User
from app.permissions.catalog import ROLES
from app.schemas.auth import (
    LoginRequest,
    MembershipOut,
    MeResponse,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
REFRESH_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        s.refresh_cookie_name,
        token,
        max_age=s.refresh_token_days * 86400,
        httponly=True,
        secure=s.cookie_secure,
        samesite="lax",
        path=REFRESH_PATH,
    )


def _token_response(issued: auth_service.IssuedTokens) -> TokenResponse:
    return TokenResponse(
        access_token=issued.access_token,
        expires_in=issued.expires_in,
        user=UserOut.model_validate(issued.user),
    )


def _client(request: Request) -> tuple[str | None, str | None]:
    return request.headers.get("user-agent"), request.client.host if request.client else None


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    _, ip = _client(request)
    user = await auth_service.register_user(
        db, email=body.email, password=body.password, full_name=body.full_name,
        account_type=body.account_type, ip=ip,
    )  # fmt: skip
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    ua, ip = _client(request)
    issued = await auth_service.login(db, email=body.email, password=body.password, ua=ua, ip=ip)
    _set_refresh_cookie(response, issued.refresh_token)
    return _token_response(issued)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=get_settings().refresh_cookie_name),
):
    if not refresh_token:
        raise AppError(401, "invalid_refresh_token", "Invalid or expired refresh token")
    ua, ip = _client(request)
    try:
        issued = await auth_service.refresh(db, token=refresh_token, ua=ua, ip=ip)
    except AppError:
        response.delete_cookie(get_settings().refresh_cookie_name, path=REFRESH_PATH)
        raise
    _set_refresh_cookie(response, issued.refresh_token)
    return _token_response(issued)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=get_settings().refresh_cookie_name),
):
    await auth_service.logout(db, token=refresh_token)
    response.delete_cookie(get_settings().refresh_cookie_name, path=REFRESH_PATH)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(Organization.id, Organization.name, Role.key)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .join(Role, Role.id == OrganizationMember.role_id)
            .where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.status == "active",
                Organization.status == "active",
            )
            .order_by(Organization.name)
        )
    ).all()
    memberships = [
        MembershipOut(
            organization_id=oid, organization_name=name, role=role,
            permissions=sorted(ROLES[role][2]),
        )
        for oid, name, role in rows
    ]  # fmt: skip
    return MeResponse(user=UserOut.model_validate(user), memberships=memberships)
